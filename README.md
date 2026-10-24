# harness2-hermes

Scaffold for running the Harness^2 loop (arXiv:2610.14224,
google-research/harness2) on top of Hermes profiles. Harness^2 refines an
agent's harness with a contrastive Propose-Probe-Compose step, then banks
evidence-backed lessons in an improvement library. This repo ports that loop
to Hermes: the harness is a profile (config + SOUL.md + skills), a probe is a
fresh `hermes -p <profile> chat` session, and the library is a directory of
adopted harness trees with EXPERIENCE.md.

## Layout

```
base/            common execution harness H0 (source of truth, never edited in place)
  SOUL.md            system prompt + guardrail prose + always-on memory slot
  hermes.md          workspace rules (copied to .hermes.md at probe time)
  config.yaml        probe overlay, deep-merged over the active profile config
  skills/            on-demand skills with scripts
candidates/      candidate harness trees (full copies of base/ with edits)
prompts/         stage prompts adapted from the paper's Appendix H
scripts/         candidate creation, validation, profile materialization,
                 probe runs, library ingestion
runs/            per-task run directories: task.md, source/, <probe>/stdout.log, <probe>/ws/out/
library/         the improvement harness: adopted trees + EXPERIENCE.md + index
```

## Component map (paper -> Hermes)

| Component (Harness^2) | Activation | Hermes surface |
|---|---|---|
| C1 system prompt | every call | `SOUL.md` in the profile |
| C2 guardrails | every call | rules in `SOUL.md` + `approvals`/`security`/`agent` keys in config.yaml |
| C3 memory | every call | `## Memory` section of `SOUL.md` (always-on) |
| C4 tool guidance | every call | `hermes.md` (workspace `.hermes.md`) + toolset keys in config.yaml |
| C5 subagents | via task tool | `delegation:` keys in config.yaml + delegation rule in SOUL.md |
| C6 skills | via skill tool | `skills/<name>/SKILL.md` in the profile |
| C7 scripts | run via bash | `skills/<name>/scripts/` (flattened into the workspace) + top-level `scripts/` |
| C8 plugin/middleware | inside tool loop | out of scope for this scaffold (closest: MCP servers, shell hooks) |

`hermes.md` and top-level `scripts/` are workspace-level: `run_probe.sh`
copies them into each probe workspace.

## Per-task protocol

1. Task: `runs/<task>/task.md` (verbatim request) + optional `runs/<task>/source/`.
2. Reference run: `bash scripts/run_probe.sh base harness2-<task>-ref runs/<task>`
3. Propose: seed two candidates,
   `python3 scripts/new_candidate.py --task <task> --id inv` and `--id dom`;
   run two editor sessions (`prompts/editor-inv.md`, `prompts/editor-dom.md`),
   each editing its tree in place; gate with
   `python3 scripts/check_candidate.py candidates/<task>-<id>`.
4. Probe: `bash scripts/run_probe.sh candidates/<task>-inv harness2-<task>-inv runs/<task>`,
   same for dom.
5. Compose: seed `--id composed`; run the composer session (`prompts/composer.md`),
   which writes `candidates/<task>-composed` or declares KEEP_BASE.
6. Successor run: `bash scripts/run_probe.sh candidates/<task>-composed
   harness2-<task>-composed runs/<task>` (skip on KEEP_BASE; the reference's
   deliverable stands).
7. Select (k>1 only): `prompts/selector.md` over anonymized deliverables.
8. Reflect: reflector session (`prompts/reflector.md`) writes `<edits>` +
   `<experience>` (or NO_ENTRY) to `runs/<task>/reflection.md`.
9. Library: `python3 scripts/library_add.py --task <task>
   --adopted candidates/<task>-composed --experience runs/<task>/reflection.md`
   (or `--adopted KEEP_BASE --no-entry`).

## Cost per task

- k=1 parallel: 1 reference run + 2 probe runs + 1 compose session + 1 successor run.
- k=5 parallel: 5 references + 10 probes + 5 compose sessions + 5 successors.
- k sequential: 1 reference + k rounds x (2 probes + 1 compose session) + k successor runs.

Every probe is a full agent session with a wall-clock cap (default 900 s,
settable as the 4th argument; written to `agent.run_budget_seconds` in the
probe profile's config).

## Safety and isolation

- Probes run unattended: `base/config.yaml` pins `approvals.mode: smart` and
  keeps `security.redact_secrets: true`. Do not set approvals off in a probe
  profile.
- Editor, composer, selector, and reflector sessions must never see grading
  material. Keep task.md and source/ free of rubrics, answer keys, and scores
  (the paper's guard).
- Harness changes take effect only in fresh sessions (prompt caching). The
  runner always starts a new one-shot session and never edits a profile while
  a session is running.
- Probes are tagged `--source tool` so they stay out of your session lists
  (this deployment's gateway rejects custom source tags).
- Network: probe profiles inherit full web access. For benchmark-style tasks,
  accept rubric-leak risk or restrict the `web`/`browser` toolsets in the
  overlay.

## Captures

- `<probe>/stdout.log` is the stream-json trajectory; it is the probe's
  transcript for editors, composer, and reflector.
- The canonical session store is the profile's state.db; a
  `transcript.jsonl` copy is made if the profile writes one.
- Deliverables stay under `<probe>/ws/out/`.

## Quickstart

Requirements: a working Hermes install with at least one usable profile to
clone from (any of them), Python 3.9+.

```bash
git clone <this repo> && cd harness2-hermes
# The active profile's config is the base; probes clone it and overlay base/config.yaml.
bash scripts/smoke.sh        # runs the reference probe once, end-to-end
```

`smoke.sh` exiting 0 means the full chain works: profile materialization,
probe session, deliverable verification, cleanup. From there, follow the
per-task protocol above with your own task in `runs/<task>/task.md`.

## Post-update smoke test

Hermes CLI/config contracts can drift between versions. `scripts/smoke.sh`
is version-gated: it only re-runs the probe when the hermes version differs
from `runs/.last-green-version` (last green run), appends the outcome to
`runs/update-log.md`, and updates the marker on success. Wire it to any
scheduler (cron, launchd, a Hermes cron job with a version+marker monitor
script) and the loop self-tests on every Hermes update; on failure the
failing trajectory is in `runs/<task>/<probe>/stdout.log` for diagnosing the
drift.
