#ifdef _WIN32
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <filesystem>

static bool port_open(){
    // Avoid networking complexity in launcher: simply let duplicate runtime fail its bind.
    return false;
}
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int){
    wchar_t exePath[MAX_PATH];GetModuleFileNameW(nullptr,exePath,MAX_PATH);
    std::filesystem::path dir=std::filesystem::path(exePath).parent_path();
    auto runtime=(dir/L"FUSE-LocalLLM.exe").wstring();

    STARTUPINFOW si{};si.cb=sizeof(si);PROCESS_INFORMATION pi{};
    std::wstring cmd=L"\""+runtime+L"\" serve --port 8999";
    CreateProcessW(nullptr,cmd.data(),nullptr,nullptr,FALSE,CREATE_NO_WINDOW|DETACHED_PROCESS,nullptr,dir.wstring().c_str(),&si,&pi);
    if(pi.hProcess){CloseHandle(pi.hThread);CloseHandle(pi.hProcess);}
    Sleep(1400);

    const wchar_t* url=L"http://127.0.0.1:8999/";
    std::wstring args=L"--app="+std::wstring(url)+L" --start-maximized --disable-features=msEdgeSidebarV2";
    HINSTANCE r=ShellExecuteW(nullptr,L"open",L"msedge.exe",args.c_str(),nullptr,SW_SHOW);
    if((INT_PTR)r<=32)ShellExecuteW(nullptr,L"open",url,nullptr,nullptr,SW_SHOW);
    return 0;
}
#else
int main(){return 0;}
#endif
