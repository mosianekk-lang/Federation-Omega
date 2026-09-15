#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "fuse/court.h"
namespace fuse {
std::wstring self_path(){std::wstring s(32768,L'\0');DWORD n=GetModuleFileNameW(nullptr,s.data(),(DWORD)s.size());if(!n)return {};s.resize(n);return s;}
Status launch_court_child(const std::wstring&exe,const std::string&id,const std::wstring&root,DWORD*exit_code){if(!exit_code)return Status::InvalidArgument;std::wstring wid(id.begin(),id.end());std::wstring cmd=L"\""+exe+L"\" --court-child "+wid+L" \""+root+L"\"";STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};if(!CreateProcessW(nullptr,cmd.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW,nullptr,nullptr,&si,&pi))return Status::FileOpenFailed;DWORD wr=WaitForSingleObject(pi.hProcess,60000);if(wr!=WAIT_OBJECT_0){TerminateProcess(pi.hProcess,0xDEAD);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);return Status::TestFailed;}DWORD ec=0;GetExitCodeProcess(pi.hProcess,&ec);CloseHandle(pi.hThread);CloseHandle(pi.hProcess);*exit_code=ec;return Status::Ok;}
}
