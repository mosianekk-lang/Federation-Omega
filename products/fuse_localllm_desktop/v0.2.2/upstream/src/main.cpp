#include "fuse_core.hpp"
#include "ui_embedded.hpp"
#include "llama.h"
#include "ggml-backend.h"
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <iostream>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <shellapi.h>
#pragma comment(lib,"ws2_32.lib")
using socket_t=SOCKET;
static void socket_close(socket_t s){closesocket(s);}
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
using socket_t=int;
static void socket_close(socket_t s){close(s);}
#define INVALID_SOCKET (-1)
#define SOCKET_ERROR (-1)
#endif

using namespace fuse;

static double json_number(const std::string & b,const std::string & key,double fallback){
    auto p=b.find("\""+key+"\"");if(p==std::string::npos)return fallback;p=b.find(':',p);if(p==std::string::npos)return fallback;
    try{return std::stod(b.substr(p+1));}catch(...){return fallback;}
}
static bool json_bool(const std::string & b,const std::string & key,bool fallback){
    auto p=b.find("\""+key+"\"");if(p==std::string::npos)return fallback;p=b.find(':',p);if(p==std::string::npos)return fallback;
    auto s=b.substr(p+1,8);if(s.find("true")!=std::string::npos)return true;if(s.find("false")!=std::string::npos)return false;return fallback;
}

struct GenerationOptions{int max_tokens=512;int ctx=4096;float temp=.6f;float top_p=.95f;int top_k=20;bool no_think=false;};

