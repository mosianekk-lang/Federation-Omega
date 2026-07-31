from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib

ROOT = Path('earth2-portfolio')
STATE = ROOT / 'state'
REPORTS = ROOT / 'reports'
STATE.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

PORTFOLIO = ROOT / 'portfolio.json'
CONFIG = ROOT / 'config.json'

MATURITY = [
    'CONCEPT_DEFINED','GENOME_READY','PROTOTYPE_CANDIDATE','PROTOTYPE_BUILT',
    'BENCHMARKED','PILOT_CANDIDATE','PILOT_ACTIVE','PRODUCT_READY',
    'COMMERCIAL_CANDIDATE','OFFER_READY','SOLD','DELIVERED','RECURRING','LICENSED'
]


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def save_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')


def priority(item):
    s = item.get('scores', {})
    return round(
        0.25 * s.get('revenue_potential', 0)
        + 0.20 * s.get('urgency', 0)
        + 0.20 * s.get('defensibility', 0)
        + 0.20 * s.get('network_effect', 0)
        + 0.15 * s.get('implementation_feasibility', 0), 2
    )


def eligible(item, items_by_id):
    return all(items_by_id.get(dep, {}).get('maturity') in MATURITY[3:] for dep in item.get('dependencies', []))


def next_stage(current):
    try:
        i = MATURITY.index(current)
    except ValueError:
        return 'CONCEPT_DEFINED'
    return MATURITY[min(i + 1, len(MATURITY) - 1)]


def main():
    now = datetime.now(timezone.utc).isoformat()
    portfolio = load_json(PORTFOLIO, {'concepts': []})
    config = load_json(CONFIG, {})
    concepts = portfolio.get('concepts', [])
    items_by_id = {x['id']: x for x in concepts}

    for item in concepts:
        item['priority_score'] = priority(item)

    candidates = [
        x for x in concepts
        if x.get('maturity') not in {'LICENSED','RETIRED'} and eligible(x, items_by_id)
    ]
    ranked = sorted(candidates, key=lambda x: x['priority_score'], reverse=True)
    capacity = int(config.get('max_advances_per_cycle', 5))
    selected = ranked[:capacity]

    advances = []
    for item in selected:
        before = item.get('maturity', 'CONCEPT_DEFINED')
        after = next_stage(before)
        item['maturity'] = after
        item['last_advanced_at'] = now
        item['assigned_council'] = f"{item.get('domain','General')} Expert Genome Council"
        item['next_action'] = {
            'GENOME_READY':'extract expert methods and buyer problem',
            'PROTOTYPE_CANDIDATE':'define architecture and acceptance tests',
            'PROTOTYPE_BUILT':'build minimum runnable prototype',
            'BENCHMARKED':'run benchmark and defect repair',
            'PILOT_CANDIDATE':'prepare buyer-ready pilot',
            'PILOT_ACTIVE':'operate supervised pilot',
            'PRODUCT_READY':'package product and service passport',
            'COMMERCIAL_CANDIDATE':'validate price and buyer',
            'OFFER_READY':'prepare proposal and sales assets',
            'SOLD':'execute approved sale',
            'DELIVERED':'verify fulfilment and receipt',
            'RECURRING':'convert to subscription',
            'LICENSED':'license or federate'
        }.get(after, 'maintain and learn')
        advances.append({'id':item['id'],'name':item['name'],'from':before,'to':after,'priority':item['priority_score']})

    portfolio['concepts'] = concepts
    portfolio['updated_at'] = now
    save_json(PORTFOLIO, portfolio)

    state = {
        'timestamp': now,
        'portfolio_size': len(concepts),
        'eligible_candidates': len(candidates),
        'advanced_count': len(advances),
        'advances': advances,
        'blocked_count': len(concepts) - len(candidates),
        'state': 'PORTFOLIO_CYCLE_COMPLETE'
    }
    save_json(STATE / 'latest-cycle.json', state)
    (REPORTS / 'latest-brief.md').write_text(
        '# EARTH 2.0 Portfolio OS Brief\n\n'
        f'Updated: {now}\n\n'
        f'- Portfolio size: {len(concepts)}\n'
        f'- Eligible candidates: {len(candidates)}\n'
        f'- Advanced this cycle: {len(advances)}\n'
        + ''.join(f"- {a['id']} {a['name']}: {a['from']} → {a['to']}\n" for a in advances),
        encoding='utf-8'
    )
    receipt = hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()
    (STATE / 'latest-cycle.sha256').write_text(receipt + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
