import argparse,json
from .parts import prepare
from .runner import run_benchmark
from .report import report
from .sequential import run_sequential
p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run','sequential','report']);p.add_argument('--workspace',required=True);p.add_argument('--attempts',type=int,default=3);p.add_argument('--count',type=int,choices=range(1,11),default=5);a=p.parse_args()
if a.command=='prepare':result=prepare(a.workspace,count=a.count)
elif a.command=='run':result=run_benchmark(a.workspace,a.attempts)
elif a.command=='sequential':result=run_sequential(a.workspace,a.attempts)
else:result=report(a.workspace)
print(json.dumps(result,indent=2))
