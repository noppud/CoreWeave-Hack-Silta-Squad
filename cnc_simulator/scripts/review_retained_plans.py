"""Ask the timing judge to review retained passing plans after an attempt limit.

Keeps the budget-exhaustion event and original reason. Never auto-accepts a plan.
"""
import argparse
import json
import time
from pathlib import Path
from camloop.astra import Astra
from camloop.common import save


def review(workspace):
    root=Path(workspace).resolve()
    for path in sorted((root/'runs').glob('benchmark-*/manifest.json')):
        m=json.loads(path.read_text())
        if m['status']!='incomplete' or not m['best'] or not m['reason'].startswith('Operational attempt limit'):
            continue
        if m.get('final_timing_review'):continue
        best=m['best'];r=m['attempts'][best['attempt']]['result']
        assert r['passed'] is True and r['validity']=='valid'
        context=dict(objective='Minimize estimated machining seconds among passing plans',
            current_seconds=best['seconds'],time_breakdown=r['time_breakdown'],best_seconds=best['seconds'],
            verified_time_history=[a['result']['estimated_time_seconds'] for a in m['attempts'] if a.get('result') and a['result']['validity']=='valid'],
            active_guidance=m.get('final_knowledge',m['loaded_knowledge'])['guidance'],
            guidance_evaluation_available=False,attempts_remaining=0)
        decision,evidence=Astra(path.parent/'evidence').ask('supervisor',context)
        m['final_timing_review']=dict(value=decision,evidence=evidence)
        m['budget_exhaustion_reason']=m['reason']
        m['events'].append(dict(type='retained_plan_timing_review',time=time.time(),action=decision['action'],evidence=evidence))
        if decision['action']=='stop':
            m.update(status='completed',stage='completed',reason='Timing judge accepted the retained passing plan after the attempt budget',finished_at=time.time())
        save(path,m)
        print(m['job_id'],decision['action'],decision['reason'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('workspace');review(p.parse_args().workspace)
