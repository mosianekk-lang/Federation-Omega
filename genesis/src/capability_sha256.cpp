#include "fuse/capability.h"
namespace fuse {Status capability_sha256(ByteSpan in,Buffer*out){Digest256 d{};auto st=sha256(in,&d);if(st!=Status::Ok)return st;FcbWriter w{};fcb_begin(&w,0x1002,0);fcb_put_u64(&w,1,in.size);fcb_put_bytes(&w,2,FcbType::DIGEST256,{d.bytes.data(),32});return fcb_finish(&w,out,nullptr);}}
