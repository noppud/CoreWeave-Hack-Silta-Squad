// Record one exact Fusion window through ScreenCaptureKit; never sends UI input.
// macOS 15+. Usage: window_video DOCUMENT OUTPUT_MP4 STOP_FILE STATUS_JSON MAX_SECONDS FPS
import AppKit
import AVFoundation
import CoreGraphics
import Foundation
import ScreenCaptureKit

func report(_ value: [String: Any], to path: String) throws {
    let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
    try data.write(to: URL(fileURLWithPath: path), options: .atomic)
}
struct CaptureError: Error, CustomStringConvertible {
    let description: String
    init(_ message: String) { description = message }
}
@available(macOS 15.0, *)
final class RecordingEvents: NSObject, SCRecordingOutputDelegate, SCStreamOutput {
    private let lock = NSLock()
    private var started = false, finished = false
    private var error: String? = nil
    private var frames = 0
    func snapshot() -> (Bool, Bool, String?, Int) {
        lock.lock(); defer { lock.unlock() }
        return (started, finished, error, frames)
    }
    func recordingOutputDidStartRecording(_ recordingOutput: SCRecordingOutput) {
        lock.lock(); started = true; lock.unlock()
    }
    func recordingOutputDidFinishRecording(_ recordingOutput: SCRecordingOutput) {
        lock.lock(); finished = true; lock.unlock()
    }
    func recordingOutput(_ recordingOutput: SCRecordingOutput, didFailWithError error: Error) {
        lock.lock(); self.error = error.localizedDescription; lock.unlock()
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .screen, sampleBuffer.isValid,
              let attachments = CMSampleBufferGetSampleAttachmentsArray(sampleBuffer,
                  createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              let status = attachments.first?[.status] as? Int,
              status == SCFrameStatus.complete.rawValue else { return }
        lock.lock(); frames += 1; lock.unlock()
    }
}
@main
struct WindowVideo {
    static func main() async {
        let args = CommandLine.arguments
        if args.count == 2 && args[1] == "--preflight" {
            let value: [String: Any] = ["screen_recording_access": CGPreflightScreenCaptureAccess(),
                                       "macos_supported": ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 15]
            let data = try! JSONSerialization.data(withJSONObject: value, options: [.sortedKeys])
            print(String(data: data, encoding: .utf8)!); return
        }
        guard args.count == 7, let maximum = Double(args[5]), maximum >= 2, maximum <= 900,
              let fps = Int32(args[6]), [30, 60].contains(fps) else {
            fputs("Usage: window_video DOCUMENT OUTPUT_MP4 STOP_FILE STATUS_JSON MAX_SECONDS FPS\n", stderr)
            exit(2)
        }
        let status = args[4]
        do {
            guard #available(macOS 15.0, *) else { throw CaptureError("macOS 15+ is required") }
            try await capture(args[1], args[2], args[3], status, maximum, fps)
        } catch {
            try? report(["status": "failed", "error": String(describing: error)], to: status)
            fputs("Fusion window recording failed: \(error)\n", stderr)
            exit(1)
        }
    }
    @available(macOS 15.0, *)
    static func capture(_ document: String, _ output: String, _ stopFile: String,
                        _ status: String, _ maximum: Double, _ fps: Int32) async throws {
        guard CGPreflightScreenCaptureAccess() else {
            throw CaptureError("Screen recording permission is missing; no prompt or capture attempted")
        }
        guard !FileManager.default.fileExists(atPath: output),
              !FileManager.default.fileExists(atPath: stopFile) else {
            throw CaptureError("Recording output/stop marker already exists")
        }
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: true)
        let pattern = "^" + NSRegularExpression.escapedPattern(for: document)
            + "(?: \\([^)]*\\))? - Autodesk Fusion"
        let matches = content.windows.filter {
            $0.owningApplication?.bundleIdentifier == "com.autodesk.fusion360"
            && ($0.title ?? "").range(of: pattern, options: .regularExpression) != nil
        }
        guard matches.count == 1 else { throw CaptureError("Expected exactly one visible Fusion document window") }
        let window = matches[0]
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        let scale = min(1920.0 / filter.contentRect.width, Double(filter.pointPixelScale))
        config.width = max(2, Int(filter.contentRect.width * scale) / 2 * 2)
        config.height = max(2, Int(filter.contentRect.height * scale) / 2 * 2)
        config.minimumFrameInterval = CMTime(value: 1, timescale: fps)
        config.showsCursor = false
        config.capturesAudio = false
        config.captureMicrophone = false
        config.queueDepth = 5
        let recordingConfig = SCRecordingOutputConfiguration()
        recordingConfig.outputURL = URL(fileURLWithPath: output)
        recordingConfig.videoCodecType = .h264
        recordingConfig.outputFileType = .mp4
        let events = RecordingEvents()
        let stream = SCStream(filter: filter, configuration: config, delegate: nil)
        try stream.addStreamOutput(events, type: .screen,
                                   sampleHandlerQueue: DispatchQueue(label: "silta.window.frames"))
        let recording = SCRecordingOutput(configuration: recordingConfig, delegate: events)
        try stream.addRecordingOutput(recording)
        try await stream.startCapture()
        let start = Date()
        while !events.snapshot().0 {
            if let error = events.snapshot().2 { throw CaptureError(error) }
            guard Date().timeIntervalSince(start) < 15 else { throw CaptureError("Recorder did not start") }
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        try report(["status": "recording", "window_id": window.windowID,
                    "document": document, "width": config.width, "height": config.height,
                    "fps_requested": fps, "output": output], to: status)
        var stopReason = "stop_requested"
        while !FileManager.default.fileExists(atPath: stopFile) {
            if let error = events.snapshot().2 { throw CaptureError(error) }
            if Date().timeIntervalSince(start) >= maximum { stopReason = "recording_limit"; break }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        try await stream.stopCapture()
        let stopping = Date()
        while !events.snapshot().1 {
            if let error = events.snapshot().2 { throw CaptureError(error) }
            guard Date().timeIntervalSince(stopping) < 20 else { throw CaptureError("MP4 finalization timed out") }
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        let asset = AVURLAsset(url: URL(fileURLWithPath: output))
        let duration = try await asset.load(.duration).seconds
        let tracks = try await asset.loadTracks(withMediaType: .video)
        guard duration.isFinite, duration > 0, tracks.count == 1, events.snapshot().3 > 1 else {
            throw CaptureError("No valid multi-frame video was recorded")
        }
        let nominalFPS = try await tracks[0].load(.nominalFrameRate)
        let size = try await tracks[0].load(.naturalSize)
        try report(["status": "recorded", "document": document, "output": output,
                    "window_id": window.windowID, "duration_seconds": duration,
                    "width": size.width, "height": size.height, "fps_nominal": nominalFPS,
                    "complete_frames": events.snapshot().3, "stop_reason": stopReason,
                    "source": "ScreenCaptureKit Fusion window", "audio": false], to: status)
    }
}
