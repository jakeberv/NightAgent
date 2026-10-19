#!/usr/bin/env bash
# Initialise a project folder for NightAgent, in place.
# Usage: nightagent/new_project.sh <project_dir>
#
# Projects live two levels below the repo root (e.g. example-projects/<name>), because the
# template's CLAUDE.md refers to ../../nightagent. The human creates <project_dir> with copies of
# project-template/QUESTION.md (filled in, in the supervisor's voice) and project-template/CLAUDE.md,
# plus any starting data/ or code. On its first run the student agent calls this script, which
# copies in the rest of project-template/ without overwriting anything,
# and builds the supervisor agent from SUPERVISOR.md (public protocol) plus supervisor-persona.md
# (private). No git: the project folder is a plain folder.
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <project_dir>" >&2
  exit 1
fi

CORE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -f "$1/QUESTION.md" ]; then echo "Error: $1/QUESTION.md not found: write the question first" >&2; exit 1; fi
DEST="$(cd "$1" && pwd)"
if [ -e "$DEST/.claude/agents/supervisor.md" ]; then
  echo "Error: $DEST is already initialised" >&2; exit 1
fi

# Copy the template around the human's files (never overwrite them).
rsync -a --ignore-existing --exclude .DS_Store --exclude .gitkeep "$CORE/project-template/" "$DEST/"

# Build the supervisor subagent: frontmatter + public protocol + private persona.
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
  printf '\n'
  cat "$CORE/supervisor-persona.md"
} > "$DEST/.claude/agents/supervisor.md"

# Hide the persona from the student: deny access to the agent file and the persona file.
python3 - "$DEST/.claude/settings.json" "$CORE/supervisor-persona.md" <<'PY'
import json, sys
p, persona = sys.argv[1], sys.argv[2]
s = json.load(open(p))
for tool in ("Read", "Edit"):
    rule = f"{tool}(/{persona})"
    if rule not in s["permissions"]["deny"]:
        s["permissions"]["deny"].append(rule)
json.dump(s, open(p, "w"), indent=2)
open(p, "a").write("\n")
PY

echo "Initialised $DEST"
