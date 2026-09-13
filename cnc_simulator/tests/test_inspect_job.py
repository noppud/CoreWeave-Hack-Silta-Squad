import json
import pytest
from camloop.inspect_job import inspect

def test_historical_prompt_is_not_reconstructed(tmp_path):
 response=tmp_path/'planner.response.json';response.write_text('{"value": {}}')
 (tmp_path/'planner.request.json').write_text('{"context": {"fixed": true}}')
 (tmp_path/'manifest.json').write_text(json.dumps({'attempts':[{'evidence':str(response),'path':str(tmp_path)}]}))
 r=inspect(tmp_path,'prompt')
 assert r['developer_instructions']['available'] is False
 assert r['request']['content']['context']['fixed'] is True
 assert r['response']['available'] is True
 with pytest.raises(ValueError):inspect(tmp_path,'prompt',-1)

def test_saved_memory_is_scoped_to_job(tmp_path):
 (tmp_path/'manifest.json').write_text(json.dumps({'loaded_memory':{'version':2},'feedback_memory':{'version':2},'saved_memory_version':3}))
 r=inspect(tmp_path,'memory');assert r['saved']['available'] is False
 (tmp_path/'saved-memory.json').write_text('{"version":3}')
 r=inspect(tmp_path,'memory');assert r['saved']['content']['version']==3
 assert r['loaded']['version']==2
