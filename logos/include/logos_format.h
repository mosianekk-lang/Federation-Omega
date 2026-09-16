#pragma once
#include "logos_base.h"
namespace logos {
static constexpr u64 LGO1_HEADER_SIZE=24,LGO1_FIELD_HEADER_SIZE=16,LGO1_TRAILER_SIZE=32,LGL1_RECORD_SIZE=152;static constexpr u8 FIELD_CRITICAL=0x01;
enum class FieldType:u8{U64=0x01,UTF8=0x02,BYTES=0x03,DIGEST256=0x04,DIGEST256_LIST=0x05};
enum class RecordKind:u64{NODE=1,EDGE=2,REJECTION=3};
enum class NodeType:u64{SOURCE=1,WITNESS=2,PASSAGE=3,CLAIM=4,IMPLEMENTATION=5,COURT=6,OBSERVATION=7,EVIDENCE=8,CONTRADICTION=9,PRINCIPLE=10,VIEW=11};
enum class RelationCode:u64{WITNESS_OF=1,EXTRACTED_FROM=2,ASSERTS=3,IMPLEMENTS=4,TESTS=5,OBSERVES=6,SUPPORTS=7,CONTRADICTS=8,SCOPED_TO=9,PROJECTED_INTO=10};
enum class EventType:u32{NODE_CREATED=1,NODE_REVISED=2,EDGE_ADDED=3,EDGE_RETIRED=4,REJECTION_RECORDED=5,VIEW_PUBLISHED=6};
enum FieldId:u32{F_RECORD_KIND=1,F_NODE_TYPE=2,F_SEMANTIC_ID=3,F_REVISION=4,F_LIFECYCLE=5,F_TITLE=6,F_SUMMARY=7,F_EPISTEMIC_STATE=8,F_MATURITY=9,F_SCOPE=10,F_ATTRIBUTION=11,F_OBJECT_DIGEST=12,F_LOCATOR=13,F_VALUE_TEXT=14,F_VALUE_U64=15,F_REF_A_ID=16,F_REF_A_REVISION_DIGEST=17,F_REF_B_ID=18,F_REF_B_REVISION_DIGEST=19,F_RELATION_CODE=20,F_FALSIFICATION_CONDITION=21,F_APPLICABILITY_BOUNDARY=22,F_STATUS=23,F_BODY_DIGEST=24,F_GRAPH_ROOT=25,F_SOURCE_CLASS=26,F_CLAIM_CLASS=27,F_COURT_DENOMINATOR=28,F_VIEW_TYPE=29,F_PROVENANCE_ID=30,F_TIME_SCOPE=31,F_SUBJECT_ID=32,F_PREDICATE=33,F_VALUE_KIND=34,F_MEMBER_A_ID=35,F_MEMBER_B_ID=36,F_RESOLUTION_ID=37,F_INPUT_DIGEST=38,F_REJECTION_REASON=39,F_REJECTION_DETAIL=40};
enum class Lifecycle:u64{DRAFT=1,ACTIVE=2,DEPRECATED=3,SUPERSEDED=4,RETIRED=5,DISPUTED=6,QUARANTINED=7};
enum class Epistemic:u64{REPORTED=1,OBSERVED=2,INFERRED=3,INTERPRETED=4,ANALOGICAL=5,HYPOTHESIZED=6,TESTED=7,REPRODUCED=8,CONTRADICTED=9,FALSIFIED=10};
enum class Maturity:u64{L0_CAPTURED=0,L1_PROVISIONAL=1,L2_TESTED=2,L3_SCOPE_VERIFIED=3,L4_CROSS_VERIFIED=4,L5_CANONICAL=5};
enum class ValueKind:u64{TEXT=1,U64=2};enum class ViewType:u64{CANON=1,PROOF=2};
struct FieldView{u32 id{};FieldType type{};u8 flags{};ByteSpan value{};};struct LgoObjectView{ByteSpan bytes{};std::vector<FieldView> fields;Digest256 digest{};};struct LgoBuilder{Buffer field_stream;u32 field_count{};u32 last_field_id{};};
Status lgo_begin(LgoBuilder*);Status lgo_add_u64(LgoBuilder*,u32,u64,u8=0);Status lgo_add_utf8(LgoBuilder*,u32,std::string_view,u8=0);Status lgo_add_bytes(LgoBuilder*,u32,ByteSpan,u8=0);Status lgo_add_digest(LgoBuilder*,u32,const Digest256&,u8=0);Status lgo_add_digest_list(LgoBuilder*,u32,const std::vector<Digest256>&,u8=0);Status lgo_finish(LgoBuilder*,Buffer*,Digest256*);
Status lgo_validate(ByteSpan);Status lgo_parse(ByteSpan,LgoObjectView*);const FieldView* lgo_find_field(const LgoObjectView&,u32);Status lgo_get_u64(const LgoObjectView&,u32,u64*);Status lgo_get_utf8(const LgoObjectView&,u32,std::string*);Status lgo_get_digest(const LgoObjectView&,u32,Digest256*);Status lgo_get_digest_list(const LgoObjectView&,u32,std::vector<Digest256>*);
struct LglRecord{u32 event_type{};u64 sequence{};Digest256 previous_event_hash{},payload_object_digest{},target_semantic_hash{},event_hash{};};
Status lgl_encode(EventType,u64,const Digest256&,const Digest256&,std::string_view,Buffer*,Digest256*);Status lgl_validate(ByteSpan);Status lgl_parse(ByteSpan,LglRecord*);
}
