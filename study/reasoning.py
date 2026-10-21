"""Small evidence contracts and run-local memory; these never establish causality."""
from copy import deepcopy
import json
import math
import re

import jsonschema


def prose(limit=500):
    return {"type": "string", "minLength": 8, "maxLength": limit,
            "pattern": r"[.!?][\"'’\)]?$"}


EVIDENCE_REFERENCES = {"type": "array", "maxItems": 6, "items": {
    "type": "object", "properties": {"trial_id": {"type": "integer", "minimum": 1},
        "metric": {"type": "string", "minLength": 1, "maxLength": 60}},
    "required": ["trial_id", "metric"], "additionalProperties": False}}
EVIDENCE = {"type": "array", "maxItems": 6, "items": {
    "type": "object", "properties": {"trial_id": {"type": "integer", "minimum": 1},
        "metric": {"type": "string", "minLength": 1, "maxLength": 60},
        "split": {"const": "validation"}, "value": {"type": "number"}},
    "required": ["trial_id", "metric", "split", "value"], "additionalProperties": False}}
LESSON = {"type": "object", "properties": {
    "id": {"type": "string", "pattern": "^[a-z0-9_-]{1,40}$"},
    "status": {"enum": ["supported", "inconclusive", "superseded"]},
    "summary": prose(240), "scope": prose(240),
    "interpretation": {"type": "object", "properties": {
        "status": {"const": "unverified"}, "summary": prose(240), "scope": prose(240)},
        "required": ["status", "summary", "scope"], "additionalProperties": False},
    "evidence": {**EVIDENCE, "minItems": 1}},
    "required": ["id", "status", "summary", "scope", "evidence"], "additionalProperties": False}


def contract_schema(role, memory=False, *, supervisor_strategy='night_science', framing=False):
    """Schema for canonical contracts stored in logs, feedback and memory."""
    properties = {"summary": prose(240), "evidence": deepcopy(EVIDENCE)}
    if role == "researcher":
        properties.update(hypothesis=prose(), baseline_trial_id={"type": ["integer", "null"], "minimum": 1},
            change=prose(), expected_outcome=prose(),
            supervisor_response={"enum": ["followed", "modified", "rejected", "not_applicable"]},
            response_reason=prose())
    elif role == "supervisor":
        if supervisor_strategy == 'night_science' and not framing:
            properties.update(motivation=prose(), alternative_explanations={
                "type": "array", "minItems": 2, "maxItems": 3, "uniqueItems": True,
                "items": prose(240)})
        properties.update(assessment=prose(), unresolved_question=prose(),
                          recommendation=prose(), expected_outcome=prose())
        if framing:
            properties.update(motivation=prose(), hypothesis=prose())
        elif supervisor_strategy == 'night_science':
            properties.update(cross_field_connection=prose(),
                falsifying_outcome=prose(), resource_check=prose())
    elif role == "reflection":
        properties.update(what_changed=prose(), uncertainty=prose(), next_comparison=prose())
    else:
        raise ValueError(f"Unknown contract role: {role}")
    required = list(properties)
    properties.update(interpretation_status={'const': 'unverified'}, comparison_scope=prose(240))
    if memory:
        properties["lesson_updates"] = {"type": "array", "maxItems": 2, "items": deepcopy(LESSON)}
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


def request_contract_schema(role, memory=False, *, supervisor_strategy='night_science', framing=False):
    """Model input contains references; measurements and interpretation labels are harness-owned."""
    schema = contract_schema(role, memory, supervisor_strategy=supervisor_strategy, framing=framing)
    schema['properties']['evidence'] = deepcopy(EVIDENCE_REFERENCES)
    for field in ('interpretation_status', 'comparison_scope'):
        del schema['properties'][field]
    if memory:
        lesson = schema['properties']['lesson_updates']['items']
        lesson['properties']['evidence'] = {**deepcopy(EVIDENCE_REFERENCES), 'minItems': 1}
        del lesson['properties']['interpretation']
    return schema


def recorded_measurement(citation, records):
    row = records.get(citation['trial_id'], {})
    return (row.get('metrics') or {}).get(citation['metric'])


