"""Run every planted transcript and print one row per attack class. Exit 1 if any verdict or named line is wrong."""
import json, pathlib, sys
from goalguard import check
from fixtures_gen import KEY

HERE = pathlib.Path(__file__).parent


def rows():
    """Return (class, ok) pairs aligned with cases.jsonl, as (class, id, ok)."""
    out = []
    for raw in (HERE / "cases.jsonl").read_text().splitlines():
        c = json.loads(raw)
        text = (HERE / "tests" / "fixtures" / f"{c['file']}.jsonl").read_text()
        verdict, found = check(text.splitlines(), KEY.decode())
        ok = verdict == c["expect"] and (c.get("line") is None or c["line"] in [f["line"] for f in found])
        out.append((c["class"], c["id"], ok))
    return out


def results():
    tally = {}
    for cls, _, ok in rows():
        a = tally.setdefault(cls, [0, 0]); a[0] += ok; a[1] += 1
    lines = ["| class | verdict as labeled |", "|---|---|"] + [f"| {k} | {a}/{b} |" for k, (a, b) in tally.items()]
    return "\n".join(lines)


if __name__ == "__main__":
    print(results())
    sys.exit(0 if rows() and all(ok for *_, ok in rows()) else 1)
