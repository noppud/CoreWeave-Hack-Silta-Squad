import json
from pathlib import Path
from audit_memory_chain import audit,sha

def test_audit_detects_memory_not_delivered_to_cam(tmp_path):
 def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
 work=tmp_path;d=work/'runs/job';old={'version':0,'episodes':[]};new={'version':1,'episodes':[{'part':'job'}]}
 v0=work/'memory/versions/0000.json';v1=work/'memory/versions/0001.json'
 save(v0,old);save(v1,new)
 request=d/'evidence/planner.request.json';response=d/'evidence/planner.response.json'
 save(request,{'context':{'retained_memory':old}})
 snapshot=work/'memory/source-0001.json';save(snapshot,{'id':'job'})
 save(work/'memory/commit-0001.json',{'read_back_verified':True,'sha256':sha(v1),'source_snapshot':str(snapshot),'source_manifest_sha256':sha(snapshot)})
 save(d/'manifest.json',{'id':'job','name':'Test','loaded_memory_version':0,'saved_memory_version':1,'loaded_memory':old,'loaded_memory_sha256':sha(v0),'attempts':[{'evidence':str(response)}]})
 result=audit(d,work)
 assert result['persistence_verified']
 assert result['checks']['job_saved_snapshot'] is None
 # A matching counter must not conceal missing planner memory.
 save(request,{'context':{'retained_memory':{'version':0,'episodes':[{'invented':True}]}}})
 result=audit(d,work)
 assert not result['persistence_verified']
 assert result['checks']['memory_reached_first_cam_request'] is False
 # Likewise, changing a stored version invalidates the saved-byte check.
 save(request,{'context':{'retained_memory':old}})
 save(v0,{'version':0,'episodes':[{'tampered':True}]})
 assert audit(d,work)['checks']['loaded_version_bytes'] is False
