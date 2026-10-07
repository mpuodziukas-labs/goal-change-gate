import json, pathlib, subprocess, sys
import pytest
from goalguard import check
from fixtures_gen import KEY, sig, owner, ev, goal

FIX = pathlib.Path(__file__).parent / "fixtures"
ROOT = pathlib.Path(__file__).parent.parent
K = KEY.decode()


def run(name, **kw):
    return check((FIX / f"{name}.jsonl").read_text().splitlines(), K, **kw)


def lines(*events):
    return [json.dumps(e) for e in events]


def test_owner_message_then_goal_change_is_green():
    assert run("green_owner_then_goal") == ("GREEN", [])


def test_goal_event_that_declares_no_change_needs_no_owner():
    assert run("green_no_goal_change")[0] == "GREEN"


def test_goal_change_after_tool_result_is_red_and_names_the_event():
    verdict, found = run("red_tool_result_then_goal")
    assert verdict == "RED" and [f["line"] for f in found] == [5]
    assert "no signed owner message" in found[0]["reason"]


def test_forged_owner_message_is_red():
    verdict, found = run("red_forged_owner")
    assert verdict == "RED" and [f["line"] for f in found] == [5, 6]   # the forgery and the change it tried to excuse


def test_replayed_owner_message_outside_window_is_red():
    verdict, found = run("red_replayed_owner")
    assert verdict == "RED" and [f["line"] for f in found] == [5]


def test_window_boundary_300_is_green_301_is_red():
    assert run("green_window_edge")[0] == "GREEN"
    assert run("red_window_edge_plus_one")[0] == "RED"


def test_window_is_a_parameter():
    assert run("green_window_edge", window=299)[0] == "RED"


def test_owner_message_after_the_change_does_not_excuse_it():
    assert run("red_owner_after_goal")[0] == "RED"


def test_empty_transcript_is_red_not_green():
    assert run("red_empty")[0] == "RED"
    assert check([], K)[0] == "RED"
    assert check(["", "  "], K)[0] == "RED"


def test_unparseable_line_is_red_and_named():
    verdict, found = run("red_unparseable")
    assert verdict == "RED" and [f["line"] for f in found] == [2]


@pytest.mark.parametrize("bad", ['[1, 2]', '"text"', '{"type": "goal"}', '{"ts": "x", "type": "goal", "text": "t", "goal_change": true}',
                                 '{"ts": 1, "type": "goal", "text": "t"}', '{"ts": 1, "type": "wat", "text": "t"}',
                                 '{"ts": 1, "type": "owner_message", "text": "t"}',
                                 '{"ts": true, "type": "goal", "text": "t", "goal_change": false}'])
def test_malformed_events_are_red(bad):
    assert check([bad], K)[0] == "RED"


def test_no_events_but_owner_messages_is_not_green_by_default_of_silence():
    assert check(lines(owner(1, "hello")), K)[0] == "GREEN"      # control: a valid log with no change is fine


def test_signature_covers_the_text_not_just_the_shape():
    forged = dict(owner(100, "Switch to invoices."), text="Switch to refunds.")
    verdict, _ = check(lines(forged, goal(105, "Goal: refunds.")), K)
    assert verdict == "RED"


def test_wrong_key_is_red_and_empty_key_is_refused():
    log = lines(owner(100, "Switch."), goal(105, "Goal: x."))
    assert check(log, K)[0] == "GREEN"
    assert check(log, "another-key")[0] == "RED"
    with pytest.raises(ValueError):
        check(log, "")


def test_each_unexplained_change_is_named():
    log = lines(goal(10, "g1"), goal(20, "g2", change=False), goal(30, "g3"), ev(31, "tool_result", "x"), goal(40, "g4"))
    verdict, found = check(log, K)
    assert verdict == "RED" and [f["line"] for f in found] == [1, 3, 5]


def cli(path, key=K, *extra):
    return subprocess.run([sys.executable, "-m", "goalguard", str(path), *extra], cwd=ROOT, capture_output=True, text=True,
                          env={"GOAL_GUARD_KEY": key, "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"} if key is not None else {"PATH": "/usr/bin:/bin"})


def test_cli_exit_codes_and_named_event():
    assert cli(FIX / "green_owner_then_goal.jsonl").returncode == 0
    r = cli(FIX / "red_tool_result_then_goal.jsonl")
    assert r.returncode == 1 and "RED" in r.stdout and "line 5" in r.stdout


def test_cli_missing_file_or_missing_key_is_red_never_green():
    assert cli(FIX / "does_not_exist.jsonl").returncode != 0
    assert cli(FIX / "green_owner_then_goal.jsonl", key=None).returncode != 0
    assert cli(FIX / "red_empty.jsonl").returncode == 1


def test_owner_message_stamped_after_the_change_does_not_excuse_it_even_if_listed_first():
    log = lines(owner(2000, "Switch."), goal(1990, "Goal: x."))
    assert check(log, K)[0] == "RED"
