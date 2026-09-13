// Explanatory sequence; never launches a job or creates persisted learning artifacts.
export function walkthroughOrder(parts){
  return [...parts].sort((a,b)=>(b.summary?.best_seconds??0)-(a.summary?.best_seconds??0));
}
export function walkthroughKnowledge(checks,memories){
  // These small example contracts are display-only, never installed into the worker.
  const examples=[
    {id:'example-tool',title:'Reject tools outside the loaded magazine',content:'def check_tool_assignment(plan, loaded_tool_ids):\n    """Walkthrough example: validate an explicit tool list."""\n    missing = set(plan["tool_ids"]) - set(loaded_tool_ids)\n    return {"passed": not missing, "issues": [f"Missing tool: {t}" for t in sorted(missing)]}\n'},
    {id:'example-travel',title:'Keep indexed positions inside axis travel',content:'def check_axis_travel(positions, axis_limits):\n    """Walkthrough example: positions and limits share units."""\n    issues = []\n    for position in positions:\n        for axis, value in position.items():\n            low, high = axis_limits[axis]\n            if not low <= value <= high:\n                issues.append(f"{axis} position {value} exceeds travel")\n    return {"passed": not issues, "issues": issues}\n'},
    {id:'example-feed',title:'Respect the assigned tool’s feed limits',content:'def check_feed_limits(operations, tool_limits):\n    """Walkthrough example: supplied limits in mm/min."""\n    issues = []\n    for op in operations:\n        limit = tool_limits[op["tool_id"]]["max_feed_mm_min"]\n        if not 0 < op["feed_mm_min"] <= limit:\n            issues.append(f"Feed exceeds limit: {op[\'name\']}")\n    return {"passed": not issues, "issues": issues}\n'},
    {id:'example-retract',title:'Retract before rotating to the next face',content:'def check_index_retract(index_moves, required_clearance_mm):\n    """Walkthrough example: clearance in the configured fixture frame."""\n    issues = ["Indexing before safe retract" for move in index_moves\n              if move["retract_clearance_mm"] < required_clearance_mm]\n    return {"passed": not issues, "issues": issues}\n'}
  ];
  return {checks:[...checks,...examples].slice(0,6),memories:[...memories,
    'Group compatible operations by tool to reduce tool changes. Preserve required face access and finishing order, keep the accepted CAD fixed, and verify the new plan.',
    'Use remaining-stock information to avoid machining volumes already cleared. Preserve the finishing allowance, compare estimated time, and retain only a verified improvement.',
    'Reduce repeated indexing when operations can share the same orientation. Keep collision-safe retracts and fixture clearance, and compare the resulting plan under unchanged limits.'
  ].slice(0,5)};
}
export function buildWalkthrough(parts, checks, memories){
  const steps=[];let learnedChecks=[],learnedMemories=[];
  const spread=items=>{
    let previous=-1;
    return new Map(items.slice(0,parts.length).map((item,i,all)=>{
      const desired=Math.round((i/Math.max(1,all.length-1))**1.55*(parts.length-1));
      const index=Math.min(parts.length-all.length+i,Math.max(previous+1,desired));
      previous=index;return [index,item];
    }));
  };
  const checkAt=spread(checks),memoryAt=spread(memories);
  parts.forEach((part,partIndex)=>{
    let attempt=1;
    const add=(stage,title,extra={})=>steps.push({stage,title,partIndex,attempt,sequence:steps.length,event:{event:'walkthrough',raw:{}},checks:[...learnedChecks],memories:[...learnedMemories],...extra});
    const code=()=>add('cam',attempt===1?'Generate machining code':'Regenerate machining code');
    const cycle=()=>{add('checks','Checks passed',{passed:true});add('fusion','Simulation passed',{passed:true});};
    add('input','Drawing received');code();
    if(partIndex===1&&learnedChecks.length){add('checks','Check failed',{passed:false});attempt++;code();}
    if(checkAt.has(partIndex)){
      add('checks',learnedChecks.length?'Checks passed':'No learned checks yet',{passed:true});
      add('fusion','Simulation failed',{passed:false});
      learnedChecks.push(checkAt.get(partIndex));add('checks','New check added',{addedCheck:checkAt.get(partIndex)});
      attempt++;code();
    }
    cycle();
    if(memoryAt.has(partIndex)){
      add('judge','Machining plan is too slow',{passed:false});
      learnedMemories.push(memoryAt.get(partIndex));add('cam','Planning memory added',{addedMemory:memoryAt.get(partIndex)});
      attempt++;code();cycle();
    }
    add('judge','Plan accepted',{passed:true});
    add('output','Part complete',{completed:true,firstPass:attempt===1,before:part.summary?.baseline_seconds,after:part.summary?.best_seconds});
  });
  return steps;
}
