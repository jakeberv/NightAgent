import pytest

from study.config import StudyConfig


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
