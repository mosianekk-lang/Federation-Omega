from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass(frozen=True)
class DeadlinePhase:
    phase_id: str
    offset_days: int
    action: str
    required: bool=True

DEFAULT_PHASES=(
 DeadlinePhase('T14',14,'CHECK_MISSING_EVIDENCE'),
 DeadlinePhase('T10',10,'PREPARE_FIRST_COMPLETE_DRAFT'),
 DeadlinePhase('T7',7,'CONTRADICTION_AND_COMPLETENESS_AUDIT'),
 DeadlinePhase('T3',3,'FINAL_VERIFICATION_AND_REHEARSAL'),
 DeadlinePhase('T1',1,'READINESS_PACKET_AND_CONTINGENCY_CHECK'),
 DeadlinePhase('T0',0,'DEADLINE_EXECUTION_READINESS'),
)
@dataclass(frozen=True)
class DeadlineTask:
    phase_id: str
    due_at: str
    action: str
    state: str
    lateness_seconds: int

class AutonomousDeadlineEngine:
    def __init__(self,phases=DEFAULT_PHASES): self.phases=tuple(sorted(phases,key=lambda p:-p.offset_days))
    def plan(self,deadline:datetime,now:datetime):
        if deadline.tzinfo is None or now.tzinfo is None: raise ValueError('TIMEZONE_AWARE_REQUIRED')
        tasks=[]
        for p in self.phases:
            due=deadline-timedelta(days=p.offset_days); delta=(now-due).total_seconds()
            state='DUE_NOW' if due<=now<deadline else 'MISSED_WINDOW' if now>=deadline and due<deadline else 'UPCOMING'
            tasks.append(DeadlineTask(p.phase_id,due.isoformat(),p.action,state,max(0,int(delta))))
        return tuple(tasks)
    def next_due(self,deadline,now):
        tasks=self.plan(deadline,now); future=[t for t in tasks if t.state=='UPCOMING']
        return min(future,key=lambda t:t.due_at) if future else None
    def cadence_ceiling_seconds(self,deadline:datetime,now:datetime):
        sec=(deadline-now).total_seconds()
        if sec<=3600:return 300
        if sec<=86400:return 900
        if sec<=7*86400:return 3600
        return 14400
