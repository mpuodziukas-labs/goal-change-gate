"""Mutation check: remove each defense in a scratch copy, the matching tests must go RED.
A control copy must pass first. A mutant that hangs past 8 s counts as killed."""
import pathlib, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).parent
T = "tests/test_guard.py"
# (name, file, text to remove, text to put in, test file that must fail)
MUTANTS = [
    ("hmac: skip the signature check", "goalguard.py", "if hmac.compare_digest(want, e[\"sig\"]):", "if True:", T),
    ("hmac: sign a constant, not the text", "goalguard.py", "key.encode(), e[\"text\"].encode()", "key.encode(), b\"x\"", T),
    ("hmac: accept an empty key", "goalguard.py", "    if not key:", "    if False:", T),
    ("window: no upper bound, a replayed message counts", "goalguard.py", "0 <= e[\"ts\"] - t <= window", "0 <= e[\"ts\"] - t", T),
    ("window: no lower bound, a later message counts", "goalguard.py", "0 <= e[\"ts\"] - t <= window", "e[\"ts\"] - t <= window", T),
    ("window: edge off by one", "goalguard.py", "0 <= e[\"ts\"] - t <= window", "0 <= e[\"ts\"] - t < window", T),
    ("empty: an empty transcript is green", "goalguard.py", "    if seen == 0:", "    if False:", T),
    ("empty: an unparseable line is skipped", "goalguard.py", "found.append({\"line\": n, \"reason\": why})", "pass", T),
    ("goal: ignore the declared goal_change", "goalguard.py", "elif e[\"type\"] == \"goal\" and e[\"goal_change\"]:", "elif e[\"type\"] == \"goal\" and False:", T),
    ("goal: goal_change field optional", "goalguard.py", "if e[\"type\"] == \"goal\" and not isinstance(e.get(\"goal_change\"), bool):", "if False:", T),
    ("cli: an unreadable file exits 0", "goalguard.py", "        return 2\n    print(verdict", "        return 0\n    print(verdict", T),
]


def pytest_rc(tree, test):
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", test],
                           cwd=tree, capture_output=True, timeout=8,
                           env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    except subprocess.TimeoutExpired:
        return 124                                      # a mutant that hangs the tests is caught
    return r.returncode


def fresh(tmp, name):
    dst = pathlib.Path(tmp) / name
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    return dst


def main():
    killed = 0
    tests = sorted({m[4] for m in MUTANTS})
    with tempfile.TemporaryDirectory() as tmp:
        for t in tests:
            if pytest_rc(fresh(tmp, "control-" + pathlib.Path(t).stem), t) != 0:
                print(f"control FAIL {t}"); return 1
        print(f"control {len(tests)}/{len(tests)} test files pass unmodified")
        for i, (name, f, old, new, test) in enumerate(MUTANTS):
            tree = fresh(tmp, f"m{i}")
            src = (tree / f).read_text()
            if src.count(old) != 1:
                print(f"mutant {name}: pattern matched {src.count(old)} times, want 1"); return 1
            (tree / f).write_text(src.replace(old, new))
            red = pytest_rc(tree, test) != 0
            killed += red
            print(f"{'RED ' if red else 'LIVE'} {name}")
    print(f"mutants killed {killed}/{len(MUTANTS)}")
    return 0 if killed == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main())
