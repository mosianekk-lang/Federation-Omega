#include "fuse_core.hpp"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace fuse {

// Minimal FUSE-owned SHA-256 implementation.
namespace {
using u32 = uint32_t; using u64 = uint64_t;
constexpr u32 K[64] = {
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
inline u32 rotr(u32 x,u32 n){return (x>>n)|(x<<(32-n));}
struct Sha256 {
    u32 h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    std::array<unsigned char,64> buf{}; size_t used=0; u64 bits=0;
    void block(const unsigned char * p){
        u32 w[64];
        for(int i=0;i<16;i++) w[i]=(u32(p[4*i])<<24)|(u32(p[4*i+1])<<16)|(u32(p[4*i+2])<<8)|p[4*i+3];
        for(int i=16;i<64;i++){u32 s0=rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3);u32 s1=rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+s0+w[i-7]+s1;}
        u32 a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for(int i=0;i<64;i++){u32 S1=rotr(e,6)^rotr(e,11)^rotr(e,25),ch=(e&f)^((~e)&g);u32 t1=hh+S1+ch+K[i]+w[i];u32 S0=rotr(a,2)^rotr(a,13)^rotr(a,22),maj=(a&b)^(a&c)^(b&c);u32 t2=S0+maj;hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
    }
    void update(const unsigned char * p,size_t n){bits+=u64(n)*8;while(n){size_t take=std::min(n,64-used);std::copy(p,p+take,buf.begin()+used);used+=take;p+=take;n-=take;if(used==64){block(buf.data());used=0;}}}
    std::string finish(){u64 orig=bits;unsigned char one=0x80;update(&one,1);unsigned char zero=0;while(used!=56)update(&zero,1);unsigned char len[8];for(int i=0;i<8;i++)len[7-i]=static_cast<unsigned char>((orig>>(8*i))&0xff);update(len,8);std::ostringstream o;o<<std::hex<<std::setfill('0');for(auto x:h)o<<std::setw(8)<<x;return o.str();}
};
}

std::string sha256_file(const std::filesystem::path & path){
    std::ifstream f(path,std::ios::binary); if(!f) throw std::runtime_error("MODEL_OPEN_FAILED");
    Sha256 s; std::array<unsigned char,1<<20> b{};
    while(f){f.read(reinterpret_cast<char*>(b.data()),b.size());auto n=f.gcount();if(n>0)s.update(b.data(),size_t(n));}
    return s.finish();
}

std::string json_escape(const std::string & s){
    std::ostringstream o;
    for(unsigned char c:s){switch(c){case '"':o<<"\\\"";break;case '\\':o<<"\\\\";break;case '\n':o<<"\\n";break;case '\r':o<<"\\r";break;case '\t':o<<"\\t";break;default: if(c<0x20)o<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<int(c)<<std::dec; else o<<char(c);}}
    return o.str();
}

static std::string unescape_json_string(const std::string & s){
    std::string out; out.reserve(s.size());
    for(size_t i=0;i<s.size();++i){if(s[i]=='\\' && i+1<s.size()){char n=s[++i];switch(n){case 'n':out+='\n';break;case 'r':out+='\r';break;case 't':out+='\t';break;case '"':out+='"';break;case '\\':out+='\\';break;default:out+=n;}}else out+=s[i];}
    return out;
}
std::string extract_json_string(const std::string & body,const std::string & key){
    std::string needle="\""+key+"\""; auto p=body.find(needle); if(p==std::string::npos)return {};
    p=body.find(':',p+needle.size()); if(p==std::string::npos)return {}; p=body.find('"',p+1); if(p==std::string::npos)return {};
    std::string raw; bool esc=false; for(size_t i=p+1;i<body.size();++i){char c=body[i]; if(!esc && c=='"') return unescape_json_string(raw); if(!esc && c=='\\'){esc=true;raw+=c;} else {raw+=c;esc=false;}}
    return {};
}
std::string extract_last_message_content(const std::string & body){
    std::string needle="\"content\""; size_t p=0,last=std::string::npos;
    while((p=body.find(needle,p))!=std::string::npos){last=p;p+=needle.size();}
    if(last==std::string::npos) return extract_json_string(body,"prompt");
    auto sub=body.substr(last); return extract_json_string(sub,"content");
}
std::string make_chatml_prompt(const std::string & user,bool no_think){
    std::string p="<|im_start|>user\n"+user+"<|im_end|>\n<|im_start|>assistant\n";
    if(no_think) p+="<think></think>\n";
    return p;
}

std::filesystem::path auto_discover_gguf(const std::vector<std::filesystem::path> & roots){
    std::filesystem::path best; std::filesystem::file_time_type newest{};
    for(const auto & root:roots){
        std::error_code ec; if(!std::filesystem::exists(root,ec)) continue;
        for(auto it=std::filesystem::recursive_directory_iterator(root,std::filesystem::directory_options::skip_permission_denied,ec);it!=std::filesystem::recursive_directory_iterator();it.increment(ec)){
            if(ec){ec.clear();continue;} if(!it->is_regular_file(ec))continue;
            auto ext=it->path().extension().string(); std::transform(ext.begin(),ext.end(),ext.begin(),::tolower);
            if(ext!=".gguf")continue; auto t=it->last_write_time(ec); if(best.empty()||t>newest){best=it->path();newest=t;}
        }
    } return best;
}

RuntimeConfig parse_args(int argc,char ** argv){
    RuntimeConfig c;
    for(int i=1;i<argc;i++){
        std::string a=argv[i]; auto next=[&](){if(i+1>=argc)throw std::runtime_error("ARG_VALUE_MISSING:"+a);return std::string(argv[++i]);};
        if(a=="serve"||a=="--serve")c.serve=true;
        else if(a=="inspect"||a=="--inspect")c.inspect=true;
        else if(a=="--model"||a=="-m")c.model_path=next();
        else if(a=="--host")c.host=next();
        else if(a=="--port")c.port=std::stoi(next());
        else if(a=="--ctx")c.context=std::stoi(next());
        else if(a=="--max-tokens"||a=="-n")c.max_tokens=std::stoi(next());
        else if(a=="--gpu-layers"||a=="-ngl")c.gpu_layers=std::stoi(next());
        else if(a=="--threads")c.threads=std::stoi(next());
        else if(a=="--temp")c.temperature=std::stof(next());
        else if(a=="--top-p")c.top_p=std::stof(next());
        else if(a=="--top-k")c.top_k=std::stoi(next());
        else if(a=="--no-think")c.no_think=true;
        else if(a=="--prompt") { /* consumed by main */ next(); }
    }
    if(c.host!="127.0.0.1"&&c.host!="localhost"&&c.host!="::1") throw std::runtime_error("LOOPBACK_ONLY");
    if(c.port<1024||c.port>65535)throw std::runtime_error("PORT_RANGE");
    if(c.context<256||c.max_tokens<1)throw std::runtime_error("INVALID_GENERATION_LIMIT");
    if(c.threads<=0)c.threads=std::max(1u,std::thread::hardware_concurrency());
    return c;
}

ModelIdentity identify_model(const std::filesystem::path & path){
    if(path.empty()||!std::filesystem::exists(path))throw std::runtime_error("MODEL_NOT_FOUND");
    ModelIdentity m; m.path=std::filesystem::absolute(path).string();m.filename=path.filename().string();m.bytes=std::filesystem::file_size(path);m.sha256=sha256_file(path);return m;
}

std::string runtime_receipt_json(const RuntimeConfig & cfg,const ModelIdentity & m,const std::string & backend){
    std::ostringstream o; o<<"{\"schema\":\"FUSE-LOCAL-LLM-RECEIPT-V1\",\"backend\":\""<<json_escape(backend)<<"\",\"model\":{\"filename\":\""<<json_escape(m.filename)<<"\",\"bytes\":"<<m.bytes<<",\"sha256\":\""<<m.sha256<<"\"},\"network\":{\"host\":\""<<cfg.host<<"\",\"port\":"<<cfg.port<<",\"loopback_only\":true},\"limits\":{\"context\":"<<cfg.context<<",\"max_tokens\":"<<cfg.max_tokens<<",\"threads\":"<<cfg.threads<<",\"gpu_layers\":"<<cfg.gpu_layers<<"}}"; return o.str();
}
}