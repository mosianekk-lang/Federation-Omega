---------------- MODULE FormationOmegaReconciliationV2 ----------------
EXTENDS Naturals, Sequences, TLC

CONSTANTS Main0, Head0, Main1, Head1

VARIABLES main,
          head,
          checkedHead,
          permitMain,
          permitHead,
          semanticConflict,
          rollbackAvailable,
          externalEffect,
          authority,
          merged,
          closed

vars == <<main, head, checkedHead, permitMain, permitHead,
          semanticConflict, rollbackAvailable, externalEffect,
          authority, merged, closed>>

Init ==
    /\ main = Main0
    /\ head = Head0
    /\ checkedHead = Head0
    /\ permitMain = Main0
    /\ permitHead = Head0
    /\ semanticConflict = FALSE
    /\ rollbackAvailable = TRUE
    /\ externalEffect = FALSE
    /\ authority = "A1_INTERNAL"
    /\ merged = FALSE
    /\ closed = FALSE

RefreshMain ==
    /\ ~merged
    /\ main' = Main1
    /\ UNCHANGED <<head, checkedHead, permitMain, permitHead,
                   semanticConflict, rollbackAvailable, externalEffect,
                   authority, merged, closed>>

MoveHead ==
    /\ ~merged
    /\ head' = Head1
    /\ UNCHANGED <<main, checkedHead, permitMain, permitHead,
                   semanticConflict, rollbackAvailable, externalEffect,
                   authority, merged, closed>>

Recheck ==
    /\ ~merged
    /\ checkedHead' = head
    /\ permitMain' = main
    /\ permitHead' = head
    /\ UNCHANGED <<main, head, semanticConflict, rollbackAvailable,
                   externalEffect, authority, merged, closed>>

SetConflict ==
    /\ ~merged
    /\ semanticConflict' = TRUE
    /\ UNCHANGED <<main, head, checkedHead, permitMain, permitHead,
                   rollbackAvailable, externalEffect, authority, merged, closed>>

LoseRollback ==
    /\ ~merged
    /\ rollbackAvailable' = FALSE
    /\ UNCHANGED <<main, head, checkedHead, permitMain, permitHead,
                   semanticConflict, externalEffect, authority, merged, closed>>

AttemptExternalEffect ==
    /\ ~merged
    /\ externalEffect' = TRUE
    /\ UNCHANGED <<main, head, checkedHead, permitMain, permitHead,
                   semanticConflict, rollbackAvailable, authority, merged, closed>>

Merge ==
    /\ ~merged
    /\ ~semanticConflict
    /\ rollbackAvailable
    /\ main = permitMain
    /\ head = permitHead
    /\ checkedHead = head
    /\ ~externalEffect
    /\ merged' = TRUE
    /\ UNCHANGED <<main, head, checkedHead, permitMain, permitHead,
                   semanticConflict, rollbackAvailable, externalEffect,
                   authority, closed>>

Close ==
    /\ merged
    /\ ~closed
    /\ rollbackAvailable
    /\ ~semanticConflict
    /\ closed' = TRUE
    /\ UNCHANGED <<main, head, checkedHead, permitMain, permitHead,
                   semanticConflict, rollbackAvailable, externalEffect,
                   authority, merged>>

Next == RefreshMain \/ MoveHead \/ Recheck \/ SetConflict \/ LoseRollback \/ AttemptExternalEffect \/ Merge \/ Close

Spec == Init /\ [][Next]_vars

NoMergeOnSemanticConflict == semanticConflict => ~merged
NoStalePermitMerge == merged => (main = permitMain /\ head = permitHead /\ checkedHead = head)
NoA1ExternalEffectAtMerge == (authority = "A1_INTERNAL" /\ externalEffect) => ~merged
RollbackRequiredForMerge == merged => rollbackAvailable
ClosureRequiresMerge == closed => merged
ClosureRequiresRollback == closed => rollbackAvailable
ClosureExcludesConflict == closed => ~semanticConflict

Safety ==
    /\ NoMergeOnSemanticConflict
    /\ NoStalePermitMerge
    /\ NoA1ExternalEffectAtMerge
    /\ RollbackRequiredForMerge
    /\ ClosureRequiresMerge
    /\ ClosureRequiresRollback
    /\ ClosureExcludesConflict

=============================================================================
