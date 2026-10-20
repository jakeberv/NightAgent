"""Readable event output; the JSONL journal remains the complete source trace."""
import json
import sys


def _safe(text):
    return "".join(char if char.isprintable() or char == "\n" else " " for char in str(text))


def _text(value, verbose):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = _safe(text)
    return text if verbose or len(text) <= 500 else text[:500] + "… [full text in progress.log]"


def _usage(account):
    if not account:
        return ""
    cost_label = "USD" if account.get("cost_complete") else "known USD"
    suffix = "" if account.get("cost_complete") else " (incomplete)"
    fields = []
    for key, label in (("input_tokens", "input"), ("output_tokens", "output"),
                       ("cached_tokens", "cached"), ("reasoning_tokens", "reasoning")):
        complete = account.get(key + "_complete", account.get("token_usage_complete", False))
        fields.append(f"{label}={account.get(key, 0)}" + ("" if complete else " (incomplete)"))
    return f"{cost_label}={account.get('known_cost', 0):.6f}{suffix}; " + ", ".join(fields)


def format_event(event, *, verbose=False):
    """Format observable milestones, model text, tool activity and cumulative usage."""
    kind = event["type"]
    prefix = f"[{event['run_id']} +{event.get('elapsed_seconds', 0):7.2f}s]"
    role = event.get("role", "")
    if kind == "run_started":
        config = event["config"]
        body = (f"START {config['condition']} model={config['model']} provider={config['provider']} "
                f"allowance={config['allowance_seconds']}s trial_cap={config['trial_cap']} "
                f"USD_guard={config['dollar_cap']}")
    elif kind == "model_call_started":
        body = f"{role} model call started (attempt {event.get('attempt', 0) + 1})"
    elif kind == "model_call":
        response = event.get("response") or {}
        body = (f"{role} model call {event['status']} wall={event.get('duration_seconds', 0):.2f}s "
                "totals: " + _usage(event.get("accounting")))
        if response:
            body += (f"\n  generation={response.get('id', '?')} "
                     f"served={response.get('model', '?')} provider={response.get('provider', '?')}")
            message = response.get("message") or {}
            if message.get("content"):
                body += "\n  " + _text(message["content"], verbose)
            for call in message.get("tool_calls") or []:
                function = call.get("function") or {}
                body += f"\n  -> {function.get('name', '?')} " + _text(function.get("arguments", ""), verbose)
        if event.get("error"):
            body += f"\n  {event['error']}"
            if event.get("details"):
                body += " " + _text(event["details"], verbose)
    elif kind == "trial_started":
        body = f"trial {event['trial_id']} started: " + _text(event["config"], verbose)
    elif kind == "trial_finished":
        result = event["result"]
        body = f"trial {result['trial_id']} {result['status']}"
        score = result.get("score", result.get("validation_auc"))
        if score is not None:
            body += f" validation={score:.6f}"
        body += f" wall={result.get('duration_seconds', 0):.2f}s"
        if result.get("error"):
            body += " " + _text(result["error"], verbose)
    elif kind == "selection":
        best = event.get("best")
        if not best:
            return ""
        body = f"best: trial {best['trial_id']} validation={best.get('score', best.get('validation_auc')):.6f}"
    elif kind == "tool_call":
        body = f"{role} {event['name']}: " + _text(event.get("result"), verbose)
    elif kind == "review":
        body = f"supervisor review after trial {event['after_trial']}: " + _text(event["feedback"], verbose)
    elif kind == "reflection":
        body = "reflection: " + _text(event["reflection"], verbose)
    elif kind == "failure":
        body = "FAILURE " + _text(event["error"], verbose)
    elif kind == "run_stopped":
        summary = event["summary"]
        body = (f"STOP {summary['stop_reason']} trials={summary['trials']} "
                f"training_wall={summary['training_seconds']:.2f}s\n  " +
                _usage(summary["accounting"]))
    else:
        return ""
    return _safe(f"{prefix} {body}")


class ConsoleProgress:
    def __init__(self, *, stream=None, verbose=False):
        self.stream = sys.stderr if stream is None else stream
        self.verbose = verbose
        self.enabled = True

    def __call__(self, event):
        if not self.enabled:
            return
        text = format_event(event, verbose=self.verbose)
        if text:
            try:
                print(text, file=self.stream, flush=True)
            except OSError:
                # Losing a terminal/pipe must not invalidate saved experiments.
                self.enabled = False
