#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace fuse {

struct RuntimeConfig {
    std::string model_path;
    std::string host = "127.0.0.1";
    int port = 8999;
    int context = 4096;
    int max_tokens = 512;
    int gpu_layers = 999;
    int threads = 0;
    float temperature = 0.6f;
    float top_p = 0.95f;
    int top_k = 20;
    bool serve = false;
    bool inspect = false;
    bool no_think = false;
};

struct ModelIdentity {
    std::string path;
    std::string filename;
    uint64_t bytes = 0;
    std::string sha256;
};

std::string sha256_file(const std::filesystem::path & path);
std::string json_escape(const std::string & s);
std::string extract_json_string(const std::string & body, const std::string & key);
std::string extract_last_message_content(const std::string & body);
std::string make_chatml_prompt(const std::string & user, bool no_think);
std::filesystem::path auto_discover_gguf(const std::vector<std::filesystem::path> & roots);
RuntimeConfig parse_args(int argc, char ** argv);
ModelIdentity identify_model(const std::filesystem::path & path);
std::string runtime_receipt_json(const RuntimeConfig & cfg, const ModelIdentity & model, const std::string & backend);
}