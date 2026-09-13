"""Read-only raw evidence inspection for the live terminal demo."""
import argparse,hashlib,json
from pathlib import Path

def artifact(path):
 path=Path(path)
 if not path.is_file():return {'source':str(path),'available':False}
 raw=path.read_bytes()
 return {'source':str(path),'available':True,'sha256':hashlib.sha256(raw).hexdigest(),'content':json.loads(raw) if path.suffix=='.json' else raw.decode()}

def inspect(directory,view,attempt=0):
 directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
 if view=='memory':
  return {'loaded':manifest['loaded_memory'],'feedback':manifest.get('feedback_memory'),'saved':artifact(directory/'saved-memory.json'),'saved_version':manifest.get('saved_memory_version')}
 if view=='summary':return {'job':manifest['id'],'status':manifest['status'],'target_sha256':manifest['target_sha256'],'measured':manifest.get('loop_evidence'),'telemetry':manifest.get('telemetry')}
 rows=manifest['attempts']
 if attempt<0 or attempt>=len(rows):raise ValueError('No completed candidate at this index.')
 row=rows[attempt];path=Path(row['path'])
 if view=='checks':return {'candidate':attempt,'checks':artifact(path/'checks.json'),'verification':row['result']}
 if view=='cam':return {'candidate':attempt,'proposal':row['proposal'],'compiled_plan':artifact(path/'plan.json')}
 response=Path(row['evidence']);request=response.with_name(response.name.replace('.response.json','.request.json'))
 return {'candidate':attempt,'developer_instructions':artifact(request.with_suffix('.instructions.txt')),'execution':artifact(request.with_suffix('.execution.json')),'request':artifact(request),'response':artifact(response),'note':'Unavailable historical instruction files are not reconstructed or represented as recorded evidence.'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('job');p.add_argument('view',choices=['summary','prompt','cam','checks','memory']);p.add_argument('--attempt',type=int,default=0);p.add_argument('--workspace',type=Path,default=Path(__file__).resolve().parents[1]/'workspace-live');a=p.parse_args()
 if not a.job.isalnum():p.error('Job id must be alphanumeric.')
 try:print(json.dumps(inspect(a.workspace/'runs'/a.job,a.view,a.attempt),indent=2))
 except (ValueError,KeyError,OSError) as e:p.exit(1,str(e)+'\n')
if __name__=='__main__':main()
