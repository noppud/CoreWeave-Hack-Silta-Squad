// Fixed macOS UI transport for Fusion. No model calls; requires foreground access.
import AppKit
import ApplicationServices
import Foundation
import ImageIO
import Vision

func fail(_ message: String) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: ["error":message], options:[.sortedKeys])
    print(String(data:data, encoding:.utf8)!); exit(1)
}
func attribute(_ element: AXUIElement, _ key: String) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, key as CFString, &value) == .success else {return nil}
    return value
}
let args = CommandLine.arguments
guard args.count >= 4 else {fail("Usage: native_ui EXPECTED_DOCUMENT OUTPUT_PNG inspect|focus|click|drag|set|press|key [args]")}
let expected = args[1], output = args[2], action = args[3]
let apps = NSRunningApplication.runningApplications(withBundleIdentifier:"com.autodesk.fusion360")
guard apps.count == 1, AXIsProcessTrusted() else {fail("Expected one Fusion process and existing accessibility access")}
let app = apps[0], pid = apps[0].processIdentifier
let application = AXUIElementCreateApplication(pid)
func windowList() -> [[String:Any]] {
    CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as? [[String:Any]] ?? []
}
func mainWindow() -> [String:Any] {
    // Saved hub documents can append the hub name, e.g. " (helios)", to
    // the exact document title. The API still returns the unadorned name.
    let pattern = "^" + NSRegularExpression.escapedPattern(for:expected) + "\\*?(?:\\s*\\([^)]*\\))* - Autodesk Fusion"
    func matching() -> [[String:Any]] {
        windowList().filter { ($0[kCGWindowOwnerPID as String] as? Int32) == pid && ($0[kCGWindowName as String] as? String ?? "").range(of:pattern,options:.regularExpression) != nil }
    }
    var matches = matching()
    // Cloud document activation can precede its WindowServer title/Space update.
    // Observe that transition for focus only; never retry a click or accept a
    // different document merely because it belongs to the same application.
    if action == "focus" {
        let deadline = Date(timeIntervalSinceNow:3)
        while matches.isEmpty && Date() < deadline {
            RunLoop.current.run(until:Date(timeIntervalSinceNow:0.1))
            matches = matching()
        }
    }
    guard matches.count == 1 else {fail("Expected exactly one visible Fusion document: " + expected)}
    return matches[0]
}
func rect(_ window: [String:Any]) -> CGRect {
    let b = window[kCGWindowBounds as String] as! [String:Double]
    return CGRect(x:b["X"]!,y:b["Y"]!,width:b["Width"]!,height:b["Height"]!)
}
func foreground() {
    guard (attribute(application,"AXFrontmost") as? Bool) == true else {fail("Fusion is not foreground; no input sent")}
}
if action == "focus" {
    app.activate(options:[.activateAllWindows])
    AXUIElementSetAttributeValue(application,kAXFrontmostAttribute as CFString,kCFBooleanTrue)
    if let focus = attribute(application,"AXFocusedWindow") {
        AXUIElementPerformAction(focus as! AXUIElement,kAXRaiseAction as CFString)
    }
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.6))
}
let main = mainWindow(), bounds = rect(main)
var elements: [AXUIElement] = []
var rows: [[String:Any]] = []
struct AXIdentity: Hashable {
    let element: AXUIElement
    static func == (lhs: AXIdentity, rhs: AXIdentity) -> Bool {
        CFEqual(lhs.element, rhs.element)
    }
    func hash(into hasher: inout Hasher) { hasher.combine(CFHash(element)) }
}
var visited = Set<AXIdentity>()
func walk(_ element: AXUIElement, _ depth: Int, _ windowTitle: String) {
    guard depth < 16, elements.count < 1500, !visited.contains(AXIdentity(element: element)) else {return}
    visited.insert(AXIdentity(element: element))
    // Fusion sometimes returns the application itself for all windows when backgrounded.
    guard (attribute(element,"AXRole") as? String) != "AXApplication" else {return}
    var row: [String:Any] = ["index":elements.count,"window":windowTitle]
    for key in ["AXRole","AXTitle","AXDescription","AXValue","AXIdentifier","AXEnabled"] {
        if let value = attribute(element,key) {
            if let s = value as? String {row[key] = s}
            else if let n = value as? NSNumber {row[key] = n}
        }
    }
    var position = CGPoint.zero, size = CGSize.zero
    if let p = attribute(element,"AXPosition"), CFGetTypeID(p) == AXValueGetTypeID(),
       let s = attribute(element,"AXSize"), CFGetTypeID(s) == AXValueGetTypeID(),
       AXValueGetValue(p as! AXValue,.cgPoint,&position), AXValueGetValue(s as! AXValue,.cgSize,&size) {
        row["bounds"] = [position.x,position.y,size.width,size.height]
    }
    var names: CFArray?
    if AXUIElementCopyActionNames(element,&names) == .success {row["actions"] = names as? [String] ?? []}
    elements.append(element); rows.append(row)
    if let children = attribute(element,"AXChildren") as? [AXUIElement] {
        for child in children {walk(child,depth+1,windowTitle)}
    }
}
func collect() {
    rows = []; elements = []; visited = []
    if let windows = attribute(application,"AXWindows") as? [AXUIElement] {
        for window in windows {walk(window,0,attribute(window,"AXTitle") as? String ?? "")}
    }
}
func click(_ point: CGPoint, _ right: Bool, _ dragEnd: CGPoint? = nil) {
    foreground()
    if let dragEnd, !bounds.contains(dragEnd) {fail("Drag outside expected Fusion window")}
    guard bounds.contains(point) else {fail("Click outside expected Fusion window")}
    let source = CGEventSource(stateID:.hidSystemState)
    let button: CGMouseButton = right ? .right : .left
    CGWarpMouseCursorPosition(point)
    CGEvent(mouseEventSource:source,mouseType:.mouseMoved,mouseCursorPosition:point,mouseButton:button)!.post(tap:.cghidEventTap)
    Thread.sleep(forTimeInterval:0.15)
    let top = windowList().first { ($0[kCGWindowAlpha as String] as? Double ?? 0) > 0 && rect($0).contains(point) }
    var hit: AXUIElement?, hitPID: pid_t = 0
    if AXUIElementCopyElementAtPosition(AXUIElementCreateSystemWide(),Float(point.x),Float(point.y),&hit) == .success, let hit {AXUIElementGetPid(hit,&hitPID)}
    guard (top?[kCGWindowOwnerPID as String] as? Int32) == pid || hitPID == pid else {fail("Another application covers the click target")}
    let hitWindow = main
    for type: CGEventType in [right ? .rightMouseDown : .leftMouseDown, right ? .rightMouseUp : .leftMouseUp] {
        if type == .leftMouseUp, let dragEnd {
            for step in 1...20 {
                foreground()
                let f = Double(step) / 20
                let next = CGPoint(x:point.x+(dragEnd.x-point.x)*f,y:point.y+(dragEnd.y-point.y)*f)
                let move = CGEvent(mouseEventSource:source,mouseType:.leftMouseDragged,mouseCursorPosition:next,mouseButton:.left)!
                move.flags = []; move.post(tap:.cghidEventTap)
                Thread.sleep(forTimeInterval:0.02)
            }
        }
        let eventPoint = type == .leftMouseUp ? (dragEnd ?? point) : point
        let event = CGEvent(mouseEventSource:source,mouseType:type,mouseCursorPosition:eventPoint,mouseButton:button)!
        event.flags = []; event.setIntegerValueField(.mouseEventClickState,value:1)
        event.setIntegerValueField(.mouseEventWindowUnderMousePointer,value:(hitWindow[kCGWindowNumber as String] as! NSNumber).int64Value)
        event.setIntegerValueField(.mouseEventWindowUnderMousePointerThatCanHandleThisEvent,value:(hitWindow[kCGWindowNumber as String] as! NSNumber).int64Value)
        event.post(tap:.cghidEventTap); Thread.sleep(forTimeInterval:0.08)
    }
}
// Only AX-targeted actions need a pre-action tree. Every action still receives
// a fresh post-action observation; clicks use their own window/foreground guards.
if ["set", "press", "export-name", "inspect", "inspect-ax"].contains(action) {collect()}
if action == "click" {
    guard args.count == 7, let x=Double(args[4]), let y=Double(args[5]), ["left","right"].contains(args[6]) else {fail("Expected relative x y left|right")}
    click(CGPoint(x:bounds.minX+x,y:bounds.minY+y),args[6] == "right")
} else if action == "drag" {
    guard args.count == 8, let x=Double(args[4]), let y=Double(args[5]), let ex=Double(args[6]), let ey=Double(args[7]) else {fail("Expected drag start and end relative coordinates")}
    click(CGPoint(x:bounds.minX+x,y:bounds.minY+y),false,CGPoint(x:bounds.minX+ex,y:bounds.minY+ey))
} else if action == "scroll" {
    foreground()
    guard args.count == 7, let x=Double(args[4]), let y=Double(args[5]), let delta=Int32(args[6]), abs(delta) <= 1000 else {fail("Expected scroll x y bounded pixel delta")}
    let point = CGPoint(x:bounds.minX+x,y:bounds.minY+y)
    guard bounds.contains(point) else {fail("Scroll must remain inside Fusion window")}
    let event = CGEvent(scrollWheelEvent2Source:nil,units:.pixel,wheelCount:1,wheel1:delta,wheel2:0,wheel3:0)!
    event.location=point; event.post(tap:.cghidEventTap)
    RunLoop.current.run(until:Date(timeIntervalSinceNow:0.2))
} else if action == "set" || action == "press" {
    foreground()
    guard args.count >= 6 else {fail("Expected window title and exact AXIdentifier")}
    let matches = rows.enumerated().filter { $0.element["window"] as? String == args[4] && $0.element["AXIdentifier"] as? String == args[5] }
    guard matches.count == 1 else {fail("Expected one exact accessibility control")}
    let element = elements[matches[0].offset]
    if action == "set" {
        guard args.count == 7 else {fail("Expected text value")}
        guard AXUIElementSetAttributeValue(element,kAXValueAttribute as CFString,args[6] as CFString) == .success else {fail("AX set failed")}
    } else {
        guard AXUIElementPerformAction(element,kAXPressAction as CFString) == .success else {fail("AX press failed")}
    }
} else if action == "export-name" {
    foreground()
    guard args.count == 5, args[4].range(of:"^silta-stock-[a-f0-9]{32}$",options:.regularExpression) != nil,
          rows.contains(where: {$0["window"] as? String == "Save Stock"}) else {fail("Expected unique stock name in Save Stock")}
    for down in [true,false] {
        let event = CGEvent(keyboardEventSource:nil,virtualKey:0,keyDown:down)!
        event.flags = .maskCommand; event.post(tap:.cghidEventTap)
    }
    let utf16 = Array(args[4].utf16)
    for down in [true,false] {
        let event = CGEvent(keyboardEventSource:nil,virtualKey:0,keyDown:down)!
        event.flags = []
        event.keyboardSetUnicodeString(stringLength:utf16.count,unicodeString:utf16)
        event.post(tap:.cghidEventTap)
    }
} else if action == "key" {
    foreground()
    guard args.count == 5, ["return","escape","tab"].contains(args[4]) else {fail("Only Return, Escape and Tab keys supported")}
    let code: CGKeyCode = args[4] == "return" ? 36 : args[4] == "escape" ? 53 : 48
    for down in [true,false] {
        let event = CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down)!
        event.flags = []; event.post(tap:.cghidEventTap); Thread.sleep(forTimeInterval:0.05)
    }
} else if !["inspect","inspect-ax","focus"].contains(action) {fail("Unsupported action")}
if !["inspect", "inspect-ax"].contains(action) {RunLoop.current.run(until:Date(timeIntervalSinceNow:0.3)); collect()}
foreground()
// Issues verdicts come from AX text. Avoid screenshot/OCR work when the caller
// explicitly requests only that text; visual controls retain full observations.
if action == "inspect-ax" {
    let result: [String:Any] = ["document":expected,"foreground":true,
        "window_bounds":[bounds.minX,bounds.minY,bounds.width,bounds.height],
        "elements":rows,"texts":[],"small_window_texts":[],"observation_mode":"ax-only"]
    let data = try JSONSerialization.data(withJSONObject:result, options:[.sortedKeys])
    print(String(data:data,encoding:.utf8)!); exit(0)
}
let capture = Process()
capture.executableURL = URL(fileURLWithPath:"/usr/sbin/screencapture")
capture.arguments = ["-x","-R\(Int(bounds.minX)),\(Int(bounds.minY)),\(Int(bounds.width)),\(Int(bounds.height))",output]
try capture.run(); capture.waitUntilExit()
guard capture.terminationStatus == 0 else {fail("Could not capture current Fusion region")}
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate; request.usesLanguageCorrection = false; request.recognitionLanguages = ["en-US"]
request.minimumTextHeight = 0.003
try VNImageRequestHandler(url:URL(fileURLWithPath:output),options:[:]).perform([request])
var texts: [[String:Any]] = (request.results ?? []).compactMap { observation in
    guard let text = observation.topCandidates(1).first else {return nil}
    let b = observation.boundingBox
    return ["text":text.string,"confidence":text.confidence,"bounds":[b.minX*bounds.width,(1-b.maxY)*bounds.height,b.width*bounds.width,b.height*bounds.height]]
}
// Small numeric slider bubbles are omitted by full-window OCR. Read their
// observed window rectangles at native resolution, preserving the source bounds.
var smallWindowTexts: [[String:Any]] = []
if let source = CGImageSourceCreateWithURL(URL(fileURLWithPath:output) as CFURL,nil),
   let captured = CGImageSourceCreateImageAtIndex(source,0,nil) {
    let scale = Double(captured.width) / bounds.width
    // Vision can omit small labels in a large Retina screenshot. Read the
    // observed floating Fusion panels separately at native resolution, replacing
    // full-image text in those rectangles to avoid duplicate clickable labels.
    for window in windowList() where (window[kCGWindowOwnerPID as String] as? Int32) == pid {
        let r = rect(window)
        guard r.width >= 240, r.width <= 320, r.height >= 150,
              bounds.contains(r) else {continue}
        let crop = CGRect(x:(r.minX-bounds.minX)*scale,y:(r.minY-bounds.minY)*scale,
                          width:r.width*scale,height:r.height*scale)
        guard let bitmap = captured.cropping(to:crop) else {continue}
        let read = VNRecognizeTextRequest()
        read.recognitionLevel = .accurate; read.usesLanguageCorrection = false
        read.recognitionLanguages = ["en-US"]; read.minimumTextHeight = 0.003
        try VNImageRequestHandler(cgImage:bitmap,options:[:]).perform([read])
        let local = CGRect(x:r.minX-bounds.minX,y:r.minY-bounds.minY,
                           width:r.width,height:r.height)
        texts.removeAll { row in
            // Vision/CGRect coordinates above are CGFloat values. A [Double]
            // cast fails silently in an Any dictionary, retaining duplicate OCR.
            guard let b = row["bounds"] as? [CGFloat], b.count == 4 else {return false}
            return local.contains(CGPoint(x:b[0]+b[2]/2,y:b[1]+b[3]/2))
        }
        for item in read.results ?? [] {
            guard let candidate = item.topCandidates(1).first else {continue}
            let b = item.boundingBox
            texts.append(["text":candidate.string,"confidence":candidate.confidence,
                          "bounds":[local.minX+b.minX*r.width,
                                    local.minY+(1-b.maxY)*r.height,
                                    b.width*r.width,b.height*r.height]])
        }
    }
    for window in windowList() where (window[kCGWindowOwnerPID as String] as? Int32) == pid {
        let r = rect(window)
        guard r.width < 100, r.height < 50, bounds.contains(r) else {continue}
        let crop = CGRect(x:(r.minX-bounds.minX)*scale,y:(r.minY-bounds.minY)*scale,width:r.width*scale,height:r.height*scale)
        guard let bitmap = captured.cropping(to:crop) else {continue}
        let read = VNRecognizeTextRequest()
        read.recognitionLevel = .accurate; read.usesLanguageCorrection = false
        try VNImageRequestHandler(cgImage:bitmap,options:[:]).perform([read])
        for item in read.results ?? [] {
            if let candidate = item.topCandidates(1).first {
                smallWindowTexts.append(["text":candidate.string,"confidence":candidate.confidence,"bounds":[r.minX-bounds.minX,r.minY-bounds.minY,r.width,r.height]])
            }
        }
    }
}
let result: [String:Any] = ["document":expected,"foreground":attribute(application,"AXFrontmost") as? Bool ?? false,
    "window_bounds":[bounds.minX,bounds.minY,bounds.width,bounds.height],"screenshot":output,"elements":rows,"texts":texts,"small_window_texts":smallWindowTexts,
    "windows":windowList().filter {($0[kCGWindowOwnerPID as String] as? Int32) == pid}.map {["title":$0[kCGWindowName as String] ?? "", "bounds":$0[kCGWindowBounds as String] ?? [:]]}]
let data = try JSONSerialization.data(withJSONObject:result, options:[.sortedKeys])
print(String(data:data,encoding:.utf8)!)
