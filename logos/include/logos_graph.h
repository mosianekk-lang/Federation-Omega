#pragma once
#include "logos_store.h"
namespace logos {
struct NodeEntry{std::string semantic_id;u64 revision{};Digest256 revision_digest{};NodeType type{};Lifecycle lifecycle{};};
struct EdgeEntry{std::string canonical_key;Digest256 edge_digest{};std::string from_id,to_id,scope;RelationCode relation{};};
struct GraphState{std::map<std::string,NodeEntry> nodes;std::map<std::string,EdgeEntry> edges;std::vector<Digest256> rejections;};
Status graph_apply_event(GraphState*,const ObjectStore*,const LglRecord&);Status graph_replay(const ObjectStore*,const Ledger&,GraphState*);Status graph_root(const GraphState&,Digest256*);Status graph_get_node(const GraphState&,std::string_view,const NodeEntry**);Status graph_load_node(const GraphState&,const ObjectStore&,std::string_view,Buffer*,LgoObjectView*);Status graph_add_node(ObjectStore*,Ledger*,GraphState*,ByteSpan,Digest256*);Status graph_revise_node(ObjectStore*,Ledger*,GraphState*,ByteSpan,Digest256*);Status graph_add_edge(ObjectStore*,Ledger*,GraphState*,ByteSpan,Digest256*);Status graph_record_rejection(ObjectStore*,Ledger*,GraphState*,ByteSpan,Digest256*);Status graph_validate_node_contract(const GraphState&,const ObjectStore&,const LgoObjectView&);Status detect_contradictions(GraphState*,ObjectStore*,Ledger*);Status compile_canon_view(GraphState*,ObjectStore*,Ledger*,Digest256*);Status compile_proof_view(GraphState*,ObjectStore*,Ledger*,std::string_view,Digest256*);Status graph_count_type(const GraphState&,NodeType,u64*);
}
