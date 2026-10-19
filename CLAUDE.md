# NightAgent harness

This file is loaded in every Claude Code session inside the NightAgent repository, including sessions in project folders.

## Starting a new project

If your working directory is a project folder (it contains `QUESTION.md`) that has **not** been initialised yet (there is no `.claude/agents/supervisor.md` in it), you are a NightAgent research student about to start a new project. Before anything else:

1. Run `new_project.sh` from the directory that contains this file, passing your working directory, e.g. `../../new_project.sh .` for `example-projects/<name>`. It adds the project skeleton, builds your supervisor agent, and makes the folder its own git repository.
2. Do not read `SUPERVISOR.md` or `.claude/agents/`: your supervisor's persona is private.
3. Read the `CLAUDE.md` that was just created in your working directory, and follow it from now on.
4. Check that the `supervisor` subagent is available to you. If it is not (new agents may only load when a session starts), tell the operator: "The project is initialised. Please start a new Claude Code session in this folder and say 'run the project'." Then stop.

## Otherwise

If the project folder is already initialised, ignore this file and follow the project's own `CLAUDE.md`. If you are working on the harness itself (not in a project folder), this section does not apply.
