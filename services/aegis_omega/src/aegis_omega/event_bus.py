from __future__ import annotations
import json
from .schemas import Assessment
class NullEventBus:
    def publish_assessment(self,assessment:Assessment)->None:return None
class PubSubEventBus:
    def __init__(self,project:str,topic:str):
        from google.cloud import pubsub_v1
        self.publisher=pubsub_v1.PublisherClient(); self.topic_path=topic if topic.startswith("projects/") else self.publisher.topic_path(project,topic)
    def publish_assessment(self,assessment:Assessment)->str:
        payload=json.dumps({"type":"aegis.assessment","case_id":assessment.case_id,"idempotency_key":f"aegis.assessment:{assessment.case_id}","risk_score":assessment.risk_score,"confidence":assessment.confidence,"disposition":assessment.disposition},sort_keys=True).encode()
        return str(self.publisher.publish(self.topic_path,payload,event_type="aegis.assessment",case_id=assessment.case_id).result(timeout=10))
def build_event_bus(project:str,topic:str):return PubSubEventBus(project,topic) if project and topic else NullEventBus()
