#pragma once
#include "identity.h"
namespace fuse {
static constexpr u32 CAP_SYSTEM_STATUS=0x0001,CAP_SHA256=0x0002,CAP_FILE_HASH=0x0003,CAP_FILE_WRITE_ATOMIC=0x0004;
enum class CapabilityEffect:u16{NONE=0,READ_ONLY=1,REVERSIBLE=2};enum class ReplayClass:u16{RECOMPUTE_SAFE=1,RECEIVER_RECONCILE=2};
struct FileIdentity{u64 volume_serial{};std::array<u8,16> file_id{};bool operator==(const FileIdentity&o)const noexcept{return volume_serial==o.volume_serial&&file_id==o.file_id;}};
struct FileRoot{u32 root_id{};std::wstring configured_path;std::wstring final_path;FileIdentity identity{};bool read_allowed{};bool write_allowed{};};
struct CapabilityDescriptor{u32 id{};const char* name{};CapabilityEffect effect{};ReplayClass replay{};};
struct CapabilityRegistry{std::array<CapabilityDescriptor,4> entries{};Digest256 root_hash{};};
struct FileHashResult{FileIdentity identity{};u64 size{};Digest256 digest{};};
enum class FileObservedState:u16{ABSENT=0,OLD_STATE=1,NEW_STATE=2,THIRD_STATE=3};
struct FileWritePrepared{FileRoot root{};std::wstring relative_path;ObjectRef new_object{};bool old_present{};Digest256 old_digest{};bool rollback_required{};ObjectRef rollback_object{};Digest256 prepared_digest{};};
Status register_root(u32,const std::wstring&,bool,bool,FileRoot*);Status validate_relative_path(const std::wstring&);Status file_hash_authorized(const FileRoot*,const std::wstring&,FileHashResult*);Status file_read_authorized(const FileRoot*,const std::wstring&,Buffer*,FileIdentity*);Status file_write_prepare(const FileRoot*,const ObjectStore*,const std::wstring&,const ObjectRef&,bool,const Digest256*,bool,FileWritePrepared*);Status file_write_execute(const ObjectStore*,const FileWritePrepared*,FileHashResult*);Status file_write_observe(const FileWritePrepared*,FileObservedState*,FileHashResult*);Status file_write_rollback(const ObjectStore*,const FileWritePrepared*);
Status registry_initialize(CapabilityRegistry*);Status registry_find(const CapabilityRegistry*,u32,const CapabilityDescriptor**);Status capability_system_status(Buffer*);Status capability_sha256(ByteSpan,Buffer*);
}
