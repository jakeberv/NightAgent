from pathlib import Path

from study.config import StudyConfig
from study.controller import tools_for
from study.problem import load_problem
from study.provider import completion_tools


def test_fashion_tools_project_model_parameters_and_neural_preprocessing():
    problem = load_problem(Path('study/problems/fashion-mnist.yaml'))
    original = tools_for('researcher', StudyConfig(), problem)
    projected = completion_tools(original)
    schema = projected[0]['function']['parameters']
    assert not {'allOf', 'anyOf', 'oneOf'} & schema.keys()
    assert len(schema['properties']['params']['anyOf']) == 4
    assert 'torch_mlp' in schema['properties']['preprocessing']['description']
    assert 'torch_cnn' in schema['properties']['preprocessing']['description']
    assert 'none' in schema['properties']['preprocessing']['description']
    assert 'allOf' in original[0]['function']['parameters']
