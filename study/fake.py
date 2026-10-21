"""Deterministic offline demonstration; never an experimental LLM result."""
import json
from copy import deepcopy


def bounded_options(adapter, limit=4):
    """Distinct valid settings for offline profile smoke checks, never a search policy."""
    reference = adapter.reference_config
    options = [deepcopy(reference)]
    for name, schema in adapter.parameters[reference['model']].items():
        choices = schema.get('enum', [])
        if schema.get('type') in ('integer', 'number'):
            low, high = schema['minimum'], schema['maximum']
            choices = [low + (high-low)*fraction for fraction in (0, .25, .5, 1)]
            if schema['type'] == 'integer':
                choices = [int(value) for value in choices]
        for value in choices:
            candidate = deepcopy(reference)
            candidate['params'][name] = value
            try:
                adapter.validate_config(candidate)
            except ValueError:
                continue
            if candidate not in options:
                options.append(candidate)
            if len(options) >= limit:
                return options
    return options


def scripted_candidate(context):
    """Choose a deterministic, bounded offline fixture; never used by live agents."""
    from .science import ANALYSIS_SCHEMA
    schema = context.get('permitted_experiments') or ANALYSIS_SCHEMA
    model = schema['properties']['model']['enum'][0]
    parameters = next(branch['then']['properties']['params']['properties']
        for branch in schema['allOf']
        if branch['if']['properties']['model']['const'] == model
        and 'params' in branch['then']['properties'])
    registry = context.get('completed_configurations', {})
    numeric = [(name, spec) for name, spec in parameters.items()
               if spec.get('type') in ('number', 'integer')]
    preprocessing = ('none' if model.startswith('torch_') else
                     schema['properties']['preprocessing']['enum'][0])
    candidate = {'model': model, 'preprocessing': preprocessing, 'params': {}}
    completed = [entry for entry in registry.get('entries', []) if entry['model'] == model]
    if not numeric:
        if completed:
            raise ValueError('The bounded offline candidate fixture is exhausted.')
        return candidate
    name, spec = next((item for item in numeric if item[1]['type'] == 'number'), numeric[0])
    used = {(registry.get('parameter_bases', {}).get(model, {}) | entry['params']).get(name)
            for entry in completed}
    choices = spec.get('enum')
    if choices is None:
        low, high = spec['minimum'], spec['maximum']
        index = context.get('trials_attempted', 0) + 1
        choices = [(low + (high - low) * step / (step + 1) if spec['type'] == 'number'
                    else low + step % (high - low + 1))
                   for step in range(index, index + len(used) + 2)]
    value = next((choice for choice in choices if choice not in used), None)
    if value is None:
        raise ValueError('The bounded offline candidate fixture is exhausted.')
    candidate['params'][name] = value
    return candidate



