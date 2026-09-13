from camloop.signals import verification_signals,paired_signals

def test_uncertain_failure_is_review_not_physical_defect():
 s=verification_signals(dict(passed=False,issues=[dict(code='excess_material',certainty='uncertain')]))
 assert s['requires_review'] and s['numerical_uncertainty_count']==1
 assert not s['geometry_pass'] and not s['physical_defect_confirmed']

def test_failed_reference_cannot_generate_speedup():
 assert paired_signals(dict(passed=False,estimated_time_seconds=100),dict(passed=True,estimated_time_seconds=20))['improvement_percent'] is None
 assert paired_signals(dict(passed=True,estimated_time_seconds=100),dict(passed=True,estimated_time_seconds=20))['improvement_percent']==80
