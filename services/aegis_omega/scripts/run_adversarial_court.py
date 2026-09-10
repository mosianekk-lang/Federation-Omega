from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from aegis_omega.adversarial.court import run_adversarial_court
receipt=run_adversarial_court()
payload=asdict(receipt)
(ROOT/'adversarial_court_receipt.json').write_text(json.dumps(payload,indent=2,sort_keys=True,default=str)+'\n')
summary={
    'scenario_pass_count':receipt.scenario_pass_count,
    'scenario_count':receipt.scenario_count,
    'threat_recall_synthetic':receipt.threat_recall,
    'benign_specificity_synthetic':receipt.benign_specificity,
    'neural_shadow_holdout_accuracy_synthetic':receipt.neural_receipt.holdout_accuracy,
    'neural_shadow_only':receipt.neural_receipt.shadow_only,
    'auto_promotion_performed':receipt.auto_promotion_performed,
    'provider_effect_performed':receipt.provider_effect_performed,
    'receipt_sha256':receipt.receipt_sha256,
}
print(json.dumps(summary,indent=2,sort_keys=True))
assert receipt.scenario_pass_count == receipt.scenario_count
assert receipt.threat_recall == 1.0
assert receipt.benign_specificity == 1.0
assert receipt.provider_effect_performed is False
assert receipt.auto_promotion_performed is False