def resolve_contract_evidence(contract, history):
    """Convert reference-only model requests to canonical measured evidence.

    Raises ValueError for invalid citations so the caller can request a repair.
    Other contract fields remain the role-specific validator's responsibility.
    """
    result = deepcopy(contract)
    if not isinstance(result, dict):
        raise ValueError('Return a JSON object with the required contract fields.')
    updates = result.get('lesson_updates', [])
    if not isinstance(updates, list) or any(not isinstance(item, dict) for item in updates):
        raise ValueError('lesson_updates must be an array of lesson objects.')
    records = {row.get('trial_id'): row for row in history if row.get('status') == 'completed'}
    for record in [result, *updates]:
        if 'evidence' not in record:
            continue
        evidence = record['evidence']
        errors = schema_errors(evidence, EVIDENCE_REFERENCES, 'evidence references')
        if errors:
            raise ValueError(' '.join(errors))
        for citation in evidence:
            row = records.get(citation['trial_id'])
            if row is None:
                raise ValueError(f"Trial {citation['trial_id']} is not a completed trial in this run.")
            allowed = sorted(name for name, value in (row.get('metrics') or {}).items()
                             if type(value) in (int, float) and math.isfinite(value))
            if citation['metric'] not in allowed:
                raise ValueError(f"Metric {citation['metric']!r} is not a recorded numeric metric for trial "
                                 f"{citation['trial_id']}. Allowed metrics: {', '.join(allowed) or 'none'}. "
                                 "fit_diagnostics is context, not a metric citation.")
        record['evidence'] = [{**citation, 'split': 'validation',
                               'value': recorded_measurement(citation, records)} for citation in evidence]
        errors = evidence_errors(record['evidence'], history)
        if errors:
            raise ValueError(' '.join(errors))
    return result


def evidence_errors(evidence, history):
    errors = schema_errors(evidence, EVIDENCE, 'recorded evidence')
    if errors:
        return errors
    records = {row.get("trial_id"): row for row in history if row.get("status") == "completed"}
    errors = []
    for citation in evidence:
        trial_id, metric = citation["trial_id"], citation["metric"]
        actual = recorded_measurement(citation, records)
        value = citation.get("value")
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


def validate_contract(contract, role, history, *, has_feedback=False, memory=False,
                      supervisor_strategy='night_science', framing=False):
    errors = schema_errors(contract, contract_schema(role, memory,
        supervisor_strategy=supervisor_strategy, framing=framing), f"{role} contract")
    if errors:
        return errors
    errors = evidence_errors(contract["evidence"], history)
    if (role == "supervisor" and not contract["evidence"]
            and any(row.get("status") == "completed" for row in history)):
        errors.append("Cite at least one completed validation measurement in this review.")
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
        match = re.fullmatch(r'([^{}\[\]`]*)```(?:json)?\s*(.*?)\s*```([^{}\[\]`]*)', content,
                             flags=re.DOTALL | re.IGNORECASE)
        if not match or any(re.search(r'"(?:[^"\\]|\\.)*"\s*:', text)
                            for text in (match.group(1), match.group(3))):
            raise ValueError("Return one unambiguous JSON object.")
        content = match.group(2).strip()
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
    measurements = '; '.join(f"trial {item['trial_id']} recorded {item['metric']}={item['value']:.8g}"
                             for item in evidence)
    summary = f"On validation, {measurements}. Broader conclusions remain untested."
    if len(summary) <= 240:
        return summary
    if len(evidence) > 1 and all(item['metric'] == first['metric'] for item in evidence):
        values = [item['value'] for item in evidence]
        trials = ', '.join(str(item['trial_id']) for item in evidence)
        summary = (f"Cited trials {trials} recorded validation {first['metric']} "
                   f"from {min(values):.8g} to {max(values):.8g}. Broader conclusions remain untested.")
        if len(summary) <= 240:
            return summary
    return "The cited trials recorded validation measurements. Broader conclusions remain untested."


def observed_scope(evidence, history):
    """Compare known scientific settings, preferring recorded fitted values."""
    ids = list(dict.fromkeys(item['trial_id'] for item in evidence))
    records = {row.get('trial_id'): row for row in (history or []) if row.get('status') == 'completed'}
    configs = []; unresolved = False
    excluded = {'device', 'n_jobs', 'random_state', 'architecture', 'estimator'}
    for trial_id in ids:
        row = records.get(trial_id, {})
        config = {}; params = {}
        sources = [row.get(key) for key in ('config', 'effective_config', 'actual_effective_config')]
        for source in sources:
            if isinstance(source, dict):
                config.update({key: value for key, value in source.items() if key != 'params'})
                params.update(source.get('params') or {})
        params.update(row.get('resolved_parameters') or {})
        configs.append({key: value for key, value in {**config, **params}.items() if key not in excluded})
        unresolved |= not any(isinstance(source, dict) and source for source in sources[1:])
    prefix = ('Validation trial ' if len(ids) == 1 else 'Validation trials ') + ', '.join(map(str, ids))
    fallback = "Only the cited configurations on this run's validation split were observed; parameter effects are not established."
    if not configs:
        return fallback
    if any(not isinstance(config, dict) or not config for config in configs):
        result = prefix + (' was' if len(ids) == 1 else ' were') + ' observed; configuration details are unavailable, so parameter effects are not established.'
        return result if len(result) <= 240 else fallback
    flattened = configs
    known_keys = set.intersection(*(set(config) for config in flattened))
    unknown = unresolved or known_keys != set.union(*(set(config) for config in flattened))
    keys = sorted(known_keys)
    values = {key: [json.dumps(config[key], sort_keys=True, separators=(',', ':'))
                    if key in config else 'unspecified' for config in flattened] for key in keys}
    changed = [key for key in keys if len(set(values[key])) > 1]
    if len(changed) > 1:
        caveat = ' Multiple settings changed; effects are confounded.'
    elif changed:
        caveat = ' This split alone does not establish causality.'
    else:
        caveat = ' No parameter effect was isolated.'
    if unknown:
        caveat += ' Unrecorded settings remain unknown.'
    if changed:
        details = '; '.join(key + '=' + '/'.join(values[key]) for key in changed)
        result = prefix + ' compared ' + details + '.' + caveat
        if len(result) > 240:
            result = prefix + ' differed in ' + ', '.join(changed) + '.' + caveat
    elif len(configs) > 1:
        result = prefix + (' matched on the recorded settings.' if unknown else
                           ' used matching recorded configurations.') + caveat
    else:
        details = '; '.join(key + '=' + values[key][0] for key in keys)
        result = prefix + ' used ' + details + '.' + caveat
    if len(result) > 240:
        result = prefix + (' used its recorded configuration.' if len(configs) == 1 else
                           f' compared {len(configs)} recorded configurations.') + caveat
    return result if len(result) <= 240 else fallback


