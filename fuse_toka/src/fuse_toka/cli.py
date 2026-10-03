from __future__ import annotations
import argparse,json
from .app import main as gui_main
from .catalog import OFFERINGS
from .runtime import heartbeat,signed_update_state,status
def main():
    p=argparse.ArgumentParser(prog="fuse-toka"); p.add_argument("command",nargs="?",default="gui",choices=("gui","status","catalog","heartbeat","update-check")); a=p.parse_args()
    if a.command=="gui": gui_main(); return
    r=status().__dict__ if a.command=="status" else OFFERINGS if a.command=="catalog" else heartbeat() if a.command=="heartbeat" else signed_update_state(); print(json.dumps(r,indent=2,sort_keys=True,default=str))
if __name__=="__main__": main()
