---
name: compose
description: Harness^2 Compose stage: weigh reference vs candidate evidence and compose the final harness (merge, adopt wholesale, or KEEP_BASE).
---

# Compose stage

You are composing THE final harness for this task. What you emit is what gets
ADOPTED: it runs on this task (the successor probe), and if selected it enters
the library where later tasks read it. You are the last gate; merging an edit
launders it.

## Inputs

1. Reference rollout(s): `<data_root>/runs/<task>/ref/stdout.log`
   (ref-2, ... for k>1) under the unmodified harness.
2. Candidate rollouts: `<data_root>/runs/<task>/inv/stdout.log` and
   `<data_root>/runs/<task>/dom/stdout.log`, one per candidate tree.
3. The trees themselves: `<data_root>/candidates/<task>-inv`,
   `<data_root>/candidates/<task>-dom`, and the base tree (path from
   `harness2_status`). Diff candidates against the base to see exactly what
   each edit changed.

## Compose

1. Seed the composed tree: `harness2_seed` with `id: "composed"`.
2. Read the stage prompt and follow it exactly: `<prompts_dir>/composer.md`
   (parallel mode) or `<prompts_dir>/composer-sequential.md` (sequential
   rounds; the composed tree carries the previous checkpoint at T>1).
3. Compose in place at `<data_root>/candidates/<task>-composed`:
   MERGE the edits that earn their place, ADOPT ONE WHOLESALE, or
   KEEP_BASE. Every decision needs the trajectory moment or base-set pattern
   that decided it — write the notes block in the shape the prompt demands,
   and keep it for the reflector (save it as
   `<data_root>/runs/<task>/compose-notes.md`).
4. Gate: `harness2_check` task=<task> id=composed until clean.

## Contract

- KEEP_BASE: leave the seeded tree byte-identical, report it, and skip the
  successor probe (the reference's deliverable stands).
- Otherwise: the successor probe runs on `candidate:composed` with
  `probe_id: "composed"`.
