from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / '.github/workflows/strategic-fuse-appsscript-read-zero-traffic.yml'
TEXT = WORKFLOW.read_text(encoding='utf-8')
LOW = TEXT.lower()

REQUIRED = [
    'workflow_dispatch:',
    'id-token: write',
    'superior-logic-deployer@sov-hybrid-suite.iam.gserviceaccount.com',
    'READ_APPS_SCRIPT_PROJECT_BOUNDED',
    '1z4wkTnk3TF3NG6T-1f5PsSl08-3SFUQw4STcYwsiPptdGSVrfSE-4r_R',
    'OPERATOR_AUDIENCE',
    'OIDC_ALLOWED_PRINCIPALS',
    '--no-traffic',
    '--tag "$TAG"',
    'gcloud auth print-identity-token',
    '--include-email',
    '"action":"STATUS"',
    "'action': os.environ['REQUIRED_ACTION']",
    '--data-binary @/tmp/strategic-read/read-request.json',
    "'APPS_SCRIPT_PROJECT_BOUNDED_READ_VERIFIED'",
    "'rawSourcePersisted'",
    "'sourceReturned'",
    "'providerEffect'",
    "'mutationAttempted'",
    "'secretValuesRecorded'",
    'SERVING_TRAFFIC_CHANGED',
    'CANDIDATE_NOT_ZERO_TRAFFIC_AT_END',
]

FORBIDDEN = [
    'fo_admin_token',
    'fo-operator-admin-token',
    'gcloud secrets versions access',
    '${{ secrets.',
    '--update-env-vars',
    'run services update-traffic',
    '--to-revisions',
    '--to-tags',
    '--allow-unauthenticated',
    'allusers',
    'add-iam-policy-binding',
    'roles/run.invoker',
    'projects.updatecontent',
]


def test_required_boundaries_present():
    missing = [item for item in REQUIRED if item not in TEXT]
    assert not missing, missing


def test_forbidden_effect_routes_absent():
    bad = [item for item in FORBIDDEN if item.lower() in LOW]
    assert not bad, bad


def test_one_strategic_read_request_execution():
    assert TEXT.count('--data-binary @/tmp/strategic-read/read-request.json') == 1


def test_status_precedes_strategic_read():
    assert TEXT.index('/tmp/strategic-read/status-request.json') < TEXT.index('/tmp/strategic-read/read-request.json')


def test_no_traffic_is_proven_before_and_after_read():
    assert TEXT.index("CANDIDATE_TRAFFIC_NOT_ZERO") < TEXT.index('/tmp/strategic-read/read-request.json')
    assert TEXT.index('/tmp/strategic-read/read-request.json') < TEXT.index('CANDIDATE_NOT_ZERO_TRAFFIC_AT_END')


def test_no_raw_source_is_persisted_in_receipt():
    assert "'project_digest':read.get('projectDigest')" in TEXT
    assert "'raw_source_persisted':False" in TEXT
    assert "'source_returned':False" in TEXT
    assert "'source' in x" in TEXT
