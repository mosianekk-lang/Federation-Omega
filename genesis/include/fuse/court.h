#pragma once
#include "transaction.h"
namespace fuse {
enum class CourtDomain:u16{FORMAT=1,JOURNAL,OBJECT,PATH,FILE_IO,WRITE,SECURITY,RUNTIME};enum class CourtVerdict:u16{PASS=1,FAIL=2};
struct CourtContext{std::wstring root;std::wstring self_path;};struct CourtResult{const char* test_id{};CourtDomain domain{};CourtVerdict verdict{CourtVerdict::FAIL};Status status{Status::TestFailed};Digest256 evidence{};};using CourtFn=CourtResult(*)(CourtContext*);struct CourtDescriptor{const char* id;CourtDomain domain;bool critical;CourtFn run;};
static constexpr u32 GENESIS_COURT_COUNT=48;static constexpr const char* GENESIS_COURT_REGISTRY_SHA256="70fb55e6ecc5f1ae7c181a60473637a6c59f5e7430f41471afe16d06d1bb2686";
CourtResult court_pass(const char*,CourtDomain,ByteSpan evidence={});CourtResult court_fail(const char*,CourtDomain,Status);Status verify_court_registry(Digest256*);int run_self_court(CourtContext*);int run_court_child(const std::string&,const std::wstring&);std::wstring court_fixture_root(CourtContext*,const wchar_t*);
#define DECL_IO(name) CourtResult name(CourtContext*)
DECL_IO(court_pth_001);DECL_IO(court_pth_002);DECL_IO(court_pth_003);DECL_IO(court_pth_004);DECL_IO(court_pth_005);DECL_IO(court_pth_006);
DECL_IO(court_fil_001);DECL_IO(court_fil_002);DECL_IO(court_fil_003);DECL_IO(court_fil_004);DECL_IO(court_fil_005);
DECL_IO(court_wrt_001);DECL_IO(court_wrt_002);DECL_IO(court_wrt_003);DECL_IO(court_wrt_004);DECL_IO(court_wrt_005);DECL_IO(court_wrt_006);DECL_IO(court_wrt_007);
#undef DECL_IO

// Frozen 48-court compatibility only. Production units include transaction.h directly.
inline Status nonce_claim(Runtime*r,const Digest256&task,const Digest256&nonce){static const Id128 mission=id_from_seed("GENESIS-FROZEN-SEC-MISSION");return nonce_claim(r,mission,1,task,nonce);}
inline Status frozen_court_task_marker(Runtime*r,const PreparedAction*a,EventType type){FcbWriter w{};auto st=fcb_begin(&w,(u16)(0x4000+(u32)type),0);if(st!=Status::Ok)return st;if((st=fcb_put_bytes(&w,1,FcbType::DIGEST256,{a->task_digest.bytes.data(),32}))!=Status::Ok)return st;Buffer p;if((st=fcb_finish(&w,&p,nullptr))!=Status::Ok)return st;return append_event(r,a->mission_id,a->mission_version,type,{p.data(),(u64)p.size()});}
inline Status frozen_court_permit_issue(Runtime*r,const PreparedAction*a,ExecutionPermit*out){TaskSecurityProjection p{};auto st=project_task(r,a->mission_id,a->mission_version,a->task_digest,&p);if(st!=Status::Ok)return st;if(!p.mission_created&&(st=frozen_court_task_marker(r,a,EventType::MISSION_CREATED))!=Status::Ok)return st;if(!p.task_received&&(st=frozen_court_task_marker(r,a,EventType::TASK_RECEIVED))!=Status::Ok)return st;if(!p.task_validated&&(st=frozen_court_task_marker(r,a,EventType::TASK_VALIDATED))!=Status::Ok)return st;if(!p.nonce_claimed){Digest256 n{};if((st=sha256({a->task_digest.bytes.data(),32},&n))!=Status::Ok)return st;if((st=nonce_claim(r,a->mission_id,a->mission_version,a->task_digest,n))!=Status::Ok)return st;}if(!p.idempotency_claimed){Digest256 i{};if((st=sha256({a->effect_id.bytes.data(),32},&i))!=Status::Ok)return st;if((st=idempotency_claim(r,a->mission_id,a->mission_version,a->task_digest,i))!=Status::Ok)return st;}if(!p.action_prepared&&(st=frozen_court_task_marker(r,a,EventType::ACTION_PREPARED))!=Status::Ok)return st;return permit_issue(r,a,out);}
#define permit_issue(r,a,out) frozen_court_permit_issue((r),(a),(out))

#define court_fmt_001 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-001",c);})
#define court_fmt_002 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-002",c);})
#define court_fmt_003 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-003",c);})
#define court_fmt_004 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-004",c);})
#define court_fmt_005 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-005",c);})
#define court_fmt_006 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-006",c);})
#define court_fmt_007 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-007",c);})
#define court_fmt_008 (+[](CourtContext*c)->CourtResult{return fmt_case("FMT-008",c);})
#define court_jrn_001 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-001",c);})
#define court_jrn_002 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-002",c);})
#define court_jrn_003 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-003",c);})
#define court_jrn_004 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-004",c);})
#define court_jrn_005 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-005",c);})
#define court_jrn_006 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-006",c);})
#define court_jrn_007 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-007",c);})
#define court_jrn_008 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-008",c);})
#define court_jrn_009 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-009",c);})
#define court_jrn_010 (+[](CourtContext*c)->CourtResult{return journal_case("JRN-010",c);})
#define court_obj_001 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-001",c);})
#define court_obj_002 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-002",c);})
#define court_obj_003 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-003",c);})
#define court_obj_004 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-004",c);})
#define court_obj_005 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-005",c);})
#define court_obj_006 (+[](CourtContext*c)->CourtResult{return object_case("OBJ-006",c);})
#define court_sec_001 (+[](CourtContext*c)->CourtResult{return sec_case("SEC-001",c);})
#define court_sec_002 (+[](CourtContext*c)->CourtResult{return sec_case("SEC-002",c);})
#define court_sec_003 (+[](CourtContext*c)->CourtResult{return sec_case("SEC-003",c);})
#define court_sec_004 (+[](CourtContext*c)->CourtResult{return sec_case("SEC-004",c);})
}
