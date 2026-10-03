#pragma once
#include "crypto.h"
namespace fuse {
static constexpr u64 FCB1_HEADER_SIZE=24,FCB1_DIGEST_SIZE=32,FCB1_FIELD_HEADER_SIZE=16,FSJ1_HEADER_SIZE=140,FSJ1_HASH_SIZE=32;
enum class FcbType:u8{U64=1,BYTES=2,UTF8=3,DIGEST256=4};static constexpr u8 FCB_FIELD_CRITICAL=1;
struct FcbWriter{Buffer bytes;u32 field_count{};u32 last_field_id{};bool sealed{};};
struct FcbFieldView{u32 id{};FcbType type{};u8 flags{};ByteSpan value{};u64 next_offset{};};
Status fcb_begin(FcbWriter*,u16,u32);Status fcb_put_u64(FcbWriter*,u32,u64,u8 flags=0);Status fcb_put_bytes(FcbWriter*,u32,FcbType,ByteSpan,u8 flags=0);Status fcb_finish(FcbWriter*,Buffer*,Digest256*);Status fcb_validate(ByteSpan);Status fcb_first(ByteSpan,FcbFieldView*);Status fcb_next(ByteSpan,const FcbFieldView&,FcbFieldView*);Status fcb_get_u64(ByteSpan,u32,u64*);Status fcb_get_bytes(ByteSpan,u32,ByteSpan*);
struct JournalRecordInput{u32 flags{};u64 sequence{};Id128 mission_id{};u64 mission_version{};u32 event_type{};u64 wall_time_100ns{};u64 monotonic_ticks{};Digest256 previous_record_hash{};ByteSpan payload{};};
struct JournalRecordView{u64 sequence{};Id128 mission_id{};u64 mission_version{};u32 event_type{};Digest256 previous_record_hash{};ByteSpan payload{};Digest256 record_hash{};};
Status fsj_build(const JournalRecordInput*,Buffer*,Digest256*);Status fsj_validate(ByteSpan);Status fsj_view(ByteSpan,JournalRecordView*);
}
