#pragma once
#include "logos_graph.h"
namespace logos {
enum class IntakeDisposition:u64{Admitted=1,AlreadyAdmitted=2,Rejected=3};
struct HistoricalFixture{std::string source_id,author,title,year,witness_id,passage_id,locator,claim_id,subject_id,predicate,claim_class,epistemic,scope,payload;};
struct GenesisFixture{std::string implementation_id,court_id,scope,obs_receiver_id,receiver_content,obs_write_id;u64 write_count{};std::string obs_duplicate_id;u64 duplicate_second_effect{};std::string claim_id;};
struct CompilerCapsule{Digest256 input_digest{},graph_root_before{},graph_root_after{};IntakeDisposition disposition{IntakeDisposition::Rejected};std::vector<std::string> admitted_ids;};
Status parse_historical_fixture(ByteSpan,HistoricalFixture*);Status parse_genesis_fixture(ByteSpan,GenesisFixture*);Status ingest_historical(ObjectStore*,Ledger*,GraphState*,ByteSpan,CompilerCapsule*);Status ingest_genesis(ObjectStore*,Ledger*,GraphState*,ByteSpan,CompilerCapsule*);Status record_rejection(ObjectStore*,Ledger*,GraphState*,const Digest256&,u64,std::string_view,Digest256*);
}
