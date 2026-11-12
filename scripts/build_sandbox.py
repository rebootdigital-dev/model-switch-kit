"""Step 2. Build a no-send SANDBOX copy of a live n8n agent workflow. The live workflow is only read.

What the copy changes:
  - new webhook path that answers with the last node's JSON, so replay.py reads the reply directly
  - the agent's chat model comes from ?model=<id> on the URL (default: old_model in config.json)
  - every node that could send, write or call out is removed. Anything not on the SAFE list below stops the
    build until you name it under drop_nodes or keep_nodes in config.json
  - the agent's output goes to one RESULT node instead of your CRM write
  - an agent error comes back as data instead of a failed call

    python3 build_sandbox.py myagent                 # dry run: prints the plan, creates nothing
    python3 build_sandbox.py myagent --go            # creates it, inactive
    python3 build_sandbox.py myagent --agent-v2 --go # also upgrade an old (v1) n8n agent node to v2.2
    python3 build_sandbox.py myagent --prompt new-prompt.txt --label fixes --go   # test a changed prompt
    python3 build_sandbox.py myagent --from-file export.json   # dry run on an exported workflow, no API call

After --go: open it in n8n, look it over, activate it, and paste the printed URL into config.json under sandboxes.
Anyone with that URL can spend your OpenAI credits. Deactivate the sandbox when testing is done.
"""
import copy, json, sys, uuid
from common import config, n8n

SAFE = ("n8n-nodes-base.webhook", "n8n-nodes-base.set", "n8n-nodes-base.if", "n8n-nodes-base.switch",
        "n8n-nodes-base.filter", "n8n-nodes-base.merge", "n8n-nodes-base.noOp", "n8n-nodes-base.code",
        "n8n-nodes-base.stickyNote", "n8n-nodes-base.dateTime", "n8n-nodes-base.wait",
        "@n8n/n8n-nodes-langchain.agent", "@n8n/n8n-nodes-langchain.lmChat",
        "@n8n/n8n-nodes-langchain.textClassifier", "@n8n/n8n-nodes-langchain.outputParser",
        "@n8n/n8n-nodes-langchain.memoryBufferWindow")
RESULT, SKIPPED = "RESULT - reply (sandbox, nothing sent)", "RESULT - branch that used a removed node"


def set_node(name, pos, fields):
    return {"id": str(uuid.uuid4()), "name": name, "type": "n8n-nodes-base.set", "typeVersion": 3.4,
            "position": pos, "parameters": {"mode": "manual", "includeOtherFields": False, "assignments": {
                "assignments": [{"id": str(uuid.uuid4()), "name": k, "value": v, "type": "string"} for k, v in fields]}}}


