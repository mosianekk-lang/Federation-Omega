#pragma once
#include "capability.h"
namespace fuse {
enum class EventType:u32{MISSION_CREATED=1,TASK_RECEIVED,TASK_VALIDATED,NONCE_CLAIMED,IDEMPOTENCY_CLAIMED,ACTION_PREPARED,PERMIT_ISSUED,PERMIT_CONSUMED,EXECUTION_STARTED,EFFECT_RECONCILING,EFFECT_OBSERVED,RESULT_OBSERVED,RESULT_ATTESTED,TASK_PROVEN,MISSION_COMPLETE_VERIFIED,TASK_FAILED,ROLLBACK_STARTED,ROLLBACK_COMPLETED};
struct TaskEnvelope{u16 schema_version{1};Id128 mission_id{};u64 mission_version{1};Id128 task_id{};Id128 correlation_id{};u32 capability_id{};Digest256 registry_root{};Digest256 canonical_arguments_hash{};Digest256 nonce{};Digest256 idempotency_key{};u16 authority_class{};u16 privacy_class{};u16 effect_class{};u64 issued_at{};u64 expires_at{};};
struct PreparedAction{Id128 mission_id{};u64 mission_version{1};Id128 task_id{};Digest256 task_digest{};Digest256 effect_id{};Digest256 prepared_digest{};};
struct ExecutionPermit{Id128 mission_id{};u64 mission_version{1};Id128 permit_id{};Id128 task_id{};Digest256 task_digest{};Digest256 effect_id{};Digest256 prepared_digest{};bool consumed{};};
struct TaskSecurityProjection{Id128 mission_id{};u64 mission_version{};Digest256 task_digest{};Digest256 nonce{};Digest256 idempotency_key{};Digest256 effect_id{};Id128 permit_id{};bool mission_created{};bool task_received{};bool task_validated{};bool nonce_claimed{};bool idempotency_claimed{};bool action_prepared{};bool permit_issued{};bool permit_consumed{};bool execution_started{};bool effect_reconciling{};bool effect_observed{};bool result_observed{};bool result_attested{};bool task_proven{};bool mission_complete{};};
struct Runtime{std::wstring root;std::wstring state_root;std::wstring workspace_root;JournalWriter journal{};ObjectStore objects{};SigningIdentity identity{};CapabilityRegistry registry{};FileRoot workspace{};};
Status runtime_open(const std::wstring&,Runtime*);void runtime_close(Runtime*);Status task_digest(const TaskEnvelope*,Digest256*);
Status append_event(Runtime*,const Id128&,u64,EventType,ByteSpan);Status project_task(Runtime*,const Id128&,u64,const Digest256&,TaskSecurityProjection*);
Status nonce_seen(Runtime*,const Digest256&,bool*);Status nonce_claim(Runtime*,const Id128&,u64,const Digest256&,const Digest256&);
Status idempotency_seen(Runtime*,const Digest256&,bool*);Status idempotency_claim(Runtime*,const Id128&,u64,const Digest256&,const Digest256&);
Status permit_id_for(const PreparedAction*,Id128*);Status permit_consumed(Runtime*,const Id128&,bool*);Status permit_issue(Runtime*,const PreparedAction*,ExecutionPermit*);Status permit_consume(Runtime*,const ExecutionPermit*);
int run_mvs_canary(const std::wstring&);int run_mvs_crash_child(const std::wstring&);
}
