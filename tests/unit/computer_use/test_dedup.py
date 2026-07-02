from test_smoke import load
dedup = load("dedup")


def test_hamming():
    assert dedup.hamming(0b1010, 0b1000) == 1


def test_retain_keeps_every_explored_screen():
    # H1: the critic must see EVERY screen the run reached, not just endpoints + problem steps.
    # A successful mid-run navigation lands on a new screen whose post-action shot is exactly what
    # a visual-issue finder should critique — so a plain successful step is retained too.
    assert dedup.should_retain("rejected", False, False) is True
    assert dedup.should_retain("app_left_foreground", False, False) is True
    assert dedup.should_retain("success", True, False) is True    # første
    assert dedup.should_retain("success", False, True) is True    # siste
    assert dedup.should_retain("success", False, False) is True   # mellomsteg → utforsket skjerm, kritiseres


def test_critic_dup_threshold():
    assert dedup.is_critic_dup(0b1111, 0b1111, threshold=2) is True
    assert dedup.is_critic_dup(0b1111, 0b0000, threshold=2) is False
    assert dedup.is_critic_dup(0b1111, None) is False  # ingen forrige