def build(cfg, key, w, agent_v2, prompt, label):
    a = cfg["agents"][key]
    agents, drop, keep = a["agent_nodes"], set(a.get("drop_nodes", [])), set(a.get("keep_nodes", []))
    names = {n["name"] for n in w["nodes"]}
    for n in agents + [a["model_node"]]:
        if n not in names:
            sys.exit(f"'{n}' is not a node in this workflow. Nodes: {sorted(names)}")
    conns = copy.deepcopy(w["connections"])
    # nodes that take the agent's output (the CRM write, switches before it) are replaced by one RESULT node
    post = {e["node"] for ag in agents for outs in conns.get(ag, {}).get("main", []) for e in outs}
    unsure = [n for n in w["nodes"] if n["name"] not in drop | keep | post and not n["type"].startswith(SAFE)]
    if unsure:
        print("STOP. These nodes are not on the safe list. Put each name under drop_nodes (remove it) or")
        print("keep_nodes (you checked it cannot send, write or bill) in config.json, then run again:")
        for n in unsure:
            print(f"   {n['name']:45} {n['type']}")
        sys.exit(1)
    gone = drop | post
    nodes = [n for n in copy.deepcopy(w["nodes"]) if n["name"] not in gone]
    hook = next((n["name"] for n in nodes if n["type"] == "n8n-nodes-base.webhook"), None)
    if not hook:
        sys.exit("No Webhook trigger found. This script expects the agent to start from a webhook.")
    path = f"sandbox-{key}{'-' + label if label else ''}-{uuid.uuid4().hex[:10]}"
    model_expr = "$('%s').item.json.query.model || '%s'" % (hook, cfg.get("old_model", "gpt-4.1"))
    for n in nodes:
        if n["type"] == "n8n-nodes-base.webhook":
            n["parameters"].update(path=path, responseMode="lastNode", options={})
            n["webhookId"] = str(uuid.uuid4())
        if n["name"] == a["model_node"]:
            cur = n["parameters"].get("model")  # newer model nodes store the model as a picker object
            n["parameters"]["model"] = ({"__rl": True, "mode": "id", "value": "={{ %s }}" % model_expr}
                                        if isinstance(cur, dict) else "={{ %s }}" % model_expr)
        if n["name"] in agents:
            n["onError"] = "continueRegularOutput"
            if agent_v2 and n["typeVersion"] < 2:
                # The v1 conversational agent sends a `stop` parameter that newer OpenAI models reject with a 400.
                old = n["parameters"]
                n["typeVersion"] = 2.2
                n["parameters"] = {"promptType": "define", "text": old["text"],
                                   "options": {"systemMessage": old["options"]["systemMessage"]}}
            if prompt:
                n["parameters"].setdefault("options", {})["systemMessage"] = prompt
    for g in gone:
        conns.pop(g, None)
    nodes.append(set_node(RESULT, [1800, 300], [
        ("model", "={{ %s }}" % model_expr), ("raw_output", "={{ $json.output ?? '' }}"),
        ("error", "={{ $json.error ? JSON.stringify($json.error) : '' }}"), ("execution_id", "={{ $execution.id }}")]))
    nodes.append(set_node(SKIPPED, [1800, 0], [
        ("model", "={{ %s }}" % model_expr), ("raw_output", ""), ("route", "ended at a removed node"),
        ("execution_id", "={{ $execution.id }}")]))
    for ag in agents:
        conns.setdefault(ag, {})["main"] = [[{"node": RESULT, "type": "main", "index": 0}]]
    for src, kinds in conns.items():
        for kind, outs_list in kinds.items():
            for outs in outs_list:
                for e in list(outs or []):
                    if e["node"] in gone:
                        if kind == "main" and src not in agents:
                            e["node"] = SKIPPED
                        else:
                            outs.remove(e)
    body = {"name": f"SANDBOX - {w['name']}{' - ' + label if label else ''} (never sends)", "nodes": nodes,
            "connections": conns, "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all"}}
    return body, path, sorted(gone)


if __name__ == "__main__":
    cfg, key = config(), sys.argv[1]
    arg = lambda f: sys.argv[sys.argv.index(f) + 1] if f in sys.argv else ""
    w = json.load(open(arg("--from-file"))) if arg("--from-file") else n8n(cfg, "GET", f"workflows/{cfg['agents'][key]['workflow_id']}")
    prompt = open(arg("--prompt")).read() if arg("--prompt") else ""
    body, path, gone = build(cfg, key, w, "--agent-v2" in sys.argv, prompt, arg("--label"))
    print("name:   ", body["name"])
    print("removed:", gone)
    print("kept:")
    for n in body["nodes"]:
        print(f"   {n['name']:45} {n['type']} v{n['typeVersion']}")
    if "--go" in sys.argv and not arg("--from-file"):
        r = n8n(cfg, "POST", "workflows", body)
        print(f"\nCREATED {r['id']} (inactive). Webhook URL once you activate it:")
        print(f"{cfg['n8n_base'].rstrip('/')}/webhook/{path}")
    else:
        print("\nDry run. Nothing created. Add --go to create it.")
