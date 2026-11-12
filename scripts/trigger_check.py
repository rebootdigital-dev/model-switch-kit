"""Step 5. Check which automations each reply would set off. Use it when anything downstream (a GHL workflow,
a Zap, an n8n IF) looks for a phrase in the agent's reply.

triggers.json is a list you write by reading those automations:
    [{"name": "Notify the team", "contains": "sending this to my team"}, {"name": "Stop texting", "contains": "text anymore"}]

    python3 trigger_check.py <runfile.jsonl> triggers.json

Prints, per trigger, how many old-model replies and new-model replies contain the phrase, and lists every message
where the two differ. The match is case-insensitive "contains" on the reply as the model wrote it. If your workflow
cleans the text before it reaches the automation (strips emoji, swaps dashes), apply the same cleanup in clean().
"""
import json, sys
from common import read_jsonl


def clean(text):
    return text or ""


def main():
    rows, trig = read_jsonl(sys.argv[1]), json.load(open(sys.argv[2]))
    diffs = []
    print(f"{'trigger':40} {'old':>5} {'new':>5}")
    for t in trig:
        p, old, new = t["contains"].lower(), 0, 0
        if t["contains"] != t["contains"].strip():
            print(f"  NOTE: '{t['name']}' has a leading or trailing space in its phrase. Check the automation itself.")
        for i, r in enumerate(rows):
            o = r["reply_old"] is not None and p in clean(r["reply_old"]).lower()
            n = p in clean(r["result"].get("raw_output")).lower()
            old, new = old + o, new + n
            if r["reply_old"] is not None and o != n:
                diffs.append((i + 1, t["name"], "old only" if o else "new only", r["message"]))
        print(f"{t['name'][:40]:40} {old:>5} {new:>5}")
    print(f"\n{len(diffs)} differences (read each one; some are the new model being right):")
    for i, name, which, msg in diffs:
        print(f"  #{i:<4} {name[:30]:30} {which:8} | {str(msg)[:90]}")


if __name__ == "__main__":
    main()
