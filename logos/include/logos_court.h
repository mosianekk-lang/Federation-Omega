#pragma once
#include "logos_ingest.h"
namespace logos {
struct CourtResult{const char* id{};bool passed{};Status status{Status::InvariantViolation};};struct CourtSummary{u32 discovered{},executed{},passed{},failed{};};
Status run_graph_court(const std::filesystem::path&,CourtSummary*);Status run_compiler_court(const std::filesystem::path&,CourtSummary*);Status run_mevs_acceptance(const std::filesystem::path&);Status verify_root(const std::filesystem::path&,Digest256*,Digest256*,Digest256*);
}
