import pytest

from study.events import read_events


@pytest.mark.parametrize("tail", ['{"type": broken}\n', '{"type": broken}\r\n', '\n'])
def test_reader_rejects_corrupt_complete_final_record(tmp_path, tail):
    path = tmp_path / "events.jsonl"
    path.write_text('{"type":"valid"}\n' + tail)
    with pytest.raises(ValueError, match="Corrupt"):
        read_events(path)


def test_reader_rejects_corruption_before_final_record(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"type": broken}\n{"type":"valid"}\n')
    with pytest.raises(ValueError, match="Corrupt"):
        read_events(path)


@pytest.mark.parametrize("tail", ['', '{"type":', '{"type":"unfinished'])
def test_reader_preserves_records_before_unfinished_final_append(tmp_path, tail):
    path = tmp_path / "events.jsonl"
    path.write_text('{"type":"valid"}\n' + tail)
    assert read_events(path) == [{"type": "valid"}]


def test_reader_retains_valid_unterminated_final_record(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('{"type":"valid"}')
    assert read_events(path) == [{"type": "valid"}]


@pytest.mark.parametrize('cost', [10**1000, -(10**1000)], ids=['positive_overflow', 'negative_overflow'])
def test_unrepresentable_cost_remains_unknown_without_losing_accounting(cost):
    from study.events import Accounting
    accounting = Accounting()
    accounting.add({'cost': cost, 'prompt_tokens': 1, 'completion_tokens': 1})
    assert accounting.calls == 1
    assert accounting.known_cost == 0 and not accounting.cost_complete
    assert accounting.token_usage_complete
