---
name: verify-writes
description: "Use after writing or regenerating any deliverable file in out/. Reopen the file and verify required parts, internal consistency, and absence of placeholders."
---

# Verify writes

Run after producing any deliverable in out/.

1. Run the checker from the workspace root:
   `python3 scripts/check_file.py out/<file>`
2. Read the file back in full. For each part the request names, confirm it is
   present in the right place.
3. Check internal consistency: totals match their rows, figures agree between
   a summary and the table it summarizes, cross-references resolve.
4. Report what was verified and any defect found. Fix defects before declaring
   the task done.
