"""Step 1. Save real inbound messages and the reply the OLD model actually sent, from n8n's kept executions.

n8n only keeps executions for a while (often 2 to 3 weeks), so run this now and again every week until you
switch. It only reads. It appends new executions and skips ones it already saved.
Output holds real customer messages: <data_dir>/harvest/<agent>.jsonl. Keep that folder out of git and Drive shares.

    python3 harvest.py                # every agent in config.json
    python3 harvest.py myagent        # one
    python3 harvest.py myagent --limit 5   # quick check that the node names in config are right
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from common import config, data_path, n8n, n8n_paged, first_json


def extract(cfg, eid, agent_nodes):
    d = n8n(cfg, "GET", f"executions/{eid}?includeData=true", allow_fail=True) or {}
    rd = (d.get("data") or {}).get("resultData", {}).get("runData", {})
    hook = next((v for k, v in rd.items() if k.lower().startswith("webhook")), None)
    body = (first_json(hook[0]) or {}).get("body") if hook else None
    rec = {"execution_id": str(eid), "started": d.get("startedAt"), "status": d.get("status"), "body": body,
           "agent": None, "reply_old": None, "model": None, "tokens": None, "latency_ms": None}
    for name in agent_nodes:
        if name in rd:
            out = first_json(rd[name][0]) or {}
            rec.update(agent=name, reply_old=out.get("output"), latency_ms=rd[name][0].get("executionTime"))
    for runs in rd.values():
        for run in runs:
            lm = (run.get("data") or {}).get("ai_languageModel")
            src = (run.get("source") or [{}])[0].get("previousNode")
            if lm and src in agent_nodes:
                j = lm[0][0]["json"]
                gen = j.get("response", {}).get("generations", [[{}]])[0][0]
                rec["model"] = (gen.get("generationInfo") or {}).get("model_name")
                rec["tokens"] = j.get("tokenUsage")
    return rec


def harvest(cfg, key, limit):
    a = cfg["agents"][key]
    path = data_path(cfg, "harvest", f"{key}.jsonl")
    seen = {r["execution_id"] for r in (json.loads(l) for l in open(path))} if os.path.exists(path) else set()
    ids = [str(e["id"]) for e in n8n_paged(cfg, f"executions?workflowId={a['workflow_id']}", max_items=limit)]
    ids = [i for i in ids if i not in seen]
    with ThreadPoolExecutor(8) as ex:
        recs = list(ex.map(lambda i: extract(cfg, i, a["agent_nodes"]), ids))
    recs.sort(key=lambda r: r["started"] or "")
    with open(path, "a") as f:
        f.writelines(json.dumps(r) + "\n" for r in recs)
    replied = sum(1 for r in recs if r["reply_old"])
    nobody = sum(1 for r in recs if not r["body"])
    print(f"{key:14} new={len(recs):4}  with a reply={replied:4}  no webhook body={nobody:4}  total={len(seen) + len(recs)}")
    if recs and not replied:
        print("  0 replies found. Check agent_nodes in config.json against the node names in the workflow.")


if __name__ == "__main__":
    cfg = config()
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    keys = [k for k in sys.argv[1:] if k in cfg["agents"]] or list(cfg["agents"])
    for k in keys:
        harvest(cfg, k, limit)
