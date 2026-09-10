"""Synthetic orchestration benchmark. Not a model-intelligence or wall-clock claim."""


def handoff_turns(waves: int) -> int:
    # v3-style output contract: one assistant/user handoff per unfinished wave.
    return waves




def autonomic_turns(waves: int, persistent_runner: bool=True) -> int:
    # v5: one user activation can own all internal cycles when a runner exists.
    return 1 if persistent_runner and waves>0 else waves




def test_20_wave_owner_handoff_reduction_is_at_least_10x():
    baseline=handoff_turns(20); candidate=autonomic_turns(20,True)
    assert baseline/candidate >= 10.0




def test_no_runner_does_not_fake_autonomy():
    assert autonomic_turns(20,False)==20
