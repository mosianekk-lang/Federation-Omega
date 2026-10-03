#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "fuse/capability.h"
namespace fuse {
Status resolve_authorized_existing(const FileRoot*,const std::wstring&,std::wstring*,FileIdentity*);Status file_hash_handle(HANDLE,FileHashResult*);
Status file_hash_authorized(const FileRoot*r,const std::wstring&rel,FileHashResult*out){if(!r||!out||!r->read_allowed)return Status::InvalidArgument;std::wstring p;auto st=resolve_authorized_existing(r,rel,&p,nullptr);if(st!=Status::Ok)return st;HANDLE h=CreateFileW(p.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_SEQUENTIAL_SCAN,nullptr);if(h==INVALID_HANDLE_VALUE)return Status::FileOpenFailed;FILE_STANDARD_INFO info{};if(!GetFileInformationByHandleEx(h,FileStandardInfo,&info,sizeof(info))||info.Directory){CloseHandle(h);return Status::FileTypeInvalid;}st=file_hash_handle(h,out);CloseHandle(h);return st;}
Status file_read_authorized(const FileRoot*r,const std::wstring&rel,Buffer*out,FileIdentity*id){if(!r||!out||!r->read_allowed)return Status::InvalidArgument;std::wstring p;auto st=resolve_authorized_existing(r,rel,&p,id);if(st!=Status::Ok)return st;HANDLE h=CreateFileW(p.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);if(h==INVALID_HANDLE_VALUE)return Status::FileOpenFailed;LARGE_INTEGER sz{};if(!GetFileSizeEx(h,&sz)||sz.QuadPart<0){CloseHandle(h);return Status::FileReadFailed;}out->resize((size_t)sz.QuadPart);u64 off=0;while(off<out->size()){DWORD n=0,w=(DWORD)(((out->size()-off)>0x40000000ull)?0x40000000ull:(out->size()-off));if(!ReadFile(h,out->data()+off,w,&n,nullptr)||!n){CloseHandle(h);return Status::FileReadFailed;}off+=n;}CloseHandle(h);return Status::Ok;}
}