struct Engine{
    llama_model * model=nullptr; const llama_vocab * vocab=nullptr; RuntimeConfig cfg; ModelIdentity identity;
    std::mutex lock;
    ~Engine(){if(model)llama_model_free(model);llama_backend_free();}
    void init(){llama_backend_init();ggml_backend_load_all();}
    void load_path(const std::string & path){
        std::lock_guard<std::mutex> g(lock);
        auto id=identify_model(path);
        auto mp=llama_model_default_params();mp.n_gpu_layers=cfg.gpu_layers;
        llama_model * next=llama_model_load_from_file(id.path.c_str(),mp);if(!next)throw std::runtime_error("MODEL_LOAD_FAILED");
        if(model)llama_model_free(model);model=next;vocab=llama_model_get_vocab(model);identity=id;
    }
    std::string desc(){
        std::lock_guard<std::mutex> g(lock);if(!model)return {};
        char b[1024]={0};int n=llama_model_desc(model,b,sizeof(b));return n>0?std::string(b,std::min<int>(n,sizeof(b)-1)):"";
    }
    std::string format_prompt(const std::string & user,bool no_think){
        llama_chat_message msg{"user",user.c_str()};const char * tmpl=model?llama_model_chat_template(model,nullptr):nullptr;
        if(tmpl){int need=llama_chat_apply_template(tmpl,&msg,1,true,nullptr,0);if(need>0){std::vector<char> out(size_t(need)+1);int got=llama_chat_apply_template(tmpl,&msg,1,true,out.data(),int32_t(out.size()));if(got>0)return std::string(out.data(),size_t(got));}}
        return make_chatml_prompt(user,no_think);
    }
    template<class F> std::string generate(const std::string & user,const GenerationOptions & o,F on_piece){
        std::lock_guard<std::mutex> g(lock);if(!model)throw std::runtime_error("NO_MODEL_LOADED");
        std::string prompt=format_prompt(user,o.no_think);
        int n_prompt=-llama_tokenize(vocab,prompt.c_str(),int32_t(prompt.size()),nullptr,0,true,true);if(n_prompt<=0)throw std::runtime_error("TOKENIZE_SIZE_FAILED");
        std::vector<llama_token> tokens(static_cast<size_t>(n_prompt),llama_token{});
        if(llama_tokenize(vocab,prompt.c_str(),int32_t(prompt.size()),tokens.data(),int32_t(tokens.size()),true,true)<0)throw std::runtime_error("TOKENIZE_FAILED");
        auto cp=llama_context_default_params();cp.n_ctx=uint32_t(std::max(o.ctx,n_prompt+o.max_tokens+16));cp.n_batch=uint32_t(std::min<int>(std::max(512,n_prompt),int(cp.n_ctx)));cp.n_threads=cfg.threads;cp.n_threads_batch=cfg.threads;
        llama_context * ctx=llama_init_from_model(model,cp);if(!ctx)throw std::runtime_error("CONTEXT_INIT_FAILED");
        auto sp=llama_sampler_chain_default_params();llama_sampler * smpl=llama_sampler_chain_init(sp);
        llama_sampler_chain_add(smpl,llama_sampler_init_top_k(o.top_k));llama_sampler_chain_add(smpl,llama_sampler_init_top_p(o.top_p,1));llama_sampler_chain_add(smpl,llama_sampler_init_temp(o.temp));llama_sampler_chain_add(smpl,llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
        llama_batch batch=llama_batch_get_one(tokens.data(),int32_t(tokens.size()));
        if(llama_decode(ctx,batch)!=0){llama_sampler_free(smpl);llama_free(ctx);throw std::runtime_error("PROMPT_DECODE_FAILED");}
        std::string out;
        for(int i=0;i<o.max_tokens;i++){
            auto t=llama_sampler_sample(smpl,ctx,-1);if(llama_vocab_is_eog(vocab,t))break;
            char buf[512];int n=llama_token_to_piece(vocab,t,buf,sizeof(buf),0,true);std::string piece;
            if(n<0){std::vector<char> big(size_t(-n)+8);n=llama_token_to_piece(vocab,t,big.data(),int32_t(big.size()),0,true);if(n>0)piece.assign(big.data(),size_t(n));}else if(n>0)piece.assign(buf,size_t(n));
            if(!piece.empty()){out+=piece;on_piece(piece);}
            batch=llama_batch_get_one(&t,1);if(llama_decode(ctx,batch)!=0)break;
        }
        llama_sampler_free(smpl);llama_free(ctx);return out;
    }
};

static std::vector<std::filesystem::path> model_roots(){
    std::vector<std::filesystem::path> r;
    if(const char * e=std::getenv("FUSE_MODEL_DIR"))r.emplace_back(e);
#ifdef _WIN32
    if(const char * u=std::getenv("USERPROFILE"))r.emplace_back(std::filesystem::path(u)/"Downloads"/"Programs"/"FUSE");
    if(const char * a=std::getenv("LOCALAPPDATA"))r.emplace_back(std::filesystem::path(a)/"FUSE"/"LocalLLM"/"models");
#else
    if(const char * h=std::getenv("HOME"))r.emplace_back(std::filesystem::path(h)/"models");
#endif
    return r;
}
static std::vector<std::filesystem::path> list_models(){
    std::vector<std::filesystem::path> out;
    for(auto & root:model_roots()){std::error_code ec;if(!std::filesystem::exists(root,ec))continue;
        for(auto it=std::filesystem::recursive_directory_iterator(root,std::filesystem::directory_options::skip_permission_denied,ec);it!=std::filesystem::recursive_directory_iterator();it.increment(ec)){if(ec){ec.clear();continue;}if(!it->is_regular_file(ec))continue;auto e=it->path().extension().string();std::transform(e.begin(),e.end(),e.begin(),::tolower);if(e==".gguf")out.push_back(std::filesystem::absolute(it->path()));}}
    std::sort(out.begin(),out.end(),[](auto&a,auto&b){std::error_code e1,e2;return std::filesystem::last_write_time(a,e1)>std::filesystem::last_write_time(b,e2);});return out;
}
static std::string models_json(const Engine & e){
    auto ms=list_models();std::ostringstream o;o<<"{\"object\":\"list\",\"data\":[";
    for(size_t i=0;i<ms.size();i++){std::error_code ec;auto b=std::filesystem::file_size(ms[i],ec);bool active=!e.identity.path.empty()&&std::filesystem::equivalent(ms[i],e.identity.path,ec);if(i)o<<",";
      o<<"{\"filename\":\""<<json_escape(ms[i].filename().string())<<"\",\"path\":\""<<json_escape(ms[i].string())<<"\",\"bytes\":"<<b<<",\"active\":"<<(active?"true":"false")<<"}";}
    o<<"]}";return o.str();
}
static std::string http_response(int code,const std::string & body,const std::string & type="application/json; charset=utf-8"){
    std::ostringstream o;o<<"HTTP/1.1 "<<code<<(code==200?" OK":" Error")<<"\r\nContent-Type: "<<type<<"\r\nContent-Length: "<<body.size()<<"\r\nConnection: close\r\nCache-Control: no-store\r\nAccess-Control-Allow-Origin: http://127.0.0.1\r\n\r\n"<<body;return o.str();
}
static void send_all(socket_t s,const std::string & x){size_t off=0;while(off<x.size()){int n=send(s,x.data()+off,int(x.size()-off),0);if(n<=0)break;off+=size_t(n);}}
static std::string recv_request(socket_t s){std::string r;char b[8192];int n;size_t content=0,he=std::string::npos;while((n=recv(s,b,sizeof(b),0))>0){r.append(b,b+n);if(he==std::string::npos){he=r.find("\r\n\r\n");if(he!=std::string::npos){auto p=r.find("Content-Length:");if(p!=std::string::npos)content=std::stoul(r.substr(p+15));}}if(he!=std::string::npos&&r.size()>=he+4+content)break;if(r.size()>8*1024*1024)break;}return r;}
static void sse_start(socket_t s){send_all(s,"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: close\r\nAccess-Control-Allow-Origin: http://127.0.0.1\r\n\r\n");}
static void sse(socket_t s,const std::string & piece){std::string j="{\"choices\":[{\"index\":0,\"delta\":{\"content\":\""+json_escape(piece)+"\"}}]}";send_all(s,"data: "+j+"\n\n");}

static int serve(Engine & e){
#ifdef _WIN32
    WSADATA w;if(WSAStartup(MAKEWORD(2,2),&w)!=0)return 2;
#endif
    socket_t srv=socket(AF_INET,SOCK_STREAM,0);if(srv==INVALID_SOCKET)return 2;int yes=1;setsockopt(srv,SOL_SOCKET,SO_REUSEADDR,(const char*)&yes,sizeof(yes));
    sockaddr_in a{};a.sin_family=AF_INET;a.sin_port=htons(uint16_t(e.cfg.port));inet_pton(AF_INET,"127.0.0.1",&a.sin_addr);if(bind(srv,(sockaddr*)&a,sizeof(a))==SOCKET_ERROR||listen(srv,16)==SOCKET_ERROR){socket_close(srv);return 3;}
    std::cout<<"FUSE LocalLLM Desktop runtime: http://127.0.0.1:"<<e.cfg.port<<"\n";
    for(;;){socket_t c=accept(srv,nullptr,nullptr);if(c==INVALID_SOCKET)continue;std::string req=recv_request(c);auto le=req.find("\r\n");std::string first=req.substr(0,le);auto he=req.find("\r\n\r\n");std::string body=he==std::string::npos?"":req.substr(he+4);
      try{
        if(first.rfind("GET /healthz ",0)==0)send_all(c,http_response(200,"{\"status\":\"ok\",\"runtime\":\"FUSE-LocalLLM-Desktop\",\"version\":\"0.2.2\"}"));
        else if(first.rfind("GET /app.css ",0)==0)send_all(c,http_response(200,fuse_ui::APP_CSS,"text/css; charset=utf-8"));
        else if(first.rfind("GET /app.js ",0)==0)send_all(c,http_response(200,fuse_ui::APP_JS,"application/javascript; charset=utf-8"));
        else if(first.rfind("GET / ",0)==0)send_all(c,http_response(200,fuse_ui::INDEX_HTML,"text/html; charset=utf-8"));
        else if(first.rfind("GET /v1/fuse/models/local ",0)==0||first.rfind("GET /api/tags ",0)==0)send_all(c,http_response(200,models_json(e)));
        else if(first.rfind("GET /api/version ",0)==0)send_all(c,http_response(200,"{\"version\":\"FUSE-LocalLLM-0.2.2\"}"));
        else if(first.rfind("GET /v1/models ",0)==0){std::string id=e.identity.filename.empty()?"none":e.identity.filename;send_all(c,http_response(200,"{\"object\":\"list\",\"data\":[{\"id\":\""+json_escape(id)+"\",\"object\":\"model\",\"owned_by\":\"FUSE\"}]}"));}
        else if(first.rfind("GET /v1/fuse/runtime ",0)==0){std::ostringstream o;o<<"{\"schema\":\"FUSE-LOCAL-LLM-RUNTIME-V2\",\"version\":\"0.2.2\",\"status\":\"ok\",\"model\":{\"filename\":\""<<json_escape(e.identity.filename)<<"\",\"path\":\""<<json_escape(e.identity.path)<<"\",\"bytes\":"<<e.identity.bytes<<",\"sha256\":\""<<json_escape(e.identity.sha256)<<"\"},\"description\":\""<<json_escape(e.desc())<<"\",\"network\":{\"host\":\"127.0.0.1\",\"port\":"<<e.cfg.port<<",\"loopback_only\":true},\"api\":{\"openai\":true,\"ollama_compat\":true,\"streaming\":true}}";send_all(c,http_response(200,o.str()));}
        else if(first.rfind("POST /v1/fuse/models/open-folder ",0)==0){
#ifdef _WIN32
          auto roots=model_roots();auto p=roots.size()>1?roots.back():roots.front();std::filesystem::create_directories(p);ShellExecuteW(nullptr,L"open",p.wstring().c_str(),nullptr,nullptr,SW_SHOW);
#endif
          send_all(c,http_response(200,"{\"ok\":true}"));
        }
        else if(first.rfind("POST /v1/fuse/models/select ",0)==0){auto p=extract_json_string(body,"path");if(p.empty())throw std::runtime_error("MODEL_PATH_MISSING");e.load_path(p);send_all(c,http_response(200,"{\"ok\":true,\"model\":\""+json_escape(e.identity.filename)+"\"}"));}
        else if(first.rfind("POST /v1/chat/completions ",0)==0||first.rfind("POST /api/chat ",0)==0||first.rfind("POST /api/generate ",0)==0||first.rfind("POST /v1/completions ",0)==0){
          std::string p=extract_last_message_content(body);if(p.empty())throw std::runtime_error("PROMPT_MISSING");GenerationOptions o;o.max_tokens=int(json_number(body,"max_tokens",512));o.ctx=int(json_number(body,"ctx",4096));o.temp=float(json_number(body,"temperature",.6));o.top_p=float(json_number(body,"top_p",.95));o.top_k=int(json_number(body,"top_k",20));o.no_think=json_bool(body,"no_think",false);bool stream=json_bool(body,"stream",false);
          auto t0=std::chrono::steady_clock::now();
          if(stream){sse_start(c);auto out=e.generate(p,o,[&](const std::string & x){sse(c,x);});send_all(c,"data: [DONE]\n\n");}
          else{auto out=e.generate(p,o,[&](const std::string &){});auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();std::ostringstream b;b<<"{\"id\":\"fuse-local\",\"object\":\"chat.completion\",\"model\":\""<<json_escape(e.identity.filename)<<"\",\"choices\":[{\"index\":0,\"message\":{\"role\":\"assistant\",\"content\":\""<<json_escape(out)<<"\"},\"finish_reason\":\"stop\"}],\"fuse\":{\"latency_ms\":"<<ms<<"}}";send_all(c,http_response(200,b.str()));}
        }else send_all(c,http_response(404,"{\"error\":\"NOT_FOUND\"}"));
      }catch(const std::exception & ex){send_all(c,http_response(400,"{\"error\":\""+json_escape(ex.what())+"\"}"));}socket_close(c);}
}

int main(int argc,char ** argv){
  try{
    auto cfg=parse_args(argc,argv);cfg.serve=true;Engine e;e.cfg=cfg;e.init();
    std::filesystem::path p=cfg.model_path.empty()?auto_discover_gguf(model_roots()):std::filesystem::path(cfg.model_path);
    if(!p.empty())e.load_path(p.string());
    return serve(e);
  }catch(const std::exception & ex){std::cerr<<"FUSE LocalLLM error: "<<ex.what()<<"\n";return 1;}
}
