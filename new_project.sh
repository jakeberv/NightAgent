#!/usr/bin/env bash
# Create a student project from a case definition.
# Usage: ./new_project.sh <case_dir> [project_dir]
#
# A case directory (see case-template/) holds QUESTION.md, supervisor-persona.md, and
# optionally starting data/ or code. The project is created at project_dir (default:
# projects/<case name>, gitignored here) as its own git repository: the student's work is
# committed there, never to this harness repo.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "Usage: $0 <case_dir> [project_dir]" >&2
  exit 1
fi

CORE="$(cd "$(dirname "$0")" && pwd)"
CASE="$(cd "$1" && pwd)"
NAME="$(basename "$CASE")"
DEST="${2:-$CORE/projects/$NAME}"

for f in QUESTION.md supervisor-persona.md; do
  if [ ! -f "$CASE/$f" ]; then echo "Error: $CASE/$f not found" >&2; exit 1; fi
done
if [ -e "$DEST" ]; then echo "Error: $DEST already exists" >&2; exit 1; fi

# Project skeleton, then the case's own files (question, data, code) on top.
mkdir -p "$(dirname "$DEST")"
cp -R "$CORE/project-template" "$DEST"
cp -R "$CASE/." "$DEST/"
DEST="$(cd "$DEST" && pwd)"
rm -f "$DEST/supervisor-persona.md" "$DEST/.DS_Store"

# Path from the project to the core protocols, used by CLAUDE.md @imports.
REL="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$CORE" "$DEST")"
sed -i '' "s|{{CORE}}|$REL|g" "$DEST/CLAUDE.md"

# Build the supervisor subagent: frontmatter + generic protocol + private persona.
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
  printf '\n## Your persona (private)\n\n'
  cat "$CASE/supervisor-persona.md"
} > "$DEST/.claude/agents/supervisor.md"

# Hide the persona from the student: deny reads of the agent file and of the case definitions.
python3 - "$DEST/.claude/settings.json" "$CORE/cases" <<'PY'
import json, sys
p, cases = sys.argv[1], sys.argv[2]
s = json.load(open(p))
for tool in ("Read", "Edit"):
    rule = f"{tool}(/{cases}/**)"
    if rule not in s["permissions"]["deny"]:
        s["permissions"]["deny"].append(rule)
json.dump(s, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY

# The project is its own repository.
git -C "$DEST" init -q
git -C "$DEST" add -A
git -C "$DEST" commit -q -m "Project setup from case $NAME"

echo "Created $DEST (own git repo)"
echo "Next: open Claude Code in $DEST (no worktree, auto mode) and say \"next step\" or \"run the project\"."
