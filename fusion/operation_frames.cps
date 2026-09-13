/** Diagnostic CAM coordinate evidence only. Never a machine post or safety verdict. */
description = "Silta indexed operation frame diagnostic";
vendor = "Silta";
extension = "jsonl";
capabilities = CAPABILITY_MILLING;
minimumRevision = 45991;
var count = 0;
function emit(value) { writeln(JSON.stringify(value)); }
function vec(p) { return [p.x, p.y, p.z]; }
function onOpen() {
  if (unit != MM) { error("Diagnostic requires millimeter output units"); return; }
  emit({type:"header", schema_version:1, units:"mm", callback_frame:"post_engine_default_WCS", coordinate_validation:"pending_live_calibration", collision_coverage:false});
}
function onSection() {
  if (currentSection.isMultiAxis() || currentSection.isOptimizedForMachine()) {
    error("Diagnostic supports unoptimized indexed sections only"); return;
  }
  cancelTransformation();
  emit({type:"section", id:currentSection.getId(), work_offset:currentSection.getWorkOffset(),
    origin_wcs:vec(currentSection.getWorkOrigin()),
    local_basis_points_wcs:[vec(currentSection.getWCSPosition(new Vector(0,0,0))),vec(currentSection.getWCSPosition(new Vector(1,0,0))),vec(currentSection.getWCSPosition(new Vector(0,1,0))),vec(currentSection.getWCSPosition(new Vector(0,0,1)))],
    tool_axis_wcs:vec(currentSection.getGlobalInitialToolAxis()), tool_diameter_mm:tool.diameter});
}
function motion(kind,x,y,z,extra) {
  var row={type:kind, section:currentSection.getId(), record:getCurrentRecordId(), start:vec(getCurrentPosition()), end:[x,y,z], movement:movement};
  if(extra) { for(var key in extra) {row[key]=extra[key];} }
  emit(row); count++;
}
function onRapid(x,y,z) { motion("rapid",x,y,z); }
function onLinear(x,y,z,feed) { motion("linear",x,y,z,{feed_mm_min:feed}); }
function onCircular(clockwise,cx,cy,cz,x,y,z,feed) {
  motion("circular",x,y,z,{center:[cx,cy,cz], normal:vec(getCircularNormal()), clockwise:clockwise, sweep_radians:getCircularSweep(), full_circle:isFullCircle(), helical:isHelical(), feed_mm_min:feed});
}
function onCycle() { error("Cycle coverage is unsupported; diagnostic incomplete"); }
function onLinear5D() { error("Simultaneous motion unsupported"); }
function onRapid5D() { error("Simultaneous motion unsupported"); }
function onClose() { emit({type:"footer", motion_count:count, completed:true, collision_coverage:false}); }
