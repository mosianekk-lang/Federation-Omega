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
}
