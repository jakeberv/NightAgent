"""Run every relationship model several times on one research question, then report the results.

Usage:
    python nightagent/experiment.py example-projects/magic                  # 4 relationships x 4 seeds
    python nightagent/experiment.py example-projects/magic --seeds 2 --relationships pastoral,directive
    python nightagent/experiment.py example-projects/magic --jobs 4         # 4 runs at a time
    python nightagent/experiment.py runs/magic-2026-10-21 --report          # only rebuild the report

The task folder holds QUESTION.md and hidden-question-metrics.md. The experiment lives in
runs/<task>-<name>/: one run folder per relationship and seed (r01, r02, ...), each starting from a
copy of QUESTION.md only. The folder names are opaque and each run's condition is recorded beside
its folder (.rNN.nightagent.json), so the agents never learn which relationship they are in. Each
run is `run.py <run folder> --all`, with its console output in logs/rNN.log.

Running the same command again resumes: finished runs are skipped and stopped ones continue where
they left off. When all runs have ended (or failed), results.md and results.csv are written: every
seed's metrics, and the mean ± std per relationship.

A "seed" here is an independent repeat: the agents' sampling is not seedable, so repeats differ
naturally, and the seed number only labels the repeat.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import shutil
import statistics
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402  (the orchestrator, for its relationships and summarise())

ROOT = run.CORE.parent  # the repository
RUNS = ROOT / "runs"
# Report columns: (header, how to read it from a run's scores and metrics). Numbers are averaged.
COLUMNS = [
    ("task metric", lambda s, m: s.get("task_metric", {}).get("value")),
    ("science /10", lambda s, m: s.get("science", {}).get("overall")),
    ("interaction /10", lambda s, m: s.get("interaction", {}).get("overall")),
    ("values learned /5", lambda s, m: s.get("interaction", {}).get("values_learned")),
    ("repeated corrections", lambda s, m: s.get("interaction", {}).get("repeated_corrections")),
    ("meetings", lambda s, m: m.get("meetings")),
    ("research weeks", lambda s, m: m.get("research_weeks")),
    ("signed off", lambda s, m: s.get("ended") == "signed_off" if s else None),
    ("student tokens (M)", lambda s, m: round(m["student_tokens"] / 1e6, 2) if m else None),
    ("project tokens (M)", lambda s, m: round(m["project_tokens"] / 1e6, 2) if m else None),
    ("project cost ($)", lambda s, m: m.get("project_cost_usd")),
    ("student hours", lambda s, m: m.get("student_hours")),
    ("project hours", lambda s, m: m.get("project_hours")),
]


def condition(folder: Path) -> dict[str, Any]:
    return json.loads(run.condition_file(folder).read_text())


def create(task: Path, name: str, relationships: list[str], seeds: int) -> Path:
    """Make runs/<task>-<name>/ with one run folder per relationship and seed (skips existing ones)."""
    metrics = task / run.HIDDEN_METRICS
    if not (task / "QUESTION.md").is_file() or not metrics.is_file():
        sys.exit(f"Error: {task} needs QUESTION.md and {run.HIDDEN_METRICS}.")
    exp = RUNS / f"{task.name}-{name}"
    exp.mkdir(parents=True, exist_ok=True)
    for f in ("QUESTION.md", run.HIDDEN_METRICS):  # the experiment's copy of the task, for provenance
        if not (exp / f).exists():
            shutil.copy2(task / f, exp / f)
    existing = {(c["relationship"], c["seed"]) for c in map(condition, folders(exp))}
    n = len(folders(exp))
    for seed in range(1, seeds + 1):
        for rel in relationships:
            if (rel, seed) in existing:
                continue
            n += 1
            folder = exp / f"r{n:02d}"
            folder.mkdir()
            shutil.copy2(exp / "QUESTION.md", folder / "QUESTION.md")
            supervisor, student = run.RELATIONSHIPS[rel]
            run.condition_file(folder).write_text(json.dumps(
                {"relationship": rel, "supervisor": supervisor, "student": student,
                 "metrics": str((exp / run.HIDDEN_METRICS).resolve()), "seed": seed}, indent=2) + "\n")
    return exp


def folders(exp: Path) -> list[Path]:
    """The experiment's run folders (those with a recorded condition), in order."""
    return sorted(p for p in exp.glob("r[0-9]*") if p.is_dir() and run.condition_file(p).exists())


