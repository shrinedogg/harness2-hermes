---
name: run
description: Run the full Harness^2 improvement loop (init, reference, propose, probe, compose, select, reflect, adopt) for one task.
---

# Harness^2 loop: run protocol

You are orchestrating one improvement round for a task. You do the judgment
stages (propose, compose, select, reflect) yourself; the `harness2_*` tools
do the machinery (probes, gating, library). Load the stage skills with
`skill_view` as you reach each stage.

## The loop (k=1, parallel mode)

1. **Init** — `harness2_init` with the verbatim task request. Guard:
   task.md and source/ must contain NO rubrics, answer keys or scores.
2. **Reference** — `harness2_probe` with `tree: "base"`, `probe_id: "ref"`.
   (k>1: ref, ref-2, ... ref-k.)
3. **Propose** — load skill `harness2:propose`. Seed two candidates
   (`harness2_seed` id `inv`, id `dom`), edit each tree in place following its
   dimension, gate each with `harness2_check`.
4. **Probe candidates** — `harness2_probe` `candidate:inv` as `probe_id: "inv"`,
   same for `dom`.
5. **Compose** — load skill `harness2:compose`. Seed `id: "composed"`
   (from `base`, or from a library entry), then compose THE final harness in
   that tree (or declare KEEP_BASE). Gate with `harness2_check`.
6. **Successor** — `harness2_probe` `candidate:composed` as
   `probe_id: "composed"`. Skip on KEEP_BASE: the reference's deliverable
   stands and the reference probe is the on-policy run.
7. **Select** (k>1 only) — load skill `harness2:select`; pick the delivered
   deliverable from the anonymized set (reference + successor).
8. **Reflect** — load skill `harness2:reflect`; write
   `runs/<task>/reflection.md` (in the plugin data root) with `<edits>` +
   `<experience>` blocks, or a single `NO_ENTRY` line.
9. **Adopt** — `harness2_adopt` with the chosen tree (or `KEEP_BASE`) and the
   reflection file (or `no_entry: true`).

Consult the library first: `harness2_library` action=list before Propose,
and show any entry that looks relevant. The library is this loop's
accumulated evidence — reuse it instead of re-deriving it.

## Cost

k=1: 1 reference + 2 candidate probes + 1 successor = 4 full agent sessions
plus your own stage work. k=5 parallel: 5 references + 10 probes + 5
successors. Every probe is budgeted (wall-clock cap, plugin setting
`probe_budget_seconds`, default 900 s).

## Orientation and resuming

`harness2_status` returns the run state and the key paths (data root, base
tree, prompts dir). Call it when starting, after failures, or to report
progress. An interrupted loop resumes at the first stage whose artifact is
missing — re-probing an existing probe dir is safe (it is rebuilt fresh).

## Safety

- Probes are isolated one-shot sessions in `harness2-*` profiles cloned from
  the active profile: they inherit model wiring and full tool access, run
  with `approvals.mode: smart`, and are wall-clock capped. Never run a probe
  profile with approvals off.
- Each probe costs a full agent session. Confirm the task is worth it before
  starting, and prefer k=1 for a first round.
- After the run is banked, offer `harness2_gc` to remove the probe profiles.