def ground_contract(contract, history, *, targets=(), capacity=None):
    """Generate factual lessons and demote recognizable unsupported assertions.

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

    def assign(field, value, reason):
        if result.get(field) != value:
            changes.append({'field': field, 'original': result.get(field),
                            'replacement': value, 'reason': reason})
            result[field] = value

    # Facts are derived from cited records, not a vocabulary-based truth test.
    # Plans and predictions remain unverified, including conditional causal ideas.
    if 'summary' in result:
        result['interpretation_status'] = 'unverified'
        if result.get('evidence'):
            result['comparison_scope'] = observed_scope(result['evidence'], history)
        for field in ('assessment', 'what_changed'):
            if field in result:
                assign(field, observed_summary(result.get('evidence', [])),
                       'Factual observations are generated from cited measurements.')
        if 'assessment' in result or 'what_changed' in result:
            assign('summary', observed_summary(result.get('evidence', [])),
                   'Factual observations are generated from cited measurements.')
        else:
            # Researcher summaries describe a plan; obvious factual overclaims
            # still become observations, while hypothesis/expected fields survive.
            for field in ('summary', 'change', 'response_reason'):
                replace_field(result, field, field, result.get('evidence', []))

    # Replace target commentary sentence-by-sentence using measured state. This
    # keeps independent action sentences; originals remain in contract_grounded.
    def normalize_targets(text, field):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        normalized = []
        status_pattern = r'\b(?:(?:still need to|yet to) (?:reach|achieve|meet)|(?:has|have)(?: not)? (?:yet )?(?:been )?(?:reached|achieved|met)|(?:not yet|already) (?:reached|achieved|met))\b'
        for sentence in sentences:
            matches = []
            for target in targets:
                label = target['name'].replace('_', ' ')
                names = [target['name'], label, label.split()[-1]]
                number = re.search(r'(?<![\d.])' + re.escape(f"{target['threshold']:g}") + r'(?![\d.])', sentence)
                named = any(re.search(r'\b' + re.escape(name) + r'\b', sentence, re.I) for name in names)
                target_language = re.search(r'\b(target|threshold|goal|milestone|stretch)\b', sentence, re.I)
                if (named and target_language) or (number and re.search(r'\b(target|reach|approach|gap|headroom)\w*\b', sentence, re.I)):
                    matches.append(target['sentence'])
            factual_status = re.search(status_pattern, sentence, re.I)
            purpose = None
            if matches and field in ('recommendation', 'next_comparison', 'summary', 'change'):
                # Keep an action before a target-purpose clause, e.g. "Test X
                # to approach the stretch target." Never invent an experiment.
                purpose = re.search(r'\s+(?:(?:to|and)\s+(?:reach|approach|meet|exceed|achieve|attain)\w*|towards?)\s+(?:the\s+)?(?=(?:\d|stretch|milestone|calibration))', sentence, re.I)
                if purpose and not factual_status:
                    normalized.append(sentence[:purpose.start()].rstrip(' ,;:.') + '.')
            if matches and factual_status:
                clauses = re.split(r'\s*(?:;\s*|,\s*(?:so|and|but|therefore)\s+|\s+(?:because|since|so|therefore)\s+)\s*',
                                   sentence, flags=re.I)
                for clause in clauses:
                    if not re.search(status_pattern, clause, re.I):
                        action = clause.strip(' ,;:.')
                        if action:
                            normalized.append(action[0].upper() + action[1:] + '.')
                normalized.extend(matches)
                continue
            # A target mention alone is not a factual attainment assertion.
            # Preserve proposed actions and questions without a separable clause.
            normalized.extend(matches if matches and (purpose or factual_status) else [sentence])
        unique = list(dict.fromkeys(normalized))
        limit = 240 if field == 'summary' else 500
        chosen = []
        for sentence in unique:
            if len(' '.join(chosen + [sentence])) <= limit:
                chosen.append(sentence)
        return ' '.join(chosen) or 'The full proposal is retained in the trace; use the recorded target status.'

    for field, value in list(result.items()):
        if isinstance(value, str) and field in ('summary', 'assessment', 'what_changed',
                                                   'recommendation', 'next_comparison', 'change', 'response_reason'):
            assign(field, normalize_targets(value, field), 'Target statements use measured attainment, not agent arithmetic.')
        # Alternative explanations remain distinct unverified hypotheses.
        # Replacing their content with target status would erase the alternatives.
    if 'resource_check' in result and capacity:
        assign('resource_check', capacity['sentence'],
               'Capacity is estimated by the runner including scheduled API calls.')
    for index, lesson in enumerate(result.get('lesson_updates', [])):
        interpretation = lesson.setdefault('interpretation', {
            'status': 'unverified', 'summary': lesson['summary'], 'scope': lesson['scope']})
        if (any(OVERCLAIM.search(interpretation[field]) for field in ('summary', 'scope'))
                and lesson['status'] != 'superseded'):
            lesson['status'] = 'inconclusive'
        replacements = {'summary': observed_summary(lesson['evidence']),
                        'scope': observed_scope(lesson['evidence'], history)}
        for field, replacement in replacements.items():
            if lesson[field] != replacement:
                changes.append({'field': f'lesson_updates.{index}.{field}', 'original': lesson[field],
                                'replacement': replacement,
                                'reason': 'Lesson facts are generated from cited records; agent prose is unverified interpretation.'})
                lesson[field] = replacement
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
        updates = ground_contract({'lesson_updates': updates}, history)[0]['lesson_updates']
        for item in updates:
            self._lessons.pop(item["id"], None)
            self._lessons[item["id"]] = deepcopy(item)
        while len(self._lessons) > self.limit:
            del self._lessons[next(iter(self._lessons))]

    def snapshot(self):
        return deepcopy(list(self._lessons.values()))


def instructions(role, *, memory=False, supervisor_strategy='night_science', framing=False):
    schema = request_contract_schema(role, memory, supervisor_strategy=supervisor_strategy, framing=framing)
    prefix = ("Place the decision contract in run_analysis.intent. " if role == "researcher" else
              "When finished with tools, return only one JSON object matching this contract. ")
    return "\n" + prefix + """Use short complete sentences, not fragments or Markdown lists.
