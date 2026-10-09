// On-demand system audio only. No microphone, network, files or output routing changes.
import Foundation
import ScreenCaptureKit
import CoreMedia
import CoreGraphics
import AudioToolbox
import Darwin

func report(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value) {
        FileHandle.standardError.write(data + Data([10]))
    }
}
func audioError(_ message: String) -> Never {
    report(["type":"error", "message":message]); exit(2)
}

final class AudioCapture: NSObject, SCStreamOutput, SCStreamDelegate, @unchecked Sendable {
    let queue = DispatchQueue(label:"desktop.audio", qos:.userInteractive)
    let writer = DispatchQueue(label:"desktop.audio.output", qos:.userInteractive)
    let slot = DispatchSemaphore(value:1)
    var stream: SCStream?
    var timer: DispatchSourceTimer?
    var sampleCount = 0

    func emit(_ samples: [Int16]) {
        guard slot.wait(timeout:.now()) == .success else { return }
        let pcm = samples.withUnsafeBytes { Data($0) }
        writer.async { [self] in
            defer { slot.signal() }
            let header: [String:Any] = ["type":"audio", "bytes":pcm.count, "rate":48000, "channels":2]
            guard let json = try? JSONSerialization.data(withJSONObject:header) else { return }
            FileHandle.standardOutput.write(json + Data([10]) + pcm)
        }
    }

    func start(demo: Bool) async throws {
        if demo {
            let source = DispatchSource.makeTimerSource(queue:queue)
            source.schedule(deadline:.now(), repeating:.milliseconds(20))
            source.setEventHandler { [self] in
                var samples = [Int16](); samples.reserveCapacity(1920)
                for i in 0..<960 {
                    let t = Double(sampleCount + i) / 48000
                    samples.append(Int16(sin(2 * .pi * 440 * t) * 3000))
                    samples.append(Int16(sin(2 * .pi * 660 * t) * 3000))
                }
                sampleCount += 960; emit(samples)
            }
            timer = source; source.resume()
        } else {
            guard CGPreflightScreenCaptureAccess() else {
                throw NSError(domain:"Allow Screen & System Audio Recording for this host or Terminal, then restart the host", code:1)
            }
            let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly:true)
            guard let display = content.displays.first(where:{$0.displayID == CGMainDisplayID()}) else {
                throw NSError(domain:"Main display unavailable for system audio", code:2)
            }
            let config = SCStreamConfiguration()
            // This stream has no screen output. Video uses its existing independent encoder.
            config.width = 2; config.height = 2
            config.minimumFrameInterval = CMTime(value:1, timescale:1)
            config.capturesAudio = true; config.sampleRate = 48000; config.channelCount = 2
            config.excludesCurrentProcessAudio = true
            let filter = SCContentFilter(display:display, excludingWindows:[])
            let capture = SCStream(filter:filter, configuration:config, delegate:self)
            try capture.addStreamOutput(self, type:.audio, sampleHandlerQueue:queue)
            stream = capture
            try await capture.startCapture()
        }
        report(["type":"ready", "rate":48000, "channels":2, "capture":demo ? "synthetic" : "system audio"])
        DispatchQueue.global(qos:.utility).async {
            while readLine() != nil {}
            exit(0) // Parent closes stdin to stop audio capture.
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) { audioError("System audio stopped: \(error)") }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer, of type: SCStreamOutputType) {
        guard type == .audio, sample.isValid,
              let format = CMSampleBufferGetFormatDescription(sample),
              let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(format)?.pointee else { return }
        guard asbd.mFormatID == kAudioFormatLinearPCM, asbd.mSampleRate == 48000,
              asbd.mChannelsPerFrame == 2, asbd.mBitsPerChannel == 32,
              asbd.mFormatFlags & kAudioFormatFlagIsFloat != 0 else { audioError("Unsupported system audio format") }
        let count = CMSampleBufferGetNumSamples(sample)
        guard count > 0, count <= 8192 else { return }
        var size = 0
        CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample, bufferListSizeNeededOut:&size,
            bufferListOut:nil, bufferListSize:0, blockBufferAllocator:nil, blockBufferMemoryAllocator:nil,
            flags:0, blockBufferOut:nil)
        guard size > 0, size < 65536 else { return }
        let memory = UnsafeMutableRawPointer.allocate(byteCount:size, alignment:16)
        defer { memory.deallocate() }
        let list = memory.assumingMemoryBound(to:AudioBufferList.self)
        var block: CMBlockBuffer?
        let result = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(sample, bufferListSizeNeededOut:nil,
            bufferListOut:list, bufferListSize:size, blockBufferAllocator:nil, blockBufferMemoryAllocator:nil,
            flags:UInt32(kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment), blockBufferOut:&block)
        guard result == noErr else { return }
        let buffers = UnsafeMutableAudioBufferListPointer(list)
        let planar = asbd.mFormatFlags & kAudioFormatFlagIsNonInterleaved != 0
        guard buffers.count >= (planar ? 2 : 1) else { return }
        for b in buffers.prefix(planar ? 2 : 1) {
            guard b.mData != nil, b.mDataByteSize >= count * (planar ? 4 : 8) else { return }
        }
        var output = [Int16](); output.reserveCapacity(count * 2)
        for i in 0..<count {
            for channel in 0..<2 {
                let values = buffers[planar ? channel : 0].mData!.assumingMemoryBound(to:Float.self)
                let value = values[planar ? i : i * 2 + channel]
                output.append(value.isFinite ? Int16(max(-1, min(1, value)) * 32767) : 0)
            }
        }
        emit(output)
        withExtendedLifetime(block) {}
    }
}

@main struct SystemAudio {
    static func main() async {
        signal(SIGPIPE, SIG_IGN)
        let capture = AudioCapture()
        do { try await capture.start(demo:CommandLine.arguments.contains("--demo")) }
        catch { audioError(String(describing:error)) }
        while true { try? await Task.sleep(nanoseconds:1_000_000_000) }
    }
}
