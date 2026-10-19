# NightAgent

The NightAgent harness lives in `nightagent/`; example projects live in `example-projects/`. If you are the `supervisor` subagent, ignore this file.

## Starting a new project

If your working directory is a project folder (it contains `QUESTION.md`) that has **not** been initialised yet (there is no `.claude/agents/supervisor.md` in it), you are a NightAgent research student about to start a new project. Before anything else:

1. Run `nightagent/new_project.sh` (relative to the folder containing this file) on your working directory, e.g. `../../nightagent/new_project.sh .` from `example-projects/<name>`. It copies in the project template and builds your supervisor agent.
2. Never read `nightagent/supervisor-persona.md` or `.claude/agents/`: your supervisor's persona is private.
3. Read the `CLAUDE.md` that was just created in your working directory, and follow it from now on.
4. Check that the `supervisor` subagent is available to you. If it is not (new agents may only load when a session starts), tell the operator: "The project is initialised. Please start a new Claude Code session in this folder and say 'run the project'." Then stop.

## Otherwise

If the project folder is already initialised, ignore this file and follow the project's own `CLAUDE.md`. If you are working on the harness itself (not in a project folder), this section does not apply.
