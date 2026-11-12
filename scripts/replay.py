"""Step 3. Send the saved messages through a sandbox on one or more models and save every reply.
Only ever posts to the sandbox URL in config.json. Results hold real customer messages: <data_dir>/runs/.

    python3 replay.py myagent-test --models gpt-6-sol --last 3          # smoke test first
    python3 replay.py myagent-test --models gpt-6-sol                   # everything harvested
    python3 replay.py myagent-test --models gpt-6-sol --set testset.json  # a saved set (see testset.example.json)
"""
import argparse, json, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from common import config, data_path, read_jsonl


def post(url, model, body):
    t = time.time()
    req = urllib.request.Request(f"{url}?model={model}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        out = {"error": f"HTTP {e.code}: {e.read()[:500].decode(errors='replace')}"}
    except Exception as e:
        out = {"error": repr(e)}
    if isinstance(out, list):
        out = out[0] if out else {}
    out["wall_ms"] = int((time.time() - t) * 1000)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sandbox"); ap.add_argument("--models", required=True)
    ap.add_argument("--set"); ap.add_argument("--last", type=int); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    cfg = config()
    sb = cfg["sandboxes"][a.sandbox]
    agent = cfg["agents"][sb["agent"]]
    field = agent["message_field"]
    H = [h for h in read_jsonl(data_path(cfg, "harvest", f"{sb['agent']}.jsonl")) if h["body"] and h["reply_old"]]
    if a.set:
        ts, byid = json.load(open(a.set)), {h["execution_id"]: h for h in H}
        written = []
        for s in ts.get("written", []):  # an edge case you wrote, sent with a real message's context
            b = dict(byid[str(s["template_execution"])]["body"]); b[field] = s["message"]
            written.append({"execution_id": s["id"], "body": b, "reply_old": None})
        keep = {str(i) for i in ts.get("execution_ids", [])}
        H = [h for h in H if h["execution_id"] in keep] + written
    elif a.last:
        H = H[-a.last:]
    models = a.models.split(",")
    jobs = [(h, m) for h in H for m in models]
    print(f"{len(H)} messages x {len(models)} models = {len(jobs)} sandbox runs")
    out = data_path(cfg, "runs", f"{a.sandbox}-{datetime.now():%Y%m%d-%H%M%S}.jsonl")
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda j: post(sb["webhook_url"], j[1], j[0]["body"]), jobs))
    with open(out, "w") as f:
        for (h, m), r in zip(jobs, res):
            f.write(json.dumps({"source_execution": h["execution_id"], "model": m, "message": h["body"].get(field),
                                "reply_old": h["reply_old"], "result": r}) + "\n")
    errs = [r for r in res if r.get("error")]
    ms = sorted(r["wall_ms"] for r in res)
    print(f"saved {out}\nerrors: {len(errs)} of {len(res)}   median {ms[len(ms) // 2] if ms else 0} ms")
    if errs:
        print("first error:", str(errs[0]["error"])[:300])


if __name__ == "__main__":
    main()
