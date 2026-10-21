import pytest
from pathlib import Path

from study.config import StudyConfig, apprentice_arm, comparison_arms


def test_default_memory_survives_run_derivation_and_explicit_opt_out():
    config = StudyConfig()
    assert config.lesson_memory is True
    assert config.for_run('frequent', 1).lesson_memory is True
    disabled = config.for_run('periodic_reflection', 1, lesson_memory=False)
    assert disabled.lesson_memory is False
    assert disabled.for_run('frequent', 2).lesson_memory is False
    assert disabled.for_run('frequent', 2, lesson_memory=True).lesson_memory is True


@pytest.mark.parametrize('comparison', ['schedules', 'supervisor_strategies'])
@pytest.mark.parametrize('memory', [True, False])
def test_other_comparisons_preserve_the_base_memory_setting(comparison, memory):
    base = StudyConfig(comparison=comparison, lesson_memory=memory)
    configs = [base.for_run(arm['condition'], 0,
        supervisor_strategy=arm['supervisor_strategy'], lesson_memory=arm.get('lesson_memory'))
        for arm in comparison_arms(base)]
    assert configs
    assert all(config.lesson_memory is memory for config in configs)


@pytest.mark.parametrize('condition', ['researcher_alone', 'frequent', 'periodic'])
def test_targeted_comparison_rejects_memory_off_main_arms(condition):
    with pytest.raises(ValueError, match='Invalid apprentice_interactions arm'):
        StudyConfig(comparison='apprentice_interactions', condition=condition, lesson_memory=False)


@pytest.mark.parametrize('condition,memory,expected', [
    ('researcher_alone', True, 'researcher_alone'),
    ('frequent', True, 'frequent'),
    ('periodic', True, 'periodic'),
    ('periodic_reflection', True, 'periodic_reflection'),
    ('periodic_reflection', False, 'periodic_reflection_no_memory'),
])
def test_targeted_arm_identity_follows_the_declared_memory_treatment(condition, memory, expected):
    config = StudyConfig(comparison='apprentice_interactions', condition=condition,
                         lesson_memory=memory)
    assert apprentice_arm(config.to_dict()) == expected


@pytest.mark.parametrize('path', sorted((Path(__file__).parents[1] / 'study').glob('*config.json')),
                         ids=lambda path: path.name)
def test_runnable_presets_enable_memory_without_changing_opt_out_support(path):
    from study.__main__ import load_config
    config = load_config(path)
    assert config.lesson_memory is True
    assert config.for_run('periodic_reflection', 0, lesson_memory=False).lesson_memory is False


@pytest.mark.parametrize("seed", [-1, 2**32, 2**32 + 1, True, 1.0, "42"])
def test_config_rejects_invalid_training_seed(seed):
    with pytest.raises(ValueError, match="training_seed"):
        StudyConfig(training_seed=seed)


@pytest.mark.parametrize("seed", [0, 2**32 - 1])
def test_config_accepts_training_seed_boundaries(seed):
    assert StudyConfig(training_seed=seed).training_seed == seed


def test_for_run_rejects_seed_overflow():
    config = StudyConfig(training_seed=2**32 - 1)
    with pytest.raises(ValueError, match="training_seed"):
        config.for_run("researcher_alone", 1)
