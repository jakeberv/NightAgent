"""Small evidence contracts and run-local memory; these never establish causality."""
from copy import deepcopy
import json
import math
import re

import jsonschema


def prose(limit=500):
    return {"type": "string", "minLength": 8, "maxLength": limit,
            "pattern": r"[.!?][\"'’\)]?$"}


EVIDENCE = {"type": "array", "maxItems": 6, "items": {
    "type": "object", "properties": {"trial_id": {"type": "integer", "minimum": 1},
        "metric": {"type": "string", "minLength": 1, "maxLength": 60},
        "split": {"const": "validation"}, "value": {"type": "number"}},
    "required": ["trial_id", "metric", "split", "value"], "additionalProperties": False}}
LESSON = {"type": "object", "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9_-]{1,40}$"},
    "status": {"enum": ["supported", "inconclusive", "superseded"]},
    "summary": prose(240), "scope": prose(240),
    "evidence": {**EVIDENCE, "minItems": 1}},
    "required": ["id", "status", "summary", "scope", "evidence"], "additionalProperties": False}


def contract_schema(role, memory=False):
    properties = {"summary": prose(240), "evidence": deepcopy(EVIDENCE)}
    if role == "researcher":
        properties.update(hypothesis=prose(), baseline_trial_id={"type": ["integer", "null"], "minimum": 1},
            change=prose(), expected_outcome=prose(),
            supervisor_response={"enum": ["followed", "modified", "rejected", "not_applicable"]},
            response_reason=prose())
    elif role == "supervisor":
        properties.update(assessment=prose(), unresolved_question=prose(),
                          recommendation=prose(), expected_outcome=prose())
    elif role == "reflection":
        properties.update(what_changed=prose(), uncertainty=prose(), next_comparison=prose())
    else:
        raise ValueError(f"Unknown contract role: {role}")
    required = list(properties)
    if memory:
        properties["lesson_updates"] = {"type": "array", "maxItems": 2, "items": deepcopy(LESSON)}
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


def evidence_errors(evidence, history):
    records = {row.get("trial_id"): row for row in history if row.get("status") == "completed"}
    errors = []
    for citation in evidence:
        trial_id, metric = citation["trial_id"], citation["metric"]
        row = records.get(trial_id, {})
        actual = (row.get("metrics") or {}).get(metric)
        if actual is None and metric == "roc_auc":
            actual = row.get("validation_auc")
        value = citation["value"]
        if (citation["split"] != "validation" or type(actual) not in (int, float)
                or type(value) not in (int, float) or not math.isfinite(actual)
                or not math.isfinite(value) or not math.isclose(value, actual, rel_tol=0, abs_tol=1e-9)):
            errors.append(f"Trial {trial_id} has no matching completed validation {metric} measurement at {value}.")
    return errors


def schema_errors(value, schema, label):
    """Bounded actionable errors shared by tool arguments and prose contracts."""
    from itertools import islice
    errors = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in islice(validator.iter_errors(value), 6):
        location = '.'.join(map(str, error.path)) or 'root'
        if error.validator == "maxLength":
            detail = f"Use at most {error.validator_value} characters (received {len(error.instance)}); rewrite as short complete sentences."
        else:
            detail = error.message[:240]
        errors.append(f"Invalid {label} at {location}: {detail}")
    return errors


def validate_contract(contract, role, history, *, has_feedback=False, memory=False):
    errors = schema_errors(contract, contract_schema(role, memory), f"{role} contract")
    if errors:
        return errors
    errors = evidence_errors(contract["evidence"], history)
    if role == "researcher":
        baseline = contract["baseline_trial_id"]
        completed = {row.get("trial_id") for row in history if row.get("status") == "completed"}
        if baseline is not None and baseline not in completed:
            errors.append("The baseline must identify a completed trial in this run.")
        if baseline is not None and baseline not in {item["trial_id"] for item in contract["evidence"]}:
            errors.append("Include a validation measurement for the baseline in evidence.")
        if has_feedback == (contract["supervisor_response"] == "not_applicable"):
            errors.append("Use not_applicable only when no supervisor feedback exists; otherwise state followed, modified or rejected.")
    for lesson in contract.get("lesson_updates", []):
        errors.extend(evidence_errors(lesson["evidence"], history))
    return errors


