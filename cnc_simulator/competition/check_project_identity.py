import os,json
import wandb
key=os.environ.pop('COREWEAVE_WANDB_API_KEY');api=wandb.Api(api_key=key)
p=api.project('coreweave-hack-silta-squad',entity='silta')
print(json.dumps({'project_id':p.id,'name':p.name}))
