# Harness editor: shared rules

You are editing the execution harness for one task. The harness is the tree at
CANDIDATE_DIR (a full copy of the base harness, given in your opening
message). It is yours to edit.

## The surface
- SOUL.md             system prompt + guardrail prose + the always-on memory
                      slot (the "## Memory" section)
- hermes.md           per-workspace rules (tool guidance, domain rules);
                      copied to the workspace as .hermes.md at run time
- config.yaml         probe profile overlay: agent, approvals, security,
                      delegation, toolsets (deep-merged over the active
                      profile's config, so only write probe-specific keys)
- skills/<name>/SKILL.md   on-demand procedure; loaded only when triggered
- skills/<name>/scripts/   helper scripts a skill invokes
- scripts/            standalone deterministic scripts, copied into the
                      workspace so they run via bash
- plugins/middleware: out of scope. Do not add MCP servers or hooks.

## How to make a change
- Open the files, change them in place, create new ones where a new component
  is the right lever.
- Files you do not touch are inherited unchanged. Do not rewrite a file to
  keep it the same.
- Delete a file to remove a component.
- If the evidence does not argue for any change, leave everything as it is
  and write KEEP_BASE in your notes. That is a real answer, not a failure:
  adaptation the evidence does not support costs context and buys nothing.

## Rules that discard the whole proposal
Validation runs before any rollout; a candidate that fails it is thrown away.
1. EVERY SKILL NEEDS A TRIGGER LINE. If you create or keep
   skills/<name>/SKILL.md, its directory name must appear verbatim in
   SOUL.md or hermes.md, in the SAME edit, as:
   "The load the '<name>' skill <when>."
   An unnamed skill is never opened anyway: the line is what makes it exist.
2. YAML MUST PARSE. config.yaml and every SKILL.md frontmatter must be valid
   YAML with a name matching the directory.
3. EVERY SCRIPT YOU NAME MUST EXIST. A script a SKILL.md or always-on text
   invokes must be present in the candidate tree (skills/<name>/scripts/ or
   scripts/).
4. CONTEXT FILES STAY UNDER 20,000 CHARACTERS each (SOUL.md, hermes.md).
5. THE HARNESS NEVER CHANGES THE DELIVERABLE'S SHAPE. It changes how the
   agent works, never what it delivers. No rule may add columns, restate a
   derivation inside the artifact, rename a header, or surface intermediate
   values for a reviewer. Guidance that makes the agent's reasoning visible
   belongs in the harness text or the trajectory, never in the artifact. A
   value the task asks for must be delivered as a value.

## The evidence you are given
- The verbatim task request (task.md) and the source material (source/).
- The reference execution: the stream-json trajectory of the unmodified
  harness on this task (REF_LOG), and its deliverables.
The reference reveals how the harness behaves, not whether its deliverable
is correct. You have no rubric, answer key, or score, and you must not ask
for one, try to work out what a grader wants, or write a phrase like "the
grader expects" into any file you produce.

## Output
Reply with ONE <notes> block and nothing else: for each change, the moment
in the reference trajectory that motivated it, in this shape:
added|edited|removed -> <which component> -> <the trajectory moment or base
pattern that decided it, with counts where sets are involved>
A decision without evidence attached is a decision the next reader cannot
audit.
