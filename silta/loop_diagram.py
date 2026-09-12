"""One canonical diagram used by the live notebook and architecture documentation."""

LOOP_DIAGRAM = r"""flowchart TD
    Input[Drawing + machine + tools] --> CAD[Confirm and freeze target CAD]
    CAD --> Recall[Read applicable memory]
    Memory[(Durable memory: GCS / local)] -->|exact context + validator| Recall
    Recall -->|verified recipe + validated advice| Main[Main agent: create or repair CAM plan]
    Main --> Checks[Cheap checks + compiled path checks]
    Checks -->|pass| Sim[Machining simulation]
    Checks -->|failed measurements| Main
    Sim -->|failure evidence| Main
    Checks --> Log[Record immutable attempt and evidence]
    Sim --> Log
    Log --> Memory
    Log --> Propose[Propose bounded learning from failure]
    Propose --> Pending[(Pending lessons in durable memory)]
    Pending -->|Validate lesson action| Sandbox[W&B Sandbox: frozen regression cases]
    Sandbox -->|passed: store validation report + applicable advice| Memory
    Sandbox -->|failed or unavailable: keep pending and record status| Pending
    Sim -->|pass| Recipe[Store verified recipe with evidence]
    Recipe --> Memory
    Sim -->|pass + metrics| Supervisor[Supervisor: improve or finish when enabled]
    Supervisor -->|bounded improvement| Main
    Supervisor -->|finish| Best[Return best verified plan]
    Sim -->|first pass when supervision is off| Best
    Memory --> Inspect[marimo: inspect provenance, lessons and reuse]
    Best --> Inspect
    Inspect -->|next run reads durable memory| Recall
"""
