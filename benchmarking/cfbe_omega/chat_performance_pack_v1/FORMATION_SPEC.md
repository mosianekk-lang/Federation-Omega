# Formation Specification

- Mission: `M-CFBE-CHAT-AUDIT-BUILD-20260904-V1`
- Authority: A0 research and A1 reversible local build/persistence.
- Excluded: live automation mutation, deployment, credentials, IAM, billing, external messages and hidden autonomy claims.
- Effectful path: one persistence executor after local proof.
- Promotion: local tests and semantic verification establish `TESTED`; only provider-native readback may establish `DEPLOYED` or `RUNNING`.
- Stop switch: stop on user supersession, secret exposure, contract rejection, provider mismatch or harm signal.
