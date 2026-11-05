---
name: reflect
description: Harness^2 Reflect stage: diff every candidate against the base, write the edit rows and at most one durable library entry (or NO_ENTRY).
---

# Reflect stage

You are reading the complete record of one improvement round and writing what
a future task in this area needs to know. Output:
`<data_root>/runs/<task>/reflection.md` with two blocks — `<edits>` (the edit
rows) and `<experience>` (at most one durable entry) — or a single `NO_ENTRY`
line in place of the `<experience>` block.

## Inputs

- The base tree and each candidate tree (diff every candidate against the
  base; `harness2_library` action=show on related entries shows how earlier
  entries were shaped).
- The trajectories: `<data_root>/runs/<task>/<probe>/stdout.log` for every
  probe that ran (ref, inv, dom, composed as applicable).
- The selection (`runs/<task>/selection.md`, k>1) and the composed notes
  (`runs/<task>/compose-notes.md`).

## Write

1. Read the stage prompt and follow it exactly: `<prompts_dir>/reflector.md`.
2. The adopted candidate is not the only evidence: selection compared
   deliverables with the harnesses hidden. Read the trajectories, not the
   verdict.
3. Edit rows: one per changed component — component, what the edit actually
   changed, the observed difference in execution, and a verdict
   (helped / hurt / no observed effect / confounded). Cite the run and the
   trajectory point where behavior diverges.
4. At most ONE durable entry, only if the edit rows support it: a `cue:`
   (the shape of situation, not this task's facts), a `lesson:` (the operation
   on a harness, naming the component it concerns) and an `evidence:` field
   citing the edit rows. If the record shows no concrete reusable contrast,
   write `NO_ENTRY` — the edit rows are still worth writing.

## Then

`harness2_adopt` with the adopted tree (or `KEEP_BASE`) and
`experience_path: runs/<task>/reflection.md` (or `no_entry: true`).
