#include "fuse_core.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>

int main(){
    using namespace fuse;
    assert(json_escape("a\"b\n")=="a\\\"b\\n");
    assert(extract_json_string("{\"prompt\":\"hello\"}","prompt")=="hello");
    assert(extract_last_message_content("{\"messages\":[{\"content\":\"one\"},{\"content\":\"two\"}]}")=="two");
    assert(make_chatml_prompt("Hi",false).find("<|im_start|>user")!=std::string::npos);

    auto tmp=std::filesystem::temp_directory_path()/"fuse_sha_test.txt";
    {std::ofstream f(tmp,std::ios::binary);f<<"abc";}
    assert(sha256_file(tmp)=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");

    auto d=std::filesystem::temp_directory_path()/"fuse_gguf_discovery";
    std::filesystem::create_directories(d);
    {std::ofstream f(d/"m.gguf");f<<"GGUF";}
    auto found=auto_discover_gguf({d});
    assert(found.filename()=="m.gguf");

    auto id=identify_model(d/"m.gguf");
    assert(id.bytes==4);
    assert(id.sha256.size()==64);

    char a0[]="x",a1[]="--host",a2[]="127.0.0.1",a3[]="--port",a4[]="8999",a5[]="--ctx",a6[]="4096";
    char* argv[]={a0,a1,a2,a3,a4,a5,a6};
    auto c=parse_args(7,argv);
    assert(c.port==8999 && c.context==4096);
    auto receipt=runtime_receipt_json(c,id,"TEST");
    assert(receipt.find("FUSE-LOCAL-LLM-RECEIPT-V1")!=std::string::npos);

    std::filesystem::remove_all(d); std::filesystem::remove(tmp);
    std::cout<<"FUSE core tests PASS\n";
}