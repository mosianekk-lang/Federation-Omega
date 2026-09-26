#pragma once
#include "logos_format.h"
namespace logos {
struct ObjectStore{std::filesystem::path root;};struct Ledger{std::filesystem::path path;u64 next_sequence{1};Digest256 previous_hash{};};
Status object_store_open(const std::filesystem::path&,ObjectStore*);Status object_put(ObjectStore*,ByteSpan,Digest256*);Status object_get(const ObjectStore*,const Digest256&,Buffer*);Status object_verify(const ObjectStore*,const Digest256&);Status blob_put(ObjectStore*,ByteSpan,Digest256*);Status blob_get(const ObjectStore*,const Digest256&,Buffer*);Status blob_verify(const ObjectStore*,const Digest256&);
Status ledger_open(const std::filesystem::path&,Ledger*);Status ledger_append(Ledger*,EventType,const Digest256&,std::string_view,Digest256*);using ReplayFn=Status(*)(const LglRecord&,void*);Status ledger_replay(const Ledger&,ReplayFn,void*);Status ledger_count(const Ledger&,u64*);
}
