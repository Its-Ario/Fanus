---
type: "query"
date: "2026-09-27T21:29:10.898995+00:00"
question: "explain fanus' current plan generation loop"
contributor: "graphify"
outcome: "useful"
source_nodes: ["generate_plan()", "_build_schedule()", "_persist()"]
---

# Q: explain fanus' current plan generation loop

## Answer

Expanded from original query via graph vocab: [plan, generate, generator, params, schedule, student, optimize]. UI regenerate_plan calls get_student_params and generate_plan. generate_plan derives subjects, coefficients, weaknesses and optional locked spans. _build_schedule tries full blocks, half low-priority non-calculation subjects, then compressed 75-minute blocks and prunes some general blocks; each pass creates free slots, allocates weekly requests, and calls greedy plus local-improvement solver. First complete pass wins; otherwise fewest unplaced wins with deficit warning. Hard validation warnings do not prevent persistence. New draft is saved; UI archives prior active plan and activates the new one.

## Outcome

- Signal: useful

## Source Nodes

- generate_plan()
- _build_schedule()
- _persist()