Return no preamble, code fences or extra fields. Aim for one short sentence per
prose field: summary at most 240 characters; other prose fields at most 500.
Prefer under 200 characters per field to leave room for the evidence. Lesson
summary and scope are each limited to 240 characters. These limits are characters,
not tokens. Before returning, check every field against its length limit.
Cite completed validation measurements using only trial_id and metric.
Choose metric names from evidence_metrics_by_trial for that trial. fit_diagnostics
is diagnostic context, not a metric; do not put it in an evidence citation.
Do not supply split or value; the harness adds the validation split and exact
recorded measurement. Evidence checks validate references, not whether
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
The context supplies target_status with measured reached/pending states and gaps.
Use this state; never describe a reached target as still ahead. Keep target status
out of experiment recommendations; specify the action in a separate sentence.
capacity_estimate is a runner calculation including scheduled API calls, reviews,
reflections and observed local trial/queue durations. Do not estimate trial capacity
from fit time alone or equate mean_model_call_seconds with local training time.
An unavailable estimate means timing evidence is insufficient, not unlimited time.
Plans, explanations and predictions are unverified hypotheses. Factual summary,
assessment and what_changed fields are replaced with cited observations by the
runner; comparison_scope records which settings changed and any confounding.
Project metadata and recent trials are already in context. Researchers must submit
the next experiment through run_analysis.
""" + ("""You may provide at most two lesson_updates based on completed trials. Retain
scope, uncertainty and citations. Reuse an id to revise a lesson; use superseded
when a conclusion no longer applies. The harness generates lesson summary and scope
from cited measurements and configurations. Your original lesson prose is retained
under interpretation with status unverified; it is never supported evidence.
Supported describes only the generated factual observation, not the interpretation.
Memory is confined to this run and its frozen split.
""" if memory else "") + ("Use the intent schema supplied by the tool." if role == "researcher" else
           "Contract: " + json.dumps(schema, separators=(",", ":")))
