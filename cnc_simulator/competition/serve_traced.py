import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['WANDB_API_KEY']=os.environ.pop('COREWEAVE_WANDB_API_KEY')
os.environ['CAMLOOP_WEAVE_PROJECT']='silta/coreweave-hack-silta-squad'
from camloop.live import main
main()
