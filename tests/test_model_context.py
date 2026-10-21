from study.run_context import agent_project


def test_generated_pixel_feature_names_are_described_without_repeating_784_names():
    original = {'feature_names': [f'feature_{i:04d}' for i in range(784)], 'counts': {'train': 12000}}
    compact = agent_project(original)
    assert 'feature_names' not in compact
    assert compact['feature_layout'] == {'count': 784, 'naming': 'feature_{index:04d}', 'index_range': [0, 783]}
    assert len(original['feature_names']) == 784
    assert compact['counts'] == original['counts']


def test_semantically_named_features_are_retained():
    original = {'feature_names': [f'biological_measurement_{i}' for i in range(100)]}
    assert agent_project(original) == original
