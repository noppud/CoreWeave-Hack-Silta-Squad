import AppKit
import ApplicationServices
import Foundation
func attr(_ e:AXUIElement,_ name:String)->CFTypeRef? {var value:CFTypeRef?;return AXUIElementCopyAttributeValue(e,name as CFString,&value) == .success ? value:nil}
func fail(_ s:String)->Never {print(s);exit(1)}
let apps=NSRunningApplication.runningApplications(withBundleIdentifier:"com.autodesk.fusion360")
guard apps.count==1,AXIsProcessTrusted(),CommandLine.arguments.count==3 else {fail("Expected Fusion and explicit document/action")}
let expected=CommandLine.arguments[1],mode=CommandLine.arguments[2]
guard ["inspect","press"].contains(mode) else {fail("Unsupported action")}
let app=AXUIElementCreateApplication(apps[0].processIdentifier)
apps[0].activate(options:[.activateAllWindows])
AXUIElementSetAttributeValue(app,kAXFrontmostAttribute as CFString,kCFBooleanTrue)
let deadline=Date(timeIntervalSinceNow:8)
repeat {
 let windows=attr(app,"AXWindows") as? [AXUIElement] ?? []
 let titles=windows.compactMap{attr($0,"AXTitle") as? String}
 var seen=[AXUIElement](),matches=[AXUIElement]()
 func walk(_ e:AXUIElement,_ depth:Int) {
  if depth>16 || seen.count>1500 || seen.contains(where:{CFEqual($0,e)}) {return}
  seen.append(e)
  if attr(e,"AXRole") as? String == "AXApplication" {return}
  if attr(e,"AXIdentifier") as? String == "QTApplication.IronUI::QtPlayButton" {matches.append(e)}
  for c in attr(e,"AXChildren") as? [AXUIElement] ?? [] {walk(c,depth+1)}
 }
 if titles.filter({$0.hasPrefix(expected) && $0.contains(" - Autodesk Fusion")}).count==1 {
  for w in windows {walk(w,0)}
  if matches.count==1,attr(matches[0],"AXEnabled") as? Bool == true {
   var properties=["document":expected,"mode":mode,"control":"QTApplication.IronUI::QtPlayButton"]
   if mode=="press" {guard AXUIElementPerformAction(matches[0],kAXPressAction as CFString) == .success else {fail("Press did not succeed")};properties["pressed"]="true"}
   print(String(data:try JSONSerialization.data(withJSONObject:properties,options:[.sortedKeys]),encoding:.utf8)!);exit(0)
  }
 }
 RunLoop.current.run(until:Date(timeIntervalSinceNow:0.08))
} while Date()<deadline
fail("Playback control never became available in the exact document")
