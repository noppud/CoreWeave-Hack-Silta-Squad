"""Observation failures must neither impersonate completion nor lose later results."""
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('live_terminal',Path(__file__).resolve().parents[1]/'competition/live_terminal.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_disconnect_then_partial_attempt_then_completion():
    result=dict(passed=True,issues=[],estimated_time_seconds=12)
    states=iter([OSError('temporary disconnect'),dict(status='simulation',manifest={'attempts':[dict(index=0,stage='compiled')]}),dict(status='completed',memory_version=1,manifest={'attempts':[dict(index=0,stage='simulated',path='actual',result=result,judge={'value':{'action':'stop'}})]})])
    def fetch():
        value=next(states)
        if isinstance(value,Exception):raise value
        return value
    output=[]
    assert module.watch('job',fetch=fetch,sleep=lambda _:None,emit=lambda s,**kw:output.append(s))==0
    text='\n'.join(output)
    assert 'Restored' in text and text.count('\nVERIFICATION\n')==1 and '"memory_saved": 1' in text

def test_persistent_disconnect_is_not_job_failure_or_completion():
    def fetch():raise OSError('offline')
    output=[]
    assert module.watch('job',fetch=fetch,sleep=lambda _:None,emit=lambda s,**kw:output.append(s),max_failures=2)==1
    text='\n'.join(output)
    assert 'execution status is unverified' in text and '\nRESULT\n' not in text
