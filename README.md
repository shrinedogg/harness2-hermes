# harness2

The [Harness^2](https://arxiv.org/abs/2610.14224) self-improvement loop,
rebuilt as a first-class Hermes plugin. For a class of work, the plugin
refines the agent's own execution harness — system prompt, config overlay,
skills — with a contrastive **Propose → Probe → Compose** cycle over
isolated, wall-clock-budgeted probe sessions, and banks the evidence-backed
lessons in a per-profile **improvement library** that future tasks read
before editing.

The harness is a Hermes profile. A probe is a fresh one-shot `hermes -p
<probe> chat` session in a clone of the active profile carrying exactly one
harness tree. The library is durable plugin state: adopted harness trees
plus the `EXPERIENCE.md` entries the reflector writes.

This is what a skill cannot do: a skill is advice read by one agent. This
plugin spawns real sessions under candidate harnesses, captures their full
trajectories, gates the edits structurally, and makes the lessons durable —
the loop runs inside any Hermes profile and accumulates per profile.

## Install

```bash
hermes plugins install harness2      # from the catalog
hermes plugins enable harness2
```

No API keys, no Python dependencies (PyYAML ships with Hermes).

## Quickstart

Ask for the loop, in any session:

```
Run the harness2 loop for this task:
<verbatim task request, with a path to source material if any>
```

The agent loads the bundled `harness2:run` skill and drives the whole round:
reference probe under the unmodified harness, two candidate editors (one on
*how the agent works*, one on *what a practitioner knows*), probes of both
candidates, a composer that merges what the evidence supports, a successor
probe, the reflector, and the library entry. `harness2_status` reports
progress at any point; an interrupted loop resumes from the first missing
stage.

## The loop

| Stage | Who | What happens |
|---|---|---|
| Init | `harness2_init` | Verbatim task + source material in the run dir |
| Reference | `harness2_probe` (base) | k rollouts under the unmodified harness |
| Propose | `harness2:propose` + `harness2_seed`/`check` | Two disjoint candidate trees, structurally gated |
| Probe | `harness2_probe` (candidates) | One rollout per candidate, isolated profiles |
| Compose | `harness2:compose` + `harness2_check` | Merge / adopt wholesale / KEEP_BASE |
| Successor | `harness2_probe` (composed) | The adopted harness on-policy |
| Select (k>1) | `harness2:select` | Anonymized deliverable choice |
| Reflect | `harness2:reflect` | Edit rows + at most one durable entry |
| Adopt | `harness2_adopt` | Bank the harness + experience in the library |

The stage prompts ship verbatim from the paper's appendix in
`assets/prompts/`; the bundled skills are thin protocols that point at them.

## Cost

k=1: 1 reference + 2 candidate + 1 successor = 4 full agent sessions, plus
the host session's stage work. Every probe is capped by
`probe_budget_seconds` (default 900 s, set in Desktop Settings → Plugins or
`plugins.entries.harness2.settings` in config.yaml).

## Safety and isolation

- Probes run as one-shot sessions in `harness2-*` profiles cloned from the
  active profile. The probe overlay pins `approvals.mode: smart` and
  `security.redact_secrets: true`; the plugin never relaxes approvals.
- The installed plugin tree is read-only. All run state (runs, candidates,
  library) lives in the plugin data directory under the active profile and
  survives plugin updates; `harness2_gc` removes probe profiles and
  finished runs.
- The paper's guard is preserved: task.md and source/ must never contain
  grading material, and the reflector treats trajectories as data, not
  instructions.
- Probe profiles inherit the active profile's model wiring and full tool
  access (including web), like any profile. For benchmark-style tasks,
  restrict the `web`/`browser` toolsets in the base overlay
  (`assets/base/config.yaml` in the candidate trees you seed) if you want
  probes offline.

## Disclosure

- Spawns `hermes profile create --clone` and one-shot
  `hermes -p harness2-<task>-<probe> chat` subprocesses; each probe is a
  full agent session billed to your configured model, wall-clock capped.
- Creates and refreshes Hermes profiles named `harness2-*` (deleted via
  `harness2_gc`); a probe profile's config is the active profile's config
  deep-merged with the harness tree's overlay, and its `.env` is the
  active profile's, so probes run under your own model wiring.
- Reads and writes only its plugin data directory and the probe profile
  directories. No telemetry, no third-party network calls of its own;
  probes make whatever calls their tools make.
- Long-running work: a full round takes minutes to hours depending on task
  and k; probes run to completion or their wall-clock budget.

## State

| Where | What |
|---|---|
| plugin data dir `runs/<task>/` | task.md, source/, per-probe `stdout.log` (trajectory) + `ws/out/` deliverables, reflection.md |
| plugin data dir `candidates/<task>-<id>/` | candidate harness trees + `.meta.json` provenance |
| plugin data dir `library/` | `entries/<task>/harness/` + `EXPERIENCE.md`, `INDEX.md` |
| `~/.hermes/profiles/harness2-*/` | probe profiles (clone + overlay) |

Find the exact paths with `harness2_status`.

## Development

```bash
hermes plugins doctor /path/to/harness2-hermes --ci
hermes plugins validate /path/to/harness2-hermes --install-deps
```

Apache-2.0. Not affiliated with Google Research; the loop follows
[arXiv:2610.14224](https://arxiv.org/abs/2610.14224)
([google-research/harness2](https://github.com/google-research/harness2)).