async def execute(exp: Path, jobs: int, passthrough: list[str]) -> None:
    """Run every unfinished run folder with run.py --all, `jobs` at a time."""
    todo = [f for f in folders(exp) if not (f / "review" / "scores.json").exists()]
    (exp / "logs").mkdir(exist_ok=True)
    limit = asyncio.Semaphore(jobs)
    print(f"{len(todo)} of {len(folders(exp))} runs to do, {jobs} at a time. Logs: {exp / 'logs'}")

    async def one(folder: Path) -> None:
        async with limit:
            c = condition(folder)
            print(f"  start {folder.name} ({c['relationship']}, seed {c['seed']})")
            with (exp / "logs" / f"{folder.name}.log").open("a") as out:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, str(run.CORE / "run.py"), str(folder), "--all", *passthrough,
                    stdout=out, stderr=asyncio.subprocess.STDOUT)
                code = await proc.wait()
            print(f"  {'done ' if code == 0 else 'STOPPED'} {folder.name}" + ("" if code == 0 else
                  f" (exit {code}; see logs/{folder.name}.log, rerun to resume)"))

    await asyncio.gather(*(one(f) for f in todo))


def fmt(x: Any) -> str:
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "yes" if x else "no"
    return f"{x:.4g}" if isinstance(x, float) else str(x)


def report(exp: Path) -> None:
    """Write results.csv (one row per run) and results.md (per relationship: every seed, then mean ± std)."""
    rows = []
    for folder in folders(exp):
        c = condition(folder)
        scores_file, metrics_file = folder / "review" / "scores.json", folder / "review" / "metrics.json"
        scores = json.loads(scores_file.read_text()) if scores_file.exists() else {}
        metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else run.summarise(folder)
        rows.append({"run": folder.name, "relationship": c["relationship"], "seed": c["seed"],
                     "status": "reviewed" if scores else "unfinished",
                     **{h: get(scores, metrics) for h, get in COLUMNS},
                     "observations": " | ".join(scores.get("observations", []))})
    if not rows:
        sys.exit(f"No runs in {exp}.")
    with (exp / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    headers = ["run", "seed", "status"] + [h for h, _ in COLUMNS]
    lines = [f"# Results: {exp.name}", "",
             f"Task metric: see `{run.HIDDEN_METRICS}`. Scores come from each run's independent review "
             f"(`rNN/review/REVIEW.md`); tokens, cost and hours from its run log (student and supervisor, "
             f"not the reviewer). Means use reviewed runs only.", ""]
    for rel in sorted({r["relationship"] for r in rows}):
        group = [r for r in rows if r["relationship"] == rel]
        supervisor, student = run.RELATIONSHIPS.get(rel, ("?", "?"))
        lines += [f"## {rel} ({supervisor} supervisor, {student} student)", "",
                  "| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        lines += ["| " + " | ".join(fmt(r[h]) for h in headers) + " |" for r in group]
        reviewed = [r for r in group if r["status"] == "reviewed"]
        summary = []
        for h, _ in COLUMNS:
            if any(isinstance(r[h], bool) for r in reviewed):  # a yes/no column: count the yeses
                summary.append(f"{sum(r[h] is True for r in reviewed)}/{len(reviewed)}")
                continue
            values = [float(r[h]) for r in reviewed if isinstance(r[h], (int, float))]
            summary.append("–" if not values else f"{statistics.mean(values):.3g}" +
                           (f" ± {statistics.stdev(values):.2g}" if len(values) > 1 else ""))
        lines += [f"| **mean ± std** | | {len(reviewed)}/{len(group)} reviewed | " + " | ".join(summary) + " |", ""]
    (exp / "results.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {exp / 'results.md'} and {exp / 'results.csv'}.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="task folder (QUESTION.md + hidden metric), or an experiment with --report")
    ap.add_argument("--name", default=date.today().isoformat(), help="experiment name (default: today's date)")
    ap.add_argument("--relationships", default="all", help=f"comma-separated subset of {','.join(run.RELATIONSHIPS)}")
    ap.add_argument("--seeds", type=int, default=4, help="independent repeats per relationship")
    ap.add_argument("--jobs", type=int, default=1, help="runs at a time (watch your rate limits)")
    ap.add_argument("--report", action="store_true", help="only rebuild the report of an existing experiment")
    args, passthrough = ap.parse_known_args()  # anything else (--provider, --model, --dry-run, ...) goes to run.py

    if args.report:
        report(args.folder.resolve())
        return
    rels = list(run.RELATIONSHIPS) if args.relationships == "all" else args.relationships.split(",")
    unknown = [r for r in rels if r not in run.RELATIONSHIPS]
    if unknown:
        sys.exit(f"Error: unknown relationship(s) {', '.join(unknown)}; choose from {', '.join(run.RELATIONSHIPS)}.")
    exp = create(args.folder.resolve(), args.name, rels, args.seeds)
    asyncio.run(execute(exp, args.jobs, passthrough))
    report(exp)


if __name__ == "__main__":
    main()
