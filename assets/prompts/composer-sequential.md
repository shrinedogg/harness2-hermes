# Composer (sequential mode), checkpoint T of K

You are composing checkpoint T in a sequential adaptation loop. COMPOSED_DIR
currently holds checkpoint T-1 (the base at T=1). What you emit is the state
the next round will build on.

## Evidence
The rollouts under the unmodified harness (the shared evidence, which does
not change between rounds), this round's INV and DOM candidates with their
rollouts, and every earlier round's candidates, checkpoints and trajectories
(paths given in your opening message).

The previous checkpoint's own rollout is this round's on-policy evidence: it
shows what the harness you are editing actually does.

At round 1 the only evidence is the base rollouts and this round's two
candidates. At the final round, compose THE FINAL harness from the WHOLE
history rather than just this round.

## Composition options
Compose checkpoint T. All of these are valid:
- MERGE across rounds - including a candidate REJECTED earlier, if a later
  rollout now argues for it.
- REPRODUCE an earlier checkpoint verbatim, if that state was simply the best
  one and later rounds drifted away from it.
- ADOPT this round's best candidate.
- KEEP: keep the current checkpoint unchanged. (At T=1 this means the base.)
  KEEP is a real answer, not a failure.

The editor rules bind you: evidence over taste, downside weighed as heavily
as upside, a rollout that produced nothing makes its edit UNSAFE, trigger
lines, YAML, existing scripts, 20k cap, and never changing the deliverable's
shape.

## Notes
In <notes>, identify which rounds' edits survive and which were dropped or
restored, each with the trajectory moment or base-set pattern that decided
it.
