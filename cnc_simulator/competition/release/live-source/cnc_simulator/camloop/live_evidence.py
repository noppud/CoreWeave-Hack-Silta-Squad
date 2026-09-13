"""Source-bounded loop evidence; never infer learning from a version counter."""
from .common import digest

def movement_identity(plan):
    return digest({k: v for k, v in plan.items() if k not in ('name', 'description')})

def attempt_history(rows):
    return [dict(strategy=r['strategy'],passed=r['result']['passed'],seconds=r['result'].get('estimated_time_seconds'),issues=r['result']['issues']) for r in rows]

def summarize(manifest):
    rows=manifest.get('attempts',[])
    passing=[r for r in rows if r['result']['passed']]
    best=manifest.get('best')
    reference=manifest.get('reference')
    baseline=reference['result']['estimated_time_seconds'] if reference and reference['result']['passed'] else None
    seconds=best['result']['estimated_time_seconds'] if best else None
    first=passing[0]['result']['estimated_time_seconds'] if passing else None
    return dict(baseline_seconds=baseline,best_seconds=seconds,
        baseline_savings_percent=100*(baseline-seconds)/baseline if baseline and seconds is not None else None,
        within_run_savings_percent=100*(first-seconds)/first if first and seconds is not None else None,
        attempts=len(rows),simulated_attempts=sum(r.get('stage')=='simulated' for r in rows),
        failures=sum(not r['result']['passed'] for r in rows),
        loaded_memory_version=manifest.get('loaded_memory_version'),
        saved_memory_version=manifest.get('saved_memory_version'),
        stop_reason=manifest.get('stop_reason'),
        claim='Baseline savings measure CAM optimization, not a causal memory benefit. Memory transfer still requires controlled evaluation.')
