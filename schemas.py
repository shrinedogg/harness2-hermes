"""Tool schemas — what the model sees when deciding when to call harness2 tools."""

INIT = {
    "name": "harness2_init",
    "description": (
        "Start a Harness^2 improvement run for one task. Creates the run directory "
        "with the verbatim task request (task.md) and optional source material. "
        "Call this first, before any other harness2 tool, for a new task. "
        "Do not put rubrics, answer keys or scores in task_text — the loop's "
        "guardrails require the task to be free of grading material."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Task slug: lowercase [a-z0-9-], e.g. 'quarterly-report'.",
            },
            "task_text": {
                "type": "string",
                "description": "The verbatim task request the probe agents must complete.",
            },
            "source_dir": {
                "type": "string",
                "description": "Optional absolute path to a directory of input material; copied into the run.",
            },
        },
        "required": ["task", "task_text"],
    },
}

PROBE = {
    "name": "harness2_probe",
    "description": (
        "Run one probe: materialize a harness tree as an isolated Hermes profile and "
        "execute the task in a fresh, wall-clock-budgeted one-shot session, capturing "
        "the stream-json trajectory and deliverables. tree is 'base' (the unmodified "
        "harness), 'candidate:<id>' (a candidate tree) or 'library:<entry>' (a banked "
        "harness). probe_id is a short label: ref, ref-2, inv, dom, composed. This is "
        "the expensive step: each call is a full agent session. Returns the trajectory "
        "path, deliverables, duration and the probe's final reply."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task slug from harness2_init."},
            "tree": {
                "type": "string",
                "description": "'base', 'candidate:<id>' or 'library:<entry>'.",
            },
            "probe_id": {
                "type": "string",
                "description": "Short label for this probe: ref, ref-2, inv, dom, composed.",
            },
            "budget": {
                "type": "integer",
                "description": "Optional wall-clock run ceiling in seconds (overrides the plugin setting).",
            },
        },
        "required": ["task", "tree", "probe_id"],
    },
}

SEED = {
    "name": "harness2_seed",
    "description": (
        "Seed a candidate harness tree as a full copy of a source tree (default: the "
        "unmodified base; also 'library:<entry>' to build on a banked harness). "
        "The copy is then edited in place by the editor stage (skill harness2:propose) "
        "and gated with harness2_check before any probe uses it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task slug."},
            "id": {
                "type": "string",
                "description": "Candidate id: inv (how the agent works), dom (what a practitioner knows), composed, or round-<n> ids for sequential mode.",
            },
            "from": {
                "type": "string",
                "description": "Source tree: 'base' (default) or 'library:<entry>'.",
            },
            "note": {"type": "string", "description": "Optional provenance note."},
        },
        "required": ["task", "id"],
    },
}

CHECK = {
    "name": "harness2_check",
    "description": (
        "Run the mechanical validation gate on a candidate harness tree: YAML parses, "
        "skill frontmatter names match directories, every skill has a trigger line in "
        "SOUL.md or hermes.md, every named script exists, context files under 20k chars. "
        "Always gate a candidate with this before probing it. A failed gate must be "
        "fixed by editing the tree, then re-checked."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task slug."},
            "id": {"type": "string", "description": "Candidate id (inv, dom, composed, ...)."},
        },
        "required": ["task", "id"],
    },
}

ADOPT = {
    "name": "harness2_adopt",
    "description": (
        "Finish the loop for a task: bank the adopted harness in the improvement "
        "library and regenerate the index. adopted is 'KEEP_BASE' (no change was "
        "evidence-supported) or 'candidate:<id>'. Pass the reflection file produced by "
        "the reflector stage (skill harness2:reflect) as experience_path, or set "
        "no_entry=true when the reflector wrote NO_ENTRY. One library entry per task."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task slug."},
            "adopted": {
                "type": "string",
                "description": "'KEEP_BASE' or 'candidate:<id>' (the adopted tree).",
            },
            "experience_path": {
                "type": "string",
                "description": "Path to the reflection file containing the <experience> block.",
            },
            "no_entry": {
                "type": "boolean",
                "description": "Set true when the reflector produced NO_ENTRY.",
            },
        },
        "required": ["task", "adopted"],
    },
}

LIBRARY = {
    "name": "harness2_library",
    "description": (
        "Read the improvement library: list all entries (action=list) or show one "
        "entry's experience, its banked harness and its diff against the base "
        "(action=show, entry=<task slug>). Consult this at the start of the Propose "
        "stage for any task — the library is the accumulated, evidence-backed "
        "knowledge this loop produces."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "show"], "description": "list or show."},
            "entry": {"type": "string", "description": "Entry slug (required for show)."},
        },
        "required": ["action"],
    },
}

STATUS = {
    "name": "harness2_status",
    "description": (
        "Report the state of a Harness^2 run: which stage artifacts exist (task, "
        "probes with deliverables, candidates, reflection, library entry) and the key "
        "paths (data root, base tree, stage-prompt files). Use to orient at the start "
        "of a loop, resume an interrupted one, or report progress."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Task slug."},
        },
        "required": ["task"],
    },
}

GC = {
    "name": "harness2_gc",
    "description": (
        "Clean up Harness^2 state. Removes probe profiles (harness2-*; scoped to one "
        "task when task is given), and optionally deletes a finished task's run "
        "directory (drop_runs). The library is never touched. Use after a run is done "
        "and its harness has been banked, to reclaim profile clutter."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "Optional task slug to scope profile removal."},
            "drop_profiles": {
                "type": "boolean",
                "description": "Delete probe profiles (default true).",
            },
            "drop_runs": {
                "type": "boolean",
                "description": "Delete the task's run directory (implies task is required).",
            },
        },
    },
}
