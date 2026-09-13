"""Deterministic diagnostic signals; numerical uncertainty never becomes a pass."""
def verification_signals(result):
 issues=result.get('issues',[])
 uncertain=[i for i in issues if i.get('certainty')=='uncertain' or i.get('code')=='uncertain']
 return dict(geometry_pass=result.get('passed') is True,requires_review=result.get('passed') is not True,
             numerical_uncertainty_count=len(uncertain),issue_codes=sorted({i.get('code','unspecified') for i in issues}),
             physical_defect_confirmed=False)

def paired_signals(reference,candidate):
 coverage=reference.get('passed') is True and candidate.get('passed') is True
 r=reference.get('estimated_time_seconds');c=candidate.get('estimated_time_seconds')
 return dict(paired_coverage=coverage,improvement_percent=100*(r-c)/r if coverage and r and c is not None else None)
