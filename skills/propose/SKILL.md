---
name: propose
description: Harness^2 Propose stage: edit candidate harness trees on the inv (how the agent works) and dom (what a practitioner knows) dimensions, then gate them.
---

# Propose stage

You are the candidate editor. For each dimension, you turn the reference
rollout(s) into targeted harness edits.

## Setup

1. Read the library first: `harness2_library` action=list, and show entries
   whose cue fits this task. Banked lessons change what you edit for.
2. Read the reference trajectory(ies): `<data_root>/runs/<task>/ref/stdout.log`
   (stream-json; the tool_use/tool_result events are the probe's transcript).
   Also read `runs/<task>/task.md` and anything in `runs/<task>/source/`.
3. Seed the candidate trees: `harness2_seed` with `id: "inv"` and `id: "dom"`
   (from `base`, or from a library entry when a banked harness is the better
   starting point — note which one).

## Edit

For EACH candidate, in its own tree (`<data_root>/candidates/<task>-<id>`):

1. Read the stage prompt and follow it exactly:
   - inv: `<prompts_dir>/editor-shared.md` + `<prompts_dir>/editor-inv.md`
   - dom: `<prompts_dir>/editor-shared.md` + `<prompts_dir>/editor-dom.md`
   (paths from the `harness2_status` output).
2. Edit files in place. Files you do not touch are inherited unchanged; do not
   rewrite a file to keep it the same. The two dimensions are disjoint: inv
   owns how the agent works, dom owns what a practitioner knows. Never let an
   edit cross that boundary.
3. KEEP_BASE is a real answer for a dimension whose evidence does not argue
   for any change — leave the tree untouched and say so.

## Gate

Run `harness2_check` on each candidate. Fix every reported error in the tree
and re-check until clean. A candidate that fails the gate must never be
probed.
