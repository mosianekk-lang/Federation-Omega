from pathlib import Path

DOCTRINE = Path('doctrine/ACME-001-v3.0.md').read_text(encoding='utf-8')

REQUIRED = [
    'Directive Compiler',
    'Complete-Directive Extraction Gate',
    'Material Notification Filter',
    'Proof-State Type System',
    'Source Authority Hierarchy',
    'Evidence Classification',
    'Large-Corpus Mode',
    'Canonical Source Resolver',
    'Display-First Control',
    'External Action Authority Matrix',
    'Cross-Chat Continuity Protocol',
    'Doctrine Layering',
    'Correction Propagation Engine',
    'Failure-Class Registry',
    'Three-Failure Route Freeze',
    'Backup and Restore Proof Standard',
    'Material-Progress Audit',
    'Unchanged-Gate Suppression',
    'Minimum-Sufficient Action',
    'Legal Route Separation',
    'Evidence-to-Element Matrix',
    'Red-Team Release Gate',
    'No Trust Transfer',
    'Capability Readiness Certificate',
    'Output Compactness Controller',
]


def test_all_modules_present():
    missing = [name for name in REQUIRED if name not in DOCTRINE]
    assert not missing, f'Missing ACME modules: {missing}'


def test_n_is_optional():
    assert '`n` is optional' in DOCTRINE
    assert 'never a heartbeat' in DOCTRINE


def test_proof_boundaries_present():
    for phrase in [
        'CI passed is not deployed',
        'Heartbeat is not semantic execution',
        'Source created is not installed',
    ]:
        assert phrase in DOCTRINE


def test_completion_priority_present():
    assert 'Mission completion outranks turn completion' in DOCTRINE


def test_failure_classes_complete():
    for number in range(1, 19):
        assert f'F{number:02d}' in DOCTRINE
