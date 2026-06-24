# Akiflow task sizing and verification

Use this when the user asks to estimate/set task sizes or durations for Akiflow tasks.

## Pattern

1. Fetch all active open tasks with `akiflow_list_tasks(done=false, limit=10000)`.
2. Estimate durations in practical calendar blocks, usually one of: 15, 30, 45, 60, 90, 120, or 180 minutes.
3. Interpret “size” as Akiflow `duration` unless the user says otherwise.
4. Set the estimate with `akiflow_edit_task(id=<task_id>, duration=<minutes>)`.
   - The Hermes tool takes minutes.
   - The Akiflow API stores seconds; the wrapper converts minutes → seconds.
5. Re-read open tasks and verify every changed task has the expected `duration / 60` value.
6. Report concise totals: number updated, verification status, total estimated workload, and a small distribution by duration.

## Estimation heuristics

- 15m: simple bump, reply, booking/scheduling, yes/no follow-up.
- 30m: single external note, quick page/content edit, small investigation.
- 45m: review a call/writing/doc and provide feedback.
- 60m: moderate review, template/content cleanup, focused operational fix.
- 90m: multi-step cleanup or restructuring with some ambiguity.
- 120m: substantial project work requiring synthesis, coordination, implementation, or a durable artifact.
- 180m: broad setup/build work with many similar items or unknowns.

## Pitfalls

- Do not stop after estimating in chat; the user asked to “set them,” so perform writes and verify.
- Do not confuse `due_date`/planned date with `duration`; sizing should only change `duration` unless asked to schedule.
- Avoid over-explaining every estimate unless the user asks; a distribution plus notable larger blocks is usually enough.
