"""Shared helpers. Standard library only. Reads config.json next to this file (or $MODEL_SWITCH_CONFIG).
The n8n API key comes from the N8N_API_KEY environment variable. Never put it in config.json."""
import json, os, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))


def config():
    path = os.environ.get("MODEL_SWITCH_CONFIG", os.path.join(HERE, "config.json"))
    if not os.path.exists(path):
        sys.exit(f"No config at {path}. Copy config.example.json to config.json and fill it in.")
    cfg = json.load(open(path))
    cfg["data_dir"] = os.path.expanduser(cfg.get("data_dir", "~/model-switch-data"))
    return cfg


def data_path(cfg, *parts):
    p = os.path.join(cfg["data_dir"], *parts)
    os.makedirs(os.path.dirname(p) if "." in os.path.basename(p) else p, exist_ok=True)
    return p


def n8n(cfg, method, path, body=None, allow_fail=False):
    key = os.environ.get("N8N_API_KEY")
    if not key:
        sys.exit("Set N8N_API_KEY in your shell first (n8n > Settings > n8n API).")
    req = urllib.request.Request(f"{cfg['n8n_base'].rstrip('/')}/api/v1/{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-N8N-API-KEY": key, "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if allow_fail:
            return None
        sys.exit(f"n8n {method} {path} -> HTTP {e.code}: {e.read()[:400].decode(errors='replace')}")


def n8n_paged(cfg, path, limit=250, max_items=None):
    out, cursor = [], None
    while True:
        sep = "&" if "?" in path else "?"
        d = n8n(cfg, "GET", f"{path}{sep}limit={limit}" + (f"&cursor={cursor}" if cursor else ""))
        out += d.get("data", [])
        cursor = d.get("nextCursor")
        if not cursor or (max_items and len(out) >= max_items):
            return out[:max_items] if max_items else out


def first_json(run):
    try:
        return run["data"]["main"][0][0]["json"]
    except (KeyError, IndexError, TypeError):
        return None


def read_jsonl(path):
    return [json.loads(l) for l in open(path) if l.strip()]