def parse_contract(content, *, allow_wrapper=False):
    if not isinstance(content, str):
        raise ValueError("Return a JSON object with the required contract fields.")
    content = content.strip()
    if content.startswith("```json") and content.endswith("```") and content.count('```') == 2:
        content = content[7:-3].strip()
        allow_wrapper = False
    def finite_number(raw):
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("Use finite JSON numbers for evidence measurements.")
        return number
    def finite_integer(raw):
        number = int(raw)
        if abs(number) > 10 ** 308:
            raise ValueError("JSON integers must fit the finite measurement range.")
        return number
    def reject_constant(raw):
        raise ValueError("Use finite JSON numbers, not " + raw + ".")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field: " + key)
            result[key] = value
        return result
    decoder = json.JSONDecoder(parse_float=finite_number, parse_int=finite_integer,
                               parse_constant=reject_constant, object_pairs_hook=unique_keys)
    if allow_wrapper and '```' in content:
        # One complete fence only; never pick among competing candidate objects.
        match = re.fullmatch(r'[^{}\[\]`"]*```(?:json)?\s*(.*?)\s*```[^{}\[\]`"]*', content,
                             flags=re.DOTALL | re.IGNORECASE)
        if not match:
            raise ValueError("Return one unambiguous JSON object.")
        content = match.group(1).strip()
        allow_wrapper = False  # A fenced payload must itself be valid JSON.
    try:
        value = decoder.decode(content)
    except json.JSONDecodeError:
        if not allow_wrapper or content.startswith(('{', '[')):
            raise
        start = content.find('{')
        if start < 0 or any(char in content[:start] for char in '{}[]"'):
            raise ValueError("Return one unambiguous JSON object.") from None
        value, end = decoder.raw_decode(content, start)
        if any(char in content[end:] for char in '{}[]"'):
            raise ValueError("Return one unambiguous JSON object.")
    if not isinstance(value, dict):
        raise ValueError("Return one JSON object.")
    return value


# Conservative lexical guard, not a semantic truth checker. Raw responses and
# every replacement stay in the journal; only grounded text enters feedback/UI.
OVERCLAIM = re.compile(
    r'\b(?:optimal|optimum|ceiling|plateau\w*|confirm\w*|prov(?:e|es|ed|en|ing)|'
    r'invariant|caus(?:es?|al|ality)|dominant|dominate\w*|indicat\w*)\b|'
    r'\b(?:limiting factor|minimal impact|no meaningful difference|does not affect|'
    r'are critical|is critical|reduces generalization)\b', re.IGNORECASE)


def observed_summary(evidence):
    if not evidence:
        return "No completed comparison establishes this conclusion. Further experiments are needed."
    first = evidence[0]
    if len(evidence) > 1 and all(item['metric'] == first['metric'] for item in evidence):
        values = [item['value'] for item in evidence]
        trials = ', '.join(str(item['trial_id']) for item in evidence)
        summary = (f"Cited trials {trials} recorded validation {first['metric']} "
                   f"from {min(values):.8g} to {max(values):.8g}. Broader conclusions remain untested.")
        if len(summary) <= 240:
            return summary
    return (f"Trial {first['trial_id']} recorded validation {first['metric']} {first['value']:.8g}. "
            "Broader conclusions remain untested.")


