#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p ../bin
xcrun swiftc -swift-version 5 -O -parse-as-library -target arm64-apple-macos14.0 \
  -framework ScreenCaptureKit -framework VideoToolbox -framework CoreMedia \
  -framework CoreVideo -framework CoreGraphics ScreenEncoder.swift -o ../bin/ScreenEncoder
codesign --force --sign - ../bin/ScreenEncoder
