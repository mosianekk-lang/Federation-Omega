#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "fuse/capability.h"
namespace fuse {Status capability_system_status(Buffer*out){SYSTEM_INFO si{};GetNativeSystemInfo(&si);MEMORYSTATUSEX ms{};ms.dwLength=sizeof(ms);GlobalMemoryStatusEx(&ms);FcbWriter w{};fcb_begin(&w,0x1001,0);fcb_put_u64(&w,1,si.dwNumberOfProcessors);fcb_put_u64(&w,2,ms.ullAvailPhys);fcb_put_u64(&w,3,sizeof(void*)*8);return fcb_finish(&w,out,nullptr);}}
