#pragma once
#include "format.h"
#include <string>
namespace fuse {
static constexpr u64 FSO1_HEADER_SIZE=48,GENESIS_SEGMENT_LIMIT=64ull*1024ull*1024ull,GENESIS_MAX_RECORD=16ull*1024ull*1024ull;
struct ObjectRef{Digest256 digest{};u64 size{};u16 content_type{};u16 flags{};};struct ObjectStore{std::wstring root;};
struct JournalScan{bool journal_exists{};u64 highest_segment_id{};u64 append_segment_id{1};u64 append_offset{};u64 last_record_segment_id{};u64 last_record_end_offset{};u64 last_sequence{};Digest256 last_record_hash{};bool tail_damage{};u64 damaged_segment_id{};u64 damage_offset{};Status damage_reason{Status::Ok};};
struct JournalWriter{std::wstring root;u64 segment_id{1};u64 segment_size{};u64 next_sequence{1};u64 segment_limit{GENESIS_SEGMENT_LIMIT};Digest256 previous_hash{};};
struct HeadState{u64 generation{};u64 segment_id{};u64 journal_offset{};u64 sequence{};Digest256 journal_hash{};Digest256 snapshot_hash{};Digest256 state_root{};};
using ReplayFn=Status(*)(const JournalRecordView*,void*);
Status journal_writer_open(const std::wstring&,JournalWriter*,u64 segment_limit=GENESIS_SEGMENT_LIMIT);Status journal_append(JournalWriter*,const Id128*,u64,u32,ByteSpan,Digest256*);Status journal_scan_root(const std::wstring&,JournalScan*);Status journal_recover(const std::wstring&,JournalScan*);Status journal_replay_all(const std::wstring&,ReplayFn,void*);Status head_reconstruct(const std::wstring&,const JournalScan&,u64,HeadState*);Status head_load_best(const std::wstring&,HeadState*);
Status object_store_open(const std::wstring&,ObjectStore*);Status object_put(const ObjectStore*,ByteSpan,u16,ObjectRef*);Status object_get(const ObjectStore*,const ObjectRef*,Buffer*);Status object_verify(const ObjectStore*,const ObjectRef*);Status object_verify_path(const std::wstring&,const ObjectRef*);std::wstring object_path(const ObjectStore*,const Digest256&);
}
