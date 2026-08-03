import argparse, json
from pathlib import Path
from .foundry import SolutionFoundry

def main():
    p=argparse.ArgumentParser()
    p.add_argument("concept_json")
    p.add_argument("--workspace",default="./ao_foundry_workspace")
    p.add_argument("--portfolio",action="store_true")
    args=p.parse_args()
    raw=json.loads(Path(args.concept_json).read_text())
    foundry=SolutionFoundry(args.workspace)
    result=foundry.score_portfolio(raw) if args.portfolio else foundry.operational_release(raw)
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