def scripted_contract(role, context):
    """Observable, explicitly scripted reasoning for the offline demonstration."""
    metric = context.get("objective", {}).get("metric", "roc_auc")
    latest = next((row for row in reversed(context.get("recent_trials", []))
                   if row.get("status") == "completed"), None)
    if latest is None:
        latest = context.get("best") or None
    evidence = []
    if latest and metric in (latest.get("metrics") or {}):
        evidence = [{"trial_id": latest["trial_id"], "metric": metric}]
    common = {"summary": "The scripted agent is comparing model capacity using recorded validation results.",
              "evidence": evidence}
    if role == "researcher":
        has_feedback = context.get("last_supervisor_feedback") is not None or context.get("initial_framing") is not None
        common.update(hypothesis="A different model capacity may improve validation performance.",
            baseline_trial_id=latest["trial_id"] if evidence else None,
            expected_outcome="The validation score will describe the next classifier's performance.",
            supervisor_response="modified" if has_feedback else "not_applicable",
            response_reason="The offline sequence is fixed and does not adapt to advice." if has_feedback
                            else "No supervisor feedback has been recorded in this run.")
    elif role == "supervisor":
        common.update(assessment=("The recorded trials provide validation observations for comparison." if evidence else
                        "No completed trials yet distinguish these hypotheses."),
            unresolved_question="Would another model capacity improve validation performance?",
            recommendation=scripted_candidate(context),
            expected_outcome="Improved validation performance would support testing that capacity further on this split.")
        if context.get('supervisor_stage') == 'framing':
            common.update(motivation="Compare model capacity to guide the use of this run's limited budget.",
                          hypothesis="A different model capacity may improve validation performance.")
        elif context.get('supervisor_strategy', 'night_science') == 'night_science':
            common.update(motivation="Compare model capacity to guide the use of this run's limited budget.",
                alternative_explanations=["Model capacity may limit validation performance.",
                                          "Differences may reflect variability on this fixed split."],
                cross_field_connection="Bias-variance reasoning suggests a capacity test; its applicability remains untested.",
                falsifying_outcome="Unchanged or worse validation performance would weaken the capacity prediction on this split.",
                resource_check="Use one permitted fit within the remaining time and trial cap, reserving API overhead.")
    else:
        common.update(what_changed="The latest trial added a validation observation.",
            uncertainty="A single observation does not establish generalization beyond this split.",
            next_comparison=scripted_candidate(context))
    if "lessons" in context and evidence:
        common["lesson_updates"] = [{"id": "latest_observation", "status": "inconclusive",
            "summary": "The latest trial provides an observation that still needs independent replication.",
            "scope": "This observation applies only to this run and validation split.", "evidence": evidence}]
    return common


class FakeModel:
    def __init__(self, options=None):
        self.trials = 0
        self.options = options

    async def complete(self, messages, tools, *, timeout):
        role = messages[0]["content"].splitlines()[0]
        calls = []
        context = json.loads(messages[1]["content"]) if len(messages) > 1 else {}
        contract = scripted_contract(role.removeprefix("ROLE: "), context)
        options = self.options or [
            {"model": "logistic", "preprocessing": "standard", "params": {"C": 1}},
            {"model": "random_forest", "preprocessing": "none", "params": {"n_estimators": 30}},
            {"model": "histogram_gradient_boosting", "preprocessing": "none", "params": {"max_iter": 40}},
            {"model": "histogram_gradient_boosting", "preprocessing": "standard", "params": {"max_iter": 80}},
        ]
        if role != 'ROLE: researcher':
            field = 'recommendation' if role == 'ROLE: supervisor' else 'next_comparison'
            if self.trials < len(options):
                contract[field] = deepcopy(options[self.trials])
        content = json.dumps(contract)
        if role == "ROLE: researcher":
            config = {**options[self.trials % len(options)], "intent": contract}
            self.trials += 1
            calls = [{"id": f"fake-{self.trials}", "type": "function",
                      "function": {"name": "run_analysis", "arguments": json.dumps(config)}}]
        elif role == "ROLE: supervisor" and len(messages) == 2 and any(
                t["function"]["name"] == "literature_search" for t in tools):
            content = "Research question: do nonlinear tree models warrant a controlled comparison?"
            calls = [{"id": "fake-literature", "type": "function", "function": {
                "name": "literature_search", "arguments": json.dumps({"query": "controlled model comparison"})}}]
        message = {"role": "assistant", "content": content}
        if calls:
            message["tool_calls"] = calls
        return {"message": message, "usage": {"prompt_tokens": 100, "completion_tokens": 30,
            "cost": 0, "prompt_tokens_details": {"cached_tokens": 0},
            "completion_tokens_details": {"reasoning_tokens": 0}},
            "id": f"offline-{self.trials}-{len(messages)}", "model": "offline-script",
            "provider": "offline", "raw": {"offline": True}}

    async def aclose(self):
        pass


class FakeLiterature:
    async def search(self, query, *, timeout):
        return {"query": query, "offline": True, "sources": [], "note": "Offline fixture: no supporting source found."}

    async def fetch(self, url, *, timeout):
        return {"url": url, "offline": True, "text": "Offline fixture, not external evidence."}
