#!/usr/bin/env bash
# Initialise a case folder as a NightAgent student project, in place.
# Usage: ./new_project.sh <case_dir>
#
# The human creates <case_dir> containing a QUESTION.md (start from project-template/QUESTION.md,
# written in the supervisor's voice), plus any starting data/ or code. This script adds the rest
# of project-template/ without overwriting anything already there, builds the supervisor agent
# from SUPERVISOR.md, and makes the folder its own git repository: the student's work is committed
# there, never to this harness repo (cases/ is gitignored here).
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <case_dir>" >&2
  exit 1
fi

CORE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$1/QUESTION.md" ]; then echo "Error: $1/QUESTION.md not found: write the question first" >&2; exit 1; fi
DEST="$(cd "$1" && pwd)"
if [ -e "$DEST/.git" ] || [ -e "$DEST/.claude/agents/supervisor.md" ]; then
  echo "Error: $DEST is already initialised" >&2; exit 1
fi

# Add the template skeleton around the human's files (never overwrite them).
rsync -a --ignore-existing --exclude .DS_Store "$CORE/project-template/" "$DEST/"
rm -f "$DEST/.DS_Store"

# Path from the project to the core protocols, used by CLAUDE.md @imports.
REL="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$CORE" "$DEST")"
sed -i '' "s|{{CORE}}|$REL|g" "$DEST/CLAUDE.md"

# Build the supervisor subagent: frontmatter + SUPERVISOR.md (protocol and private persona).
mkdir -p "$DEST/.claude/agents"
{
  cat <<'MD'
---
name: supervisor
description: The research supervisor for this project. Call it only during supervision meetings (see MEETING.md) to present results and receive feedback, clarification and agreement on actions.
tools: Read, Grep, Glob
---

MD
  cat "$CORE/SUPERVISOR.md"
} > "$DEST/.claude/agents/supervisor.md"

# Hide the persona from the student: deny reads of the agent file and of SUPERVISOR.md.
python3 - "$DEST/.claude/settings.json" "$CORE/SUPERVISOR.md" <<'PY'
import json, sys
p, sup = sys.argv[1], sys.argv[2]
s = json.load(open(p))
for tool in ("Read", "Edit"):
    rule = f"{tool}(/{sup})"
    if rule not in s["permissions"]["deny"]:
        s["permissions"]["deny"].append(rule)
json.dump(s, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY

# The project is its own repository.
git -C "$DEST" init -q
git -C "$DEST" add -A
git -C "$DEST" commit -q -m "Project setup"

echo "Initialised $DEST (own git repo)"
echo "Next: open Claude Code in $DEST (no worktree, auto mode) and say \"next step\" or \"run the project\"."
