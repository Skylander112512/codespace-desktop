// Foreground helper: ScreenCaptureKit -> VideoToolbox H.264 -> framed stdout.
// No network, input control, files, microphone, or background service.
import Foundation
import ScreenCaptureKit
import VideoToolbox
import CoreMedia
import CoreVideo
import CoreGraphics
import Darwin

func diagnostic(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) {
        FileHandle.standardError.write(data + Data([10]))
    }
}
func fail(_ message: String) -> Never {
    diagnostic(["type": "error", "message": message]); exit(2)
}
func checked(_ code: OSStatus, _ operation: String) throws {
    if code != noErr { throw NSError(domain: operation, code: Int(code)) }
}

final class Encoder: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    let queue = DispatchQueue(label: "desktop.capture", qos: .userInteractive)
    let output = DispatchQueue(label: "desktop.output", qos: .userInteractive)
    var session: VTCompressionSession?
    var stream: SCStream?
    var timer: DispatchSourceTimer?
    var keepalive: DispatchSourceTimer?
    var lastImage: CVPixelBuffer?
    var width = 1280, height = 720, fps = 60, bitrate = 4_000_000
    var pending = false, forceKeyframe = true
    var submitted: UInt64 = 0, skipped: UInt64 = 0
    var started = CMClockGetTime(CMClockGetHostTimeClock())
    var submittedAt: UInt64 = 0
    let demo: Bool
    let maxFPS: Int

    init(demo: Bool, maxFPS: Int = 60, compact: Bool = false, fullHD: Bool = false, initialBitrate: Int = 4_000_000) {
        self.demo = demo; self.maxFPS = maxFPS; self.fps = maxFPS
        if compact { width = 854; height = 480 }
        else if fullHD { width = 1920; height = 1080 }
        bitrate = max(500_000, min(16_000_000, initialBitrate))
    }

    func configureEncoder() throws {
        let specification: [CFString: Any] = [
            kVTVideoEncoderSpecification_RequireHardwareAcceleratedVideoEncoder: true,
            kVTVideoEncoderSpecification_EnableLowLatencyRateControl: true
        ]
        try checked(VTCompressionSessionCreate(allocator: nil, width: Int32(width), height: Int32(height),
            codecType: kCMVideoCodecType_H264, encoderSpecification: specification as CFDictionary,
            imageBufferAttributes: nil, compressedDataAllocator: nil,
            outputCallback: { reference, _, status, flags, sample in
                guard let reference else { return }
                let encoder = Unmanaged<Encoder>.fromOpaque(reference).takeUnretainedValue()
                encoder.queue.async { encoder.encoded(status: status, flags: flags, sample: sample) }
            }, refcon: Unmanaged.passUnretained(self).toOpaque(), compressionSessionOut: &session), "Create hardware encoder")
        guard let session else { throw NSError(domain: "No encoder", code: -1) }
        for (key, value) in [
            (kVTCompressionPropertyKey_RealTime, true as CFTypeRef),
            (kVTCompressionPropertyKey_AllowFrameReordering, false as CFTypeRef),
            (kVTCompressionPropertyKey_ProfileLevel, kVTProfileLevel_H264_ConstrainedBaseline_AutoLevel as CFTypeRef),
            (kVTCompressionPropertyKey_AverageBitRate, bitrate as CFTypeRef),
            (kVTCompressionPropertyKey_ExpectedFrameRate, fps as CFTypeRef),
            (kVTCompressionPropertyKey_MaxKeyFrameInterval, fps as CFTypeRef),
            (kVTCompressionPropertyKey_MaxKeyFrameIntervalDuration, 1 as CFTypeRef)
        ] { try checked(VTSessionSetProperty(session, key: key, value: value), "Set \(key)") }
        try checked(VTCompressionSessionPrepareToEncodeFrames(session), "Prepare encoder")
        var hardware: Unmanaged<CFTypeRef>?
        let hardwareStatus = VTSessionCopyProperty(session, key: kVTCompressionPropertyKey_UsingHardwareAcceleratedVideoEncoder,
                                         allocator: nil, valueOut: &hardware)
        if hardwareStatus == noErr {
            guard (hardware?.takeRetainedValue() as? Bool) == true else { throw NSError(domain: "Hardware encoding unavailable", code: -1) }
        } else if hardwareStatus != kVTPropertyNotSupportedErr {
            try checked(hardwareStatus, "Check hardware encoder")
        }
        // Some low-latency encoders omit this read-only property. Session
        // creation above REQUIRES hardware and fails rather than using software.
        diagnostic(["type": "ready", "hardware": true, "capture": demo ? "synthetic" : "ScreenCaptureKit",
                    "codec": "H264", "width": width, "height": height, "fps": fps, "bitrate": bitrate])
    }

    func configuration() -> SCStreamConfiguration {
        let config = SCStreamConfiguration()
        config.width = width; config.height = height
        config.minimumFrameInterval = CMTime(value: 1, timescale: CMTimeScale(fps))
        config.queueDepth = 3 // Apple's minimum; encoder accepts at most one pending frame.
        config.pixelFormat = kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
        config.showsCursor = true; config.capturesAudio = false
        return config
    }

    func start() async throws {
        if demo {
            try configureEncoder()
            let source = DispatchSource.makeTimerSource(queue: queue)
            source.schedule(deadline: .now(), repeating: .nanoseconds(1_000_000_000 / fps))
            source.setEventHandler { [weak self] in self?.demoFrame() }
            timer = source; source.resume()
        } else {
            guard CGPreflightScreenCaptureAccess() else {
                throw NSError(domain: "Screen Recording permission is required; enable the host or Terminal and restart", code: -1)
            }
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)
            guard let display = content.displays.first(where: { $0.displayID == CGMainDisplayID() }) else {
                throw NSError(domain: "Main display unavailable", code: -1)
            }
            // Preserve aspect ratio; input coordinates also use the main display.
            let scale = min(Double(width) / Double(display.width), Double(height) / Double(display.height))
            width = max(2, Int(Double(display.width) * scale) / 2 * 2)
            height = max(2, Int(Double(display.height) * scale) / 2 * 2)
            try configureEncoder()
            let filter = SCContentFilter(display: display, excludingWindows: [])
            let capture = SCStream(filter: filter, configuration: configuration(), delegate: self)
            try capture.addStreamOutput(self, type: .screen, sampleHandlerQueue: queue)
            stream = capture
            try await capture.startCapture()
            // ScreenCaptureKit can stop emitting complete frames on an idle
            // desktop. Refresh the last image twice a second so receiver
            // freshness checks can distinguish a still screen from a stall.
            let refresh = DispatchSource.makeTimerSource(queue: queue)
            refresh.schedule(deadline: .now() + .milliseconds(500), repeating: .milliseconds(500))
            refresh.setEventHandler { [weak self] in
                guard let self, let image = self.lastImage,
                      DispatchTime.now().uptimeNanoseconds - self.submittedAt >= 500_000_000 else { return }
                self.submit(image)
            }
            keepalive = refresh; refresh.resume()
        }
        DispatchQueue.global(qos: .utility).async { [self] in
            while let line = readLine() {
                guard line.utf8.count < 4096, let data = line.data(using: .utf8),
                      let command = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
                queue.async { [self] in apply(command) }
            }
            exit(0) // Parent owns the session. Closing stdin ends capture immediately.
        }
    }

    func apply(_ command: [String: Any]) {
        if command["type"] as? String == "keyframe" { forceKeyframe = true; return }
        guard command["type"] as? String == "configure", let session else { return }
        if let value = command["bitrate"] as? Int {
            bitrate = max(500_000, min(16_000_000, value))
            if VTSessionSetProperty(session, key: kVTCompressionPropertyKey_AverageBitRate, value: bitrate as CFTypeRef) != noErr {
                diagnostic(["type":"warning", "message":"Bitrate update rejected"])
            }
        }
        if let value = command["fps"] as? Int {
            fps = max(15, min(maxFPS, value))
            _ = VTSessionSetProperty(session, key: kVTCompressionPropertyKey_ExpectedFrameRate, value: fps as CFTypeRef)
            timer?.schedule(deadline: .now(), repeating: .nanoseconds(1_000_000_000 / fps))
            let config = configuration()
            if let stream { Task { do { try await stream.updateConfiguration(config) }
                catch { diagnostic(["type":"warning", "message":"Capture update failed: \(error)"]) } } }
        }
        diagnostic(["type":"configured", "bitrate":bitrate, "fps":fps])
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) { fail("Capture stopped: \(error)") }
    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .screen, sampleBuffer.isValid,
              let attachments = CMSampleBufferGetSampleAttachmentsArray(sampleBuffer, createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              let status = attachments.first?[.status] as? Int,
              status == SCFrameStatus.complete.rawValue,
              let image = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        lastImage = image
        submit(image)
    }

    func demoFrame() {
        if pending { skipped += 1; return }
        var buffer: CVPixelBuffer?
        let attributes = [kCVPixelBufferIOSurfacePropertiesKey: [:]] as CFDictionary
        guard CVPixelBufferCreate(nil, width, height, kCVPixelFormatType_32BGRA, attributes, &buffer) == kCVReturnSuccess,
              let buffer else { fail("Synthetic frame allocation failed") }
        CVPixelBufferLockBaseAddress(buffer, [])
        if let bytes = CVPixelBufferGetBaseAddress(buffer) {
            let stride = CVPixelBufferGetBytesPerRow(buffer) / 4
            let pixels = bytes.assumingMemoryBound(to: UInt32.self)
            let x = Int(submitted * 8) % max(1, width - 100)
            for y in 0..<height {
                let row = pixels.advanced(by: y * stride)
                row.update(repeating: 0xFF172B40, count: width)
                if y >= height / 3 && y < height / 3 + 100 { row.advanced(by:x).update(repeating:0xFFB7F5C8,count:100) }
            }
        }
        CVPixelBufferUnlockBaseAddress(buffer, [])
        submit(buffer)
    }

    func submit(_ image: CVPixelBuffer) {
        guard !pending, let session else { skipped += 1; return }
        pending = true; submitted += 1; submittedAt = DispatchTime.now().uptimeNanoseconds
        let pts = CMTimeSubtract(CMClockGetTime(CMClockGetHostTimeClock()), started)
        let options = forceKeyframe ? [kVTEncodeFrameOptionKey_ForceKeyFrame: true] as CFDictionary : nil
        forceKeyframe = false
        let result = VTCompressionSessionEncodeFrame(session, imageBuffer: image, presentationTimeStamp: pts,
            duration: CMTime(value:1,timescale:CMTimeScale(fps)), frameProperties: options, sourceFrameRefcon: nil, infoFlagsOut: nil)
        if result != noErr { pending = false; fail("Encode failed: \(result)") }
    }

    func encoded(status: OSStatus, flags: VTEncodeInfoFlags, sample: CMSampleBuffer?) {
        guard status == noErr else { fail("Encoder callback failed: \(status)") }
        guard !flags.contains(.frameDropped), let sample, CMSampleBufferDataIsReady(sample),
              let format = CMSampleBufferGetFormatDescription(sample), let block = CMSampleBufferGetDataBuffer(sample) else {
            queue.async { self.pending = false; self.forceKeyframe = true }; return
        }
        let elapsed = Double(DispatchTime.now().uptimeNanoseconds - submittedAt) / 1_000_000
        let attachment = (CMSampleBufferGetSampleAttachmentsArray(sample, createIfNecessary: false) as? [[CFString:Any]])?.first
        let keyframe = (attachment?[kCMSampleAttachmentKey_NotSync] as? Bool) != true
        var annex = Data(), nalHeader: Int32 = 0
        var count = 0
        let first = CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format, parameterSetIndex:0,
            parameterSetPointerOut:nil, parameterSetSizeOut:nil, parameterSetCountOut:&count, nalUnitHeaderLengthOut:&nalHeader)
        guard first == noErr, (1...4).contains(nalHeader) else { fail("Invalid H.264 format") }
        if keyframe {
            for index in 0..<count {
                var pointer: UnsafePointer<UInt8>?, length = 0
                guard CMVideoFormatDescriptionGetH264ParameterSetAtIndex(format, parameterSetIndex:index,
                    parameterSetPointerOut:&pointer, parameterSetSizeOut:&length, parameterSetCountOut:nil,
                    nalUnitHeaderLengthOut:nil) == noErr, let pointer else { fail("Missing H.264 parameter sets") }
                annex.append(contentsOf: [0,0,0,1]); annex.append(pointer, count:length)
            }
        }
        let size = CMBlockBufferGetDataLength(block)
        var avcc = Data(count:size)
        let copied = avcc.withUnsafeMutableBytes { bytes in CMBlockBufferCopyDataBytes(block, atOffset:0, dataLength:size, destination:bytes.baseAddress!) }
        guard copied == noErr else { fail("Cannot read encoded frame") }
        var offset = 0
        while offset + Int(nalHeader) <= avcc.count {
            var length = 0
            for byte in avcc[offset..<(offset + Int(nalHeader))] { length = (length << 8) | Int(byte) }
            offset += Int(nalHeader)
            guard length > 0, offset + length <= avcc.count else { fail("Invalid H.264 unit length") }
            annex.append(contentsOf:[0,0,0,1]); annex.append(avcc[offset..<(offset + length)]); offset += length
        }
        guard offset == avcc.count, annex.count < 4_000_000 else { fail("Invalid encoded frame size") }
        let pts = CMTimeConvertScale(CMSampleBufferGetPresentationTimeStamp(sample), timescale:90_000, method:.default).value
        let header: [String: Any] = ["type":"frame", "bytes":annex.count, "pts":pts, "keyframe":keyframe,
            "width":width, "height":height, "encode_ms":elapsed, "skipped":skipped]
        guard let json = try? JSONSerialization.data(withJSONObject:header,options:[.sortedKeys]) else { fail("Frame header failed") }
        let record = json + Data([10]) + annex
        output.async { [self] in
            FileHandle.standardOutput.write(record)
            queue.async { self.pending = false }
        }
    }
}

@main struct ScreenEncoder {
    static func main() async {
        signal(SIGPIPE, SIG_IGN)
        let arguments = CommandLine.arguments
        let rateIndex = arguments.firstIndex(of: "--bitrate")
        let rate = rateIndex.flatMap { $0 + 1 < arguments.count ? Int(arguments[$0 + 1]) : nil } ?? 4_000_000
        let encoder = Encoder(demo: arguments.contains("--demo"), maxFPS: arguments.contains("--fps30") ? 30 : 60, compact: arguments.contains("--compact"), fullHD: arguments.contains("--1080p"), initialBitrate: rate)
        do {
            try await encoder.start()
            while !Task.isCancelled { try await Task.sleep(nanoseconds: 60_000_000_000) }
        } catch { fail("\(error)") }
    }
}
