#pragma once
#include <array>
#include <cstdint>
#include <filesystem>
#include <map>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace logos {
using u8=std::uint8_t;using u16=std::uint16_t;using u32=std::uint32_t;using u64=std::uint64_t;using Buffer=std::vector<u8>;
struct ByteSpan{const u8* data{};u64 size{};};
struct Digest256{std::array<u8,32> bytes{};bool operator==(const Digest256&o)const noexcept{return bytes==o.bytes;}bool operator!=(const Digest256&o)const noexcept{return !(*this==o);}bool operator<(const Digest256&o)const noexcept{return bytes<o.bytes;}};
enum class Status:u32{Ok=0,InvalidArgument,IOError,BadMagic,BadVersion,BadLength,BadDigest,BadFieldOrder,DuplicateField,UnknownCriticalField,InvalidUtf8,ObjectNotFound,ObjectCollision,LedgerCorrupt,LedgerSequence,LedgerChain,NodeExists,NodeMissing,BadRevision,EdgeExists,EdgeMissing,ProvenanceMissing,ScopeMissing,ParseError,DuplicateConflict,EpistemicAmplification,InvariantViolation,Unsupported};
Digest256 sha256(ByteSpan);std::string hex(const Digest256&);Status parse_hex_digest(std::string_view,Digest256*);bool digest_equal(const Digest256&,const Digest256&);bool valid_utf8(ByteSpan);bool valid_semantic_id(std::string_view);const char* status_name(Status);
void put_u16_le(u8*,u16);void put_u32_le(u8*,u32);void put_u64_le(u8*,u64);u16 get_u16_le(const u8*);u32 get_u32_le(const u8*);u64 get_u64_le(const u8*);
}