def ground_contract(contract):
    """Replace recognizable unsupported assertions without another model call.

    Invoke only after schema and citation validation. Explicit hypothesis and
    uncertainty fields remain hypotheses, not accepted observational lessons.
    """
    result = deepcopy(contract)
    changes = []

    def replace_field(record, field, path, evidence):
        original = record.get(field, '')
        if not OVERCLAIM.search(original):
            return False
        replacement = observed_summary(evidence)
        record[field] = replacement
        changes.append({'field': path, 'original': original, 'replacement': replacement,
                        'reason': 'Single-split observations do not establish this broader conclusion.'})
        return True

    for field in ('summary', 'assessment', 'what_changed', 'change', 'expected_outcome', 'response_reason'):
        replace_field(result, field, field, result.get('evidence', []))
    for index, lesson in enumerate(result.get('lesson_updates', [])):
        flagged = False
        for field in ('summary', 'scope'):
            flagged |= replace_field(lesson, field, f'lesson_updates.{index}.{field}', lesson['evidence'])
        if flagged:
            if lesson['status'] != 'superseded':
                lesson['status'] = 'inconclusive'
            lesson['scope'] = 'Only the cited configurations on this run\'s validation split were observed.'
    return result, changes


class LessonMemory:
    """Latest revisions in bounded insertion order. No cross-run reads or writes."""
    def __init__(self, limit=6):
        self.limit = limit
        self._lessons = {}

    def update(self, updates, history):
        jsonschema.validate(updates, {"type": "array", "maxItems": 2, "items": LESSON})
        errors = [error for item in updates for error in evidence_errors(item["evidence"], history)]
        if errors:
            raise ValueError(" ".join(errors))
        updates = ground_contract({'lesson_updates': updates})[0]['lesson_updates']
        for item in updates:
            self._lessons.pop(item["id"], None)
            self._lessons[item["id"]] = deepcopy(item)
        while len(self._lessons) > self.limit:
            del self._lessons[next(iter(self._lessons))]

    def snapshot(self):
        return deepcopy(list(self._lessons.values()))


def instructions(role, *, memory=False):
    schema = contract_schema(role, memory)
    prefix = ("Place the decision contract in run_analysis.intent. " if role == "researcher" else
              "When finished with tools, return only one JSON object matching this contract. ")
    return "\n" + prefix + """Use short complete sentences, not fragments or Markdown lists.
Return no preamble, code fences or extra fields. Aim for one short sentence per
prose field: summary at most 240 characters; other prose fields at most 500.
Prefer under 200 characters per field to leave room for the evidence. Lesson
summary and scope are each limited to 240 characters. These limits are characters,
not tokens. Before returning, check every field against its length limit.
Cite only completed validation measurements from this run with their exact recorded
metric and value. Evidence checks validate references and measurements, not whether
your hypothesis or interpretation is true. Use an empty evidence list before the
first completed trial. A baseline is null for an initial or independent experiment.
Recommendation uptake is your stated response, not a causal attribution.
Describe the best observed setting among the tested configurations on this split.
A small score difference alone does not establish statistical significance,
causality, underfitting, an optimum or a performance ceiling. Unmeasured model
behavior and explanations remain hypotheses. Do not generalize to untested settings.
Do not call a setting optimal, a practical ceiling or a proven plateau. Report
the measured score and the specific configurations compared. Put tentative
interpretations in hypothesis or uncertainty, never in a supported lesson.
For example: "Trial 6 scored 0.9327 on this validation split; other settings
remain untested." A weak linear baseline does not prove feature interactions.
Use max_features="all" for all input features in a random forest; numeric 1 and
1.0 are not accepted. actual_effective_config records the fitted feature count.
With ten input features, sqrt and log2 both select three candidate features;
changing other parameters at the same time does not isolate their effect.
Use fit_diagnostics when present: max_iter is a ceiling, not the number of iterations
actually trained. Early stopping before that ceiling does not establish underfitting.
The current context includes remaining_trials, remaining_seconds and observed
mean_model_call_seconds. Account for API calls and scheduled reviews/reflections;
local fit duration alone does not estimate how many experiments remain feasible.
Project metadata and recent trials are already in context; use inspect_project
or read_results only if you need information absent from that context.
""" + ("""You may provide at most two lesson_updates based on completed trials. Retain
scope, uncertainty and citations. Reuse an id to revise a lesson; use superseded
when a conclusion no longer applies. Supported means supported by cited observations,
not proven or replicated. Memory is confined to this run and its frozen split.
""" if memory else "") + ("Use the intent schema supplied by the tool." if role == "researcher" else
           "Contract: " + json.dumps(schema, separators=(",", ":")))
