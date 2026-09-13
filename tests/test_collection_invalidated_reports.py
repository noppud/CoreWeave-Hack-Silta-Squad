"""A collection warning preserves history without counting a machining result."""
import json

from scripts.demo import campaign_report, learning_transfer_report


def test_invalidated_collection_is_unknown_and_never_optimization(tmp_path, monkeypatch):
    (tmp_path / 'docs').mkdir()
    runs = tmp_path / 'runs'
    run = runs / 'annotated'
    run.mkdir(parents=True)
    path = run / 'manifest.json'
    manifest = {
        'job_id': 'annotated', 'status': 'incomplete', 'created_at': '2026-09-13',
        'inputs': {'drawings': [{'sha256': 'one-drawing'}]},
        'collection_warning': 'Partial regeneration; re-collect.',
        'events': [
            {'event': 'verification_completed', 'attempt': i, 'at': str(i),
             'verification': {'status': status, 'completed': True,
                              'machining_seconds': 100 / i, 'evidence': [{}]}}
            for i, status in [(1, 'failed'), (2, 'passed'), (3, 'passed')]
        ],
    }
    original = json.dumps(manifest)
    path.write_text(original)
    (runs / 'four-part-learning-summary.json').write_text(json.dumps({'parts': []}))
    (runs / 'demo-campaign.json').write_text(json.dumps({
        'status': 'stopped', 'parts': [{'manifest_path': str(path)}]}))
    report = campaign_report.report(tmp_path)
    part = report['parts'][0]
    assert part['simulation_failures'] == part['simulation_passes'] == 0
    assert part['verification_unknown'] == part['collection_invalidated'] == 3
    assert part['same_part_improvement_percent'] is None
    assert not part['completed']
    # It must not even attempt to validate/report an invalidated pass.
    monkeypatch.setattr(learning_transfer_report, 'validate_verdict',
                        lambda _: (_ for _ in ()).throw(AssertionError('invalidated verdict used')))
    transfer = learning_transfer_report.part_record('one', [path])
    assert transfer['verified_candidates'] == []
    assert transfer['same_part_optimization'] is None
    assert {v['status'] for v in transfer['all_verdicts']} == {'collection_invalidated'}
    assert [v['recorded_status'] for v in transfer['all_verdicts']] == [
        'failed', 'passed', 'passed']
    assert path.read_text() == original
