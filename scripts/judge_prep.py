"""Step 4. Turn a replay run into slices for grading. Each item has the message, recent context, the old model's
reply, the new model's reply and mechanical flags. Graders read a slice plus the live prompt (see ../judge-prompt.md).

    python3 judge_prep.py <runfile.jsonl> [--slices 4]
"""
import json, os, sys
from common import config, data_path, read_jsonl


def flags(raw, err):
    f, s = [], (raw or "").strip()
    if err: f.append("RUN_ERROR")
    if not s and not err: f.append("EMPTY")
    if "action_input" in s or s.startswith("{") or s.startswith("```"): f.append("JSON_OR_CODE_LEAK")
    if any(m in s for m in ("**", "##", "](")): f.append("MARKDOWN")
    if "\n" in s: f.append("LINE_BREAK")
    if len(s) > 480: f.append("LONG")
    return f


def main():
    cfg, run = config(), sys.argv[1]
    arg = lambda fl, d: sys.argv[sys.argv.index(fl) + 1] if fl in sys.argv else d
    n = int(arg("--slices", 4))
    tag = os.path.basename(run).replace(".jsonl", "")
    sandbox = next(k for k in sorted(cfg["sandboxes"], key=len, reverse=True) if tag.startswith(k))
    agent = cfg["sandboxes"][sandbox]["agent"]
    ctx = cfg["agents"][agent].get("context_fields", [])
    H = {h["execution_id"]: h for h in read_jsonl(data_path(cfg, "harvest", f"{agent}.jsonl"))}
    items = []
    for i, r in enumerate(read_jsonl(run)):
        x, body = r["result"], (H.get(r["source_execution"]) or {}).get("body") or {}
        items.append({"item": i + 1, "source_execution": r["source_execution"],
                      "written_edge_case": r["reply_old"] is None, "message": r["message"],
                      "context_tail": {k: str(body.get(k) or "")[-1500:] for k in ctx},
                      "reply_old": r["reply_old"], "reply_new": x.get("raw_output"), "model": r["model"],
                      "flags": flags(x.get("raw_output"), x.get("error"))})
    out = data_path(cfg, "judge", tag)
    k = -(-len(items) // n)
    for s in range(n):
        json.dump(items[s * k:(s + 1) * k], open(f"{out}/slice-{s + 1}.json", "w"), indent=1, ensure_ascii=False)
    counts = {}
    for it in items:
        for f in it["flags"]: counts[f] = counts.get(f, 0) + 1
    print(out, "|", len(items), "items |", counts or "no flags")


if __name__ == "__main__":
    main()
