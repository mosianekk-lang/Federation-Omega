from __future__ import annotations
class FederationDigitalTwin:
    """Read-only impact simulator over the verified project graph."""
    def __init__(self,graph): self.graph=graph
    def simulate_source_stale(self,project_id,source_node):
        affected=self.graph.dependency_closure(project_id,source_node); return {"scenario":"SOURCE_STALE","source_node":source_node,"affected_nodes":affected,"effect_count":len(affected),"mutation_performed":False}
    def simulate_connector_outage(self,missions,connector):
        affected=[m["mission_id"] for m in missions if connector in m.get("active_connectors",[])]; executable=[m["mission_id"] for m in missions if connector not in m.get("active_connectors",[])]; return {"scenario":"CONNECTOR_OUTAGE","connector":connector,"affected_missions":affected,"unaffected_missions":executable,"mutation_performed":False}
    def simulate_mission_complete(self,missions,completed_id):
        unlocked=[]
        for m in missions:
            deps=set(m.get("depends_on",[]))
            if completed_id in deps and deps-{completed_id}==set(m.get("already_complete_dependencies",[])): unlocked.append(m["mission_id"])
        return {"scenario":"MISSION_COMPLETE","mission_id":completed_id,"potentially_unlocked":unlocked,"mutation_performed":False}
