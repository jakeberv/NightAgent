#!/usr/bin/env bash
# Create a new NightAgent student project from project-template/.
# Usage: ./new_project.sh <project_dir> "<Title>" "<Overarching research question>" [persona.md]
# The supervisor agent (.claude/agents/supervisor.md) is built from SUPERVISOR.md plus the
# persona file (default: project-template/supervisor-persona.md). The student cannot read it.
set -euo pipefail

if [ $# -lt 3 ] || [ $# -gt 4 ]; then
  echo "Usage: $0 <project_dir> \"<Title>\" \"<Overarching research question>\" [persona.md]" >&2
  exit 1
fi

CORE="$(cd "$(dirname "$0")" && pwd)"
DEST="$1"; TITLE="$2"; QUESTION="$3"
PERSONA="${4:-$CORE/project-template/supervisor-persona.md}"

if [ -e "$DEST" ]; then echo "Error: $DEST already exists" >&2; exit 1; fi
if [ ! -f "$PERSONA" ]; then echo "Error: persona file $PERSONA not found" >&2; exit 1; fi
mkdir -p "$(dirname "$DEST")"
cp -R "$CORE/project-template" "$DEST"
DEST="$(cd "$DEST" && pwd)"
rm "$DEST/supervisor-persona.md"

# Path from the project to the core protocols, used by CLAUDE.md @imports.
REL="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$CORE" "$DEST")"

export REL TITLE QUESTION
for f in CLAUDE.md QUESTION.md REPORT.md; do
  python3 - "$DEST/$f" <<'PY'
import os, sys
p = sys.argv[1]
s = open(p).read()
s = s.replace("{{CORE}}", os.environ["REL"]).replace("{{TITLE}}", os.environ["TITLE"]).replace("{{QUESTION}}", os.environ["QUESTION"])
open(p, "w").write(s)
PY
done

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
  cat "$PERSONA"
} > "$DEST/.claude/agents/supervisor.md"

echo "Created $DEST"
echo "Next: fill in Context/Constraints/Schedule in $DEST/QUESTION.md, check the persona in $DEST/.claude/agents/supervisor.md,"
echo "then open Claude Code in $DEST (no worktree) and say \"run the project\" (or \"next step\")."
