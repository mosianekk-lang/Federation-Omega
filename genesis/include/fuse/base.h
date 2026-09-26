#pragma once
#include <cstdint>
#include <cstddef>
#include <array>
#include <vector>
#include <string>

namespace fuse {
using u8=std::uint8_t; using u16=std::uint16_t; using u32=std::uint32_t; using u64=std::uint64_t;
struct ByteSpan{const u8* data{};u64 size{};};
struct MutableByteSpan{u8* data{};u64 size{};};
using Buffer=std::vector<u8>;
struct Digest256{std::array<u8,32> bytes{};bool operator==(const Digest256&o)const noexcept{return bytes==o.bytes;}bool operator!=(const Digest256&o)const noexcept{return !(*this==o);}};
struct Id128{std::array<u8,16> bytes{};bool operator==(const Id128&o)const noexcept{return bytes==o.bytes;}};
void bytes_zero(u8*,u64);void bytes_copy(u8*,const u8*,u64);bool bytes_equal(const u8*,const u8*,u64);
void put_u16_le(u8*,u16);void put_u32_le(u8*,u32);void put_u64_le(u8*,u64);u16 get_u16_le(const u8*);u32 get_u32_le(const u8*);u64 get_u64_le(const u8*);
std::string hex(ByteSpan);bool unhex(const std::string&,MutableByteSpan);std::string digest_hex(const Digest256&);Id128 id_from_seed(const char*);
}
