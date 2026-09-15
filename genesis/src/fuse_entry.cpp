#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include "fuse/court.h"
#include <filesystem>
#include <iostream>
namespace fuse {std::wstring self_path();Status ensure_directory(const std::wstring&);}int wmain(int argc,wchar_t**argv){using namespace fuse;if(argc>=2&&std::wstring(argv[1])==L"--self-court"){CourtContext c{};c.self_path=self_path();auto base=std::filesystem::temp_directory_path()/L"FUSE-GenesisCourt";ensure_directory(base.wstring());c.root=base.wstring();return run_self_court(&c);}if(argc==4&&std::wstring(argv[1])==L"--court-child"){std::wstring wid=argv[2];std::string id(wid.begin(),wid.end());return run_court_child(id,argv[3]);}if(argc==3&&std::wstring(argv[1])==L"--mvs-canary")return run_mvs_canary(argv[2]);std::wcerr<<L"Usage: fuse-genesis.exe --self-court | --court-child <id> <root> | --mvs-canary <root>\n";return 2;}
