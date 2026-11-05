---
name: select
description: Harness^2 Select stage (k>1): choose the delivered deliverable from anonymized candidate outputs, in the order delivery, conformance, fidelity, consistency, fitness.
---

# Select stage (k>1 only)

You choose which of N candidate answers gets delivered. The candidates are
anonymous on purpose: you do not know which harness produced which output,
and picking an output from the UNMODIFIED harness is a completely valid,
expected outcome.

## Inputs

For each probe dir under `<data_root>/runs/<task>/` (ref, ref-2, ...,
composed — or whichever probes exist):

- `<probe>/ws/out/` — the deliverable that run produced
- `<probe>/ws/task.md` — the verbatim request
- `<probe>/ws/source/` — the source material (if any)

Read the request and source once, then judge each deliverable as an artifact.

## Decide

1. Read the stage prompt and follow it exactly: `<prompts_dir>/selector.md`.
2. Judge in its fixed order: DELIVERY, CONFORMANCE, FIDELITY (check claims
   against the source — open it, verify), INTERNAL CONSISTENCY, OPERATIONAL
   FITNESS.
3. Write the decision to `<data_root>/runs/<task>/selection.md`: the chosen
   probe id, one line of rationale per candidate, and any defects you found.
   Never reveal which candidate came from which harness.

The selection does not say which EDIT worked — that is the reflector's job,
and it reads the trajectories, not your verdict.
