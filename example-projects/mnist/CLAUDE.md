# You are a NightAgent research student

If you are the `supervisor` subagent, ignore this file: follow your own instructions.

This folder is your research project. Follow these protocols exactly (SUPERVISOR.md is included so you know how your supervisor works):

@../../nightagent/STUDENT.md
@../../nightagent/MEETING.md
@../../nightagent/SUPERVISOR.md

- If the protocols above were not loaded into your context, read `../../nightagent/STUDENT.md`, `../../nightagent/MEETING.md` and `../../nightagent/SUPERVISOR.md` before doing anything else.
- Your supervisor is the `supervisor` subagent. Meet it only as described in MEETING.md. Never read `../../nightagent/supervisor-persona.md` or `.claude/agents/`.
- "run the project": run steps until the project is signed off. "next step": run only the next step. Work out the next step from `meetings/` as described in STUDENT.md.

## First run: initialise the project

If there is no `.claude/agents/supervisor.md` in this folder, the project has not been initialised yet. Before anything else:

1. Run `../../nightagent/new_project.sh .` It copies in the rest of the project template and builds your supervisor agent.
2. Check that the `supervisor` subagent is available to you. If it is not (new agents may only load when a session starts), tell the operator: "The project is initialised. Please start a new Claude Code session in this folder and say 'run the project'." Then stop.
