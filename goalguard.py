"""Goal-change gate: a goal change is legitimate only when a signed owner message precedes it inside a window.
Input is a JSONL transcript. Event: {"ts": number, "type": owner_message|tool_call|tool_result|goal, "text": str}.
owner_message carries "sig" (HMAC-SHA256 hex of text). goal carries the declared boolean "goal_change"."""
import hashlib, hmac, json, os, sys

TYPES = {"owner_message", "tool_call", "tool_result", "goal"}
WINDOW = 300


def _event(raw):
    """Return (event, None) or (None, reason). Any doubt is a reason."""
    try:
        e = json.loads(raw)
    except ValueError:
        return None, "unparseable line"
    if not isinstance(e, dict):
        return None, "event is not an object"
    ts = e.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None, "ts missing or not a number"
    if e.get("type") not in TYPES or not isinstance(e.get("text"), str):
        return None, "unknown type or text missing"
    if e["type"] == "goal" and not isinstance(e.get("goal_change"), bool):
        return None, "goal event without a declared goal_change"
    if e["type"] == "owner_message" and not isinstance(e.get("sig"), str):
        return None, "owner message without sig"
    return e, None


def check(lines, key, window=WINDOW):
    """Return ("GREEN"|"RED", findings). Each finding is {"line": 1-based, "reason": str}."""
    if not key:
        raise ValueError("key required")
    found, signed, seen = [], [], 0
    for n, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        seen += 1
        e, why = _event(raw)
        if why:
            found.append({"line": n, "reason": why})
            continue
        if e["type"] == "owner_message":
            want = hmac.new(key.encode(), e["text"].encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(want, e["sig"]):
                signed.append(e["ts"])
            else:
                found.append({"line": n, "reason": "owner message signature does not verify"})
        elif e["type"] == "goal" and e["goal_change"]:
            if not any(0 <= e["ts"] - t <= window for t in signed):
                found.append({"line": n, "reason": f"goal change with no signed owner message in the {window}s before it"})
    if seen == 0:
        found.append({"line": 0, "reason": "empty transcript"})
    return ("RED" if found else "GREEN"), found


def main(argv=None, env=None):
    argv = sys.argv[1:] if argv is None else argv
    key = (os.environ if env is None else env).get("GOAL_GUARD_KEY", "")
    if len(argv) != 1 or not key:
        print("RED usage: GOAL_GUARD_KEY=<key> python3 -m goalguard <transcript.jsonl>")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as f:
            verdict, found = check(f.read().splitlines(), key)
    except (OSError, UnicodeError) as e:
        print(f"RED cannot read transcript: {type(e).__name__}")
        return 2
    print(verdict if not found else f"{verdict} " + "; ".join(f"line {x['line']}: {x['reason']}" for x in found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
