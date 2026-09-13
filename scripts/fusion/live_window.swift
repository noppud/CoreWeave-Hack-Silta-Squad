// Read-only live preview of one Fusion window. No clicks, keys or Fusion API calls.
import AppKit
import CoreGraphics
import CoreImage
import Foundation
import ScreenCaptureKit

func writeStatus(_ value: [String: Any], _ directory: URL) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) {
        try? data.write(to: directory.appendingPathComponent("status.json"), options: .atomic)
    }
}

final class Frames: NSObject, SCStreamOutput, SCStreamDelegate {
    let directory: URL
    let context = CIContext(options: [.cacheIntermediates: false])
    let lock = NSLock()
    var count = 0
    var lastFrame = 0.0
    var failure: String? = nil
    var frameWidth = 0
    var frameHeight = 0
    init(_ directory: URL) { self.directory = directory }
    func snapshot() -> (Int, Double, String?, Int, Int) {
        lock.lock(); defer { lock.unlock() }
        return (count, lastFrame, failure, frameWidth, frameHeight)
    }
    func stream(_ stream: SCStream, didStopWithError error: Error) {
        lock.lock(); failure = error.localizedDescription; lock.unlock()
    }
    func stream(_ stream: SCStream, didOutputSampleBuffer sample: CMSampleBuffer,
                of type: SCStreamOutputType) {
        guard type == .screen, sample.isValid,
              let attachment = CMSampleBufferGetSampleAttachmentsArray(sample,
                createIfNecessary: false) as? [[SCStreamFrameInfo: Any]],
              attachment.first?[.status] as? Int == SCFrameStatus.complete.rawValue,
              let pixel = CMSampleBufferGetImageBuffer(sample) else { return }
        let source = CIImage(cvPixelBuffer: pixel)
        // Canvas-only output. Scale the calibrated rectangle by window width:
        // ScreenCaptureKit can change buffer height when the window is obscured.
        let bounds = source.extent
        let unit = bounds.width / 1440.0
        let rectangle = CGRect(x: bounds.minX + 390 * unit,
            y: bounds.maxY - 664 * unit,
            width: 670 * unit,
            height: 480 * unit).integral.intersection(bounds)
        let image = source.cropped(to: rectangle).transformed(by:
            CGAffineTransform(translationX: -rectangle.minX, y: -rectangle.minY))
        guard let color = CGColorSpace(name: CGColorSpace.sRGB),
              let jpeg = context.jpegRepresentation(of: image, colorSpace: color,
                options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.72]) else { return }
        do {
            try jpeg.write(to: directory.appendingPathComponent("frame.jpg"), options: .atomic)
            lock.lock(); count += 1; lastFrame = Date().timeIntervalSince1970
            frameWidth = Int(image.extent.width); frameHeight = Int(image.extent.height)
            lock.unlock()
        } catch {
            lock.lock(); failure = "Could not write preview frame"; lock.unlock()
        }
    }
}

@main struct LiveWindow {
    static func main() async {
        _ = NSApplication.shared
        guard CommandLine.arguments.count == 2 else { exit(2) }
        let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        do {
            guard CGPreflightScreenCaptureAccess() else {
                throw NSError(domain: "Silta", code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Screen recording access is unavailable"])
            }
            let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
            let windows = content.windows.filter {
                $0.owningApplication?.bundleIdentifier == "com.autodesk.fusion360"
                && ($0.title ?? "").contains(" - Autodesk Fusion")
                && !($0.title ?? "").hasPrefix("Loading additional modules")
                && $0.frame.width > 500 && $0.frame.height > 300
            }
            guard windows.count == 1 else {
                throw NSError(domain: "Silta", code: 2,
                    userInfo: [NSLocalizedDescriptionKey: "Waiting for exactly one Fusion main window"])
            }
            let window = windows[0]
            let filter = SCContentFilter(desktopIndependentWindow: window)
            let configuration = SCStreamConfiguration()
            let scale = min(1440.0 / filter.contentRect.width, Double(filter.pointPixelScale))
            configuration.width = max(2, Int(filter.contentRect.width * scale) / 2 * 2)
            configuration.height = max(2, Int(filter.contentRect.height * scale) / 2 * 2)
            configuration.minimumFrameInterval = CMTime(value: 1, timescale: 20)
            configuration.queueDepth = 3
            configuration.showsCursor = false
            configuration.capturesAudio = false
            let output = Frames(directory)
            let stream = SCStream(filter: filter, configuration: configuration, delegate: output)
            try stream.addStreamOutput(output, type: .screen,
                sampleHandlerQueue: DispatchQueue(label: "silta.live.preview"))
            try await stream.startCapture()
            let started = Date()
            while !FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop").path)
                && Date().timeIntervalSince(started) < 14400 {
                let snapshot = output.snapshot()
                if let message = snapshot.2 {
                    throw NSError(domain: "Silta", code: 3,
                        userInfo: [NSLocalizedDescriptionKey: message])
                }
                let info = CGWindowListCopyWindowInfo(.optionIncludingWindow, window.windowID) as? [[String: Any]]
                let title = info?.first?[kCGWindowName as String] as? String ?? window.title ?? "Fusion"
                writeStatus([
                    "status": snapshot.0 > 0 ? "live" : "starting",
                    "heartbeat": Date().timeIntervalSince1970,
                    "captured_at": snapshot.1, "frames": snapshot.0,
                    "window_id": window.windowID, "window_title": title,
                    "width": snapshot.3, "height": snapshot.4,
                    "viewport_only": true,
                    "fps_limit": 20, "source": "ScreenCaptureKit Fusion window",
                    "read_only_capture": true
                ], directory)
                try await Task.sleep(nanoseconds: 500_000_000)
            }
            try await stream.stopCapture()
            writeStatus(["status": "stopped", "heartbeat": Date().timeIntervalSince1970], directory)
        } catch {
            writeStatus(["status": "unavailable", "error": error.localizedDescription,
                         "heartbeat": Date().timeIntervalSince1970], directory)
            exit(1)
        }
    }
}
