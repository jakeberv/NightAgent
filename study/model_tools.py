"""Role-specific model tool schemas for the controlled study."""

def function_tool(name, description, parameters):
    return {"type": "function", "function": {"name": name, "description": description,
                                           "parameters": parameters}}


def tools_for(role, config, problem=None, *, require_lesson_update=False):
    if role == "reflection":
        return []
    # Both are supplied in every refreshed context; fetching them adds no evidence.
    tools = []
    if role == "researcher":
        if problem is None:
            from .science import ANALYSIS_SCHEMA
            schema = ANALYSIS_SCHEMA
        else:
            from .tasks import get_adapter
            schema = get_adapter(problem).analysis_schema
        from copy import deepcopy
        from .reasoning import request_contract_schema
        schema = deepcopy(schema)
        schema["properties"]["intent"] = request_contract_schema("researcher", config.lesson_memory,
            require_lesson_update=require_lesson_update)
        schema["required"] = [*schema["required"], "intent"]
        tools.append(function_tool("run_analysis", "Run exactly one bounded experiment.", schema))
    if role == "supervisor" and config.literature:
        for name, field, description in (
            ("literature_search", "query", "Search scholarly literature for a specific uncertainty."),
            ("literature_fetch", "url", "Read a public source and retain supporting passages."),
        ):
            tools.append(function_tool(name, description, {"type": "object", "properties": {
                field: {"type": "string", "minLength": 1, "maxLength": 2000}},
                "required": [field], "additionalProperties": False}))
    return tools
