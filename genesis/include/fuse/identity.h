#pragma once
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <ncrypt.h>
#include "store.h"
namespace fuse {
struct SigningIdentity{NCRYPT_PROV_HANDLE provider{};NCRYPT_KEY_HANDLE key{};std::wstring key_name;bool software_fallback{};};
Status identity_open_or_create(SigningIdentity*,const std::wstring&);void identity_close(SigningIdentity*);Status identity_sign(SigningIdentity*,const Digest256*,Buffer*);Status identity_verify(SigningIdentity*,const Digest256*,ByteSpan);
}
