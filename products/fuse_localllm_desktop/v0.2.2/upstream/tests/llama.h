#pragma once
#include <cstdint>
#include <cstddef>
#define LLAMA_DEFAULT_SEED 0xffffffffu
typedef int32_t llama_token;
struct llama_model; struct llama_vocab; struct llama_context; struct llama_sampler;
struct llama_chat_message { const char * role; const char * content; };
struct llama_model_params { int n_gpu_layers; };
struct llama_context_params { uint32_t n_ctx,n_batch,n_ubatch,n_seq_max; int n_threads,n_threads_batch; bool embeddings,offload_kqv,flash_attn,no_perf; };
struct llama_sampler_chain_params { bool no_perf; };
struct llama_batch { int32_t n_tokens; llama_token * token; float * embd; int32_t * pos; int32_t * n_seq_id; int32_t ** seq_id; int8_t * logits; };
void llama_backend_init(); void llama_backend_free();
llama_model_params llama_model_default_params();
llama_context_params llama_context_default_params();
llama_model * llama_model_load_from_file(const char*,llama_model_params);
void llama_model_free(llama_model*);
const llama_vocab * llama_model_get_vocab(const llama_model*);
const char * llama_model_chat_template(const llama_model*,const char*);
int32_t llama_chat_apply_template(const char*,const llama_chat_message*,size_t,bool,char*,int32_t);
int32_t llama_model_desc(const llama_model*,char*,size_t);
int32_t llama_tokenize(const llama_vocab*,const char*,int32_t,llama_token*,int32_t,bool,bool);
llama_context * llama_init_from_model(llama_model*,llama_context_params);
void llama_free(llama_context*);
llama_batch llama_batch_get_one(llama_token*,int32_t);
int32_t llama_decode(llama_context*,llama_batch);
bool llama_vocab_is_eog(const llama_vocab*,llama_token);
int32_t llama_token_to_piece(const llama_vocab*,llama_token,char*,int32_t,int32_t,bool);
llama_sampler_chain_params llama_sampler_chain_default_params();
llama_sampler * llama_sampler_chain_init(llama_sampler_chain_params);
void llama_sampler_chain_add(llama_sampler*,llama_sampler*);
llama_sampler * llama_sampler_init_top_k(int32_t);
llama_sampler * llama_sampler_init_top_p(float,size_t);
llama_sampler * llama_sampler_init_temp(float);
llama_sampler * llama_sampler_init_dist(uint32_t);
llama_token llama_sampler_sample(llama_sampler*,llama_context*,int32_t);
void llama_sampler_free(llama_sampler*);
