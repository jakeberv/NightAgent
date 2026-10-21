#!/usr/bin/env python3
"""One-command workshop evaluation. Replay uses only the Python standard library."""
import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def checksum(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_replay(path):
    envelope = json.loads(path.read_text())
    result = envelope["result"]
    if result.get("schema_version") != 1 or checksum(result) != envelope["sha256"]:
        raise ValueError("Replay checksum or schema mismatch")
    return result


def write_report(result, output, *, replay):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(
        {"result": result, "sha256": checksum(result)}, indent=2, allow_nan=False) + "\n")
    mode = "SAVED REPLAY" if replay else "FRESH RUN"
    if result["source_kind"] == "scripted":
        mode += " · SCRIPTED DECISIONS"
    verdict = "PASS" if result["passed"] else "FAIL"
    if replay:
        verdict = "RECORDED " + verdict + " — checks were not rerun"
    def text(value):
        return escape(str(value))
    def code(value):
        return "<pre>" + text(json.dumps(value, indent=2)) + "</pre>"
    def score(value):
        if value is None:
            return "unavailable"
        return f"{value:.2%}" if result["metric"] == "accuracy" else f"{value:.4f}"
    usage = result["accounting"]
    rows = "".join(f'<tr><td>{text(c["id"])}</td><td>{text(c["status"])}</td></tr>' for c in result["engineering"])
    trace = []
    for step in result["trace"]:
        trace.append(f'''<details><summary>Experiment {step['trial']} · {text(step['arguments']['model'])} · {score(step['score'])} · {text(step['status'])}</summary>
<p><strong>Decision:</strong> {text(step['summary'])}</p>
<p><strong>Hypothesis (model interpretation):</strong> {text(step['hypothesis'])}</p>
<p><strong>Prior evidence:</strong> {text(json.dumps(step['evidence']))}</p>
<p><strong>Tool request:</strong> <code>{text(step['tool'])}</code></p>{code(step['arguments'])}
<p><strong>Measured validation result:</strong> {text(json.dumps(step['metrics']))}</p>
<p><strong>Lessons in this decision's context:</strong> {text(', '.join(step['lessons_received']) or 'none yet')}</p>
<small>events.jsonl request line {step['request_line']}; result line {step['result_line']}. Artifact SHA-256: {text(step['artifact_sha256'])}</small></details>''')
    reference = result["reference"]
    latest_lessons = result["memory"]["updates"][-1]["lessons"] if result["memory"]["updates"] else []
    lesson_text = "".join(f"<p><strong>{text(lesson['id'])}:</strong> {text(lesson['summary'])}<br>"
                          f"<small>{text(lesson['scope'])}</small></p>" for lesson in latest_lessons)
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>NightAgent · Administrator evaluation</title><style>
body{{max-width:960px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui;color:#172b3a;background:#f7f9fb}}
h1,h2{{line-height:1.2}}h2{{margin-top:32px}}.badge{{font-weight:700;color:#155c62}}table{{border-collapse:collapse;width:100%;background:white}}
td,th{{padding:10px;text-align:left;border-bottom:1px solid #dce3e8}}details{{background:white;padding:16px;margin:12px 0;border:1px solid #dce3e8;border-radius:8px}}
summary{{font-weight:700;cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef3f6;padding:12px}}small{{overflow-wrap:anywhere;color:#506271}}</style>
<p class="badge">{mode}</p><h1>One researcher, seven experiments</h1><p><strong>{verdict}</strong></p>
<p>{text(result['recorded_at'])} · {text(result['model'])} · {text(result['device'])} · memory enabled</p>
<p>The researcher chooses experiments; the harness validates requests, trains classifiers, returns measurements and enforces limits.
Follow the requests and results below, then inspect the lesson delivered to a later decision.</p>
<h2>Measured outcome</h2><table><tr><th>Validation {text(result['metric'])}</th><th>Score</th><th>Effort</th></tr>
<tr><td>Fixed logistic reference</td><td>{score(reference.get('score'))}</td><td>1 fit; zero model calls</td></tr>
<tr><td>Researcher best</td><td>{score(result['best_score'])}</td><td>{len(result['trace'])} fits; {usage['calls']} model calls</td></tr></table>
<p>Search: {result['elapsed_seconds']:.1f} seconds · API cost: ${usage['known_cost']:.4f} · tokens: {usage['input_tokens']:,} input / {usage['output_tokens']:,} output · stop: {text(result['stop_reason'])}.</p>
<p>One research repeat. Unequal effort prevents a causal agent-benefit claim. Accuracy improvement is not a pass criterion. Test data was not scored.</p>
<h2>Eight engineering cases</h2><table>{rows}</table>
<p>These are deterministic acceptance cases. The seven experiments are steps within one research run, not seven independent evaluation cases.</p>
<h2>Decision → tool → result → next decision</h2><p>Expand an experiment to inspect its request, measurements and cited evidence.</p>{''.join(trace)}
<h2>Memory</h2><p>{len(result['memory']['updates'])} register update events; {result['memory']['deliveries']} later model contexts received lessons.
Delivery demonstrates context memory, not a proven benefit or a change in model weights.</p>
{lesson_text}<details><summary>Lesson citations and later delivery records</summary>{code(result['memory'])}</details>
<h2>Audit</h2><p>{len(result['audit']['errors'])} errors; {len(result['audit']['warnings'])} warnings.</p>
<details><summary>Audit details</summary>{code(result['audit'])}</details>
<p>Replay retains the original verdict and compact evidence, not model artifacts or full provider journals. Its checksum detects accidental edits; it is not a signature or a fresh artifact audit.</p>
<p>See <a href="results.json">results.json</a> for the portable record and source hashes.</p></html>'''
    (output / "report.html").write_text(html)
    print(f"{mode}: {verdict}\nReport: {output / 'report.html'}", flush=True)


def command(output, label, *args):
    print(label, flush=True)
    with (output / "console.log").open("a") as log:
        subprocess.run([sys.executable, *map(str, args)], cwd=REPO, stdout=log,
                       stderr=subprocess.STDOUT, check=True)


def live(args, output):
    sys.path.insert(0, str(REPO))
    from study.credentials import load_openrouter_env
    from study.controller import execution_config
    from study.config import StudyConfig
    from study.problem import load_problem
    from admin_demo.evidence import collect

    env_file = args.env_file or HERE / ".env"
    if env_file.exists():
        load_openrouter_env(env_file)
    elif args.env_file:
        raise ValueError("Requested env file does not exist")
    if not os.environ.get("OPENROUTER_API_KEY", "").strip():
        raise ValueError("Set OPENROUTER_API_KEY or put it in admin_demo/.env; use --replay for the saved example.")
    problem = REPO / "study" / "problems" / "fashion-mnist.yaml"
    config = json.loads((HERE / "config.json").read_text())
    config["device"] = args.device
    execution_config(StudyConfig(**config), load_problem(problem))  # Fail before spending if torch/device is unavailable.
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    command(output, "1/4 · Running eight offline engineering cases…", "-m", "study.workshop_eval",
            "--output", output / "engineering")
    data = args.data.resolve()
    if not (data / "manifest.json").exists():
        if args.data != REPO / "study-data" / "fashion-mnist":
            raise ValueError("Custom --data must be an already prepared Fashion-MNIST directory")
        command(output, "Preparing Fashion-MNIST (first run downloads the public dataset)…", "-m", "study.fashion_data",
                "--output", REPO / "study-data" / "fashion-source" / "fashion-pilot.npz",
                "--train-size", "12000", "--validation-size", "3000", "--seed", "42")
        command(output, "Freezing training and validation partitions…", "-m", "study", "prepare",
                "--problem", problem, "--output", data)
    command(output, "2/4 · Fitting the fixed logistic reference…", "-m", "study", "reference",
            "--problem", problem, "--data", data, "--seed", "42", "--timeout", "60",
            "--output", output / "reference")
    command(output, "3/4 · Running seven solo experiments with memory (up to 300 seconds; $1 API guard)…",
            "-m", "study", "run", "--config", output / "config.json", "--problem", problem,
            "--data", data, "--output", output / "runs" / "researcher_alone", "--quiet")
    print("4/4 · Auditing artifacts, citations and memory; writing the short report…", flush=True)
    result = collect(output)
    write_report(result, output, replay=False)
    return 0 if result["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", action="store_true", help="Read the bundled real-run recording; no network, dependencies or key")
    parser.add_argument("--env-file", type=Path, help="Credential file (default: admin_demo/.env or environment)")
    parser.add_argument("--data", type=Path, default=REPO / "study-data" / "fashion-mnist")
    parser.add_argument("--device", choices=("auto", "cpu", "mps"), default="auto")
    parser.add_argument("--output", type=Path, help="New output directory; defaults to admin_demo/output/<UTC timestamp>")
    args = parser.parse_args(argv)
    output = (args.output or HERE / "output" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")).resolve()
    try:
        output.mkdir(parents=True, exist_ok=False)
        if args.replay:
            result = read_replay(HERE / "saved" / "results.json")
            write_report(result, output, replay=True)
            return 0 if result["passed"] else 1
        return live(args, output)
    except (OSError, ValueError, KeyError, ImportError, subprocess.CalledProcessError) as exc:
        # Keep partial evidence; never label a failed live attempt as a passing replay.
        print(f"Evaluation failed ({type(exc).__name__}). Evidence/log: {output}\n"
              f"{exc}\nSaved fallback: ./admin_demo/run.sh --replay", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
