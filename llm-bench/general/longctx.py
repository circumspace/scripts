import json, os, random, sys, time, urllib.request

BASE = os.environ.get("LLAMA_SWAP", "http://localhost:8080")
LABEL = sys.argv[1]
TARGET = int(sys.argv[2]) if len(sys.argv) > 2 else 70000
REPEATS = 3
MODEL = os.environ.get("MODEL", "default")


def fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


TOOLS = [
    fn("read_file", "Read a file from the repository", {"path": {"type": "string"}}, ["path"]),
    fn("run_command", "Run a shell command in the repository", {"cmd": {"type": "string"}}, ["cmd"]),
    fn("upload_file", "Upload a file to an object storage bucket", {"bucket": {"type": "string"}, "path": {"type": "string"}}, ["bucket", "path"]),
]

WORDS = ("request handler cache retry timeout worker queue shard replica index token session buffer "
         "schema migration payload checksum lease backoff cursor snapshot ledger invoice batch").split()


def filler_file(rng, n):
    lines = []
    for i in range(n):
        a, b, c = rng.sample(WORDS, 3)
        lines.append(f"    def {a}_{b}_{i}(self, {c}):\n        return self._{b}.get({c!r}, {rng.randint(0, 9999)})")
    return "class Service:\n" + "\n".join(lines)


def filler_log(rng, n):
    return "\n".join(f"2026-10-0{rng.randint(1, 9)}T{rng.randint(10, 23)}:{rng.randint(10, 59)}:{rng.randint(10, 59)} "
                     f"{rng.choice(['INFO', 'DEBUG', 'WARN'])} {rng.choice(WORDS)}: {rng.choice(WORDS)} {rng.randint(1, 99999)} "
                     f"in {rng.randint(1, 900)}ms" for _ in range(n))


def call(i, name, args):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def result(i, text):
    return {"role": "tool", "tool_call_id": f"call_{i}", "content": text}


def transcript(blocks):
    rng = random.Random(7)
    msgs = [{"role": "system", "content": "You are a coding agent working in the user's repository. Use the tools when needed."},
            {"role": "user", "content": "We're chasing flaky failures in the billing service. Mirela is on call this week, so route anything urgent to her. Start by reading the config."},
            call(0, "read_file", {"path": "config/billing.env"}),
            result(0, "DB_HOST=billing-db.internal\nDB_PORT=54328\nDB_POOL=20\nCACHE_TTL=300\nQUEUE=billing-events")]
    facts = {int(blocks * 0.5): [
                {"role": "user", "content": "Important for later: never upload anything to the bucket orchid-77, that's the old staging bucket. Use basalt-12 for all uploads."},
                {"role": "assistant", "content": "Understood: uploads go to basalt-12, never orchid-77."}],
             int(blocks * 0.6): [
                call(9001, "run_command", {"cmd": "git show --stat HEAD"}),
                result(9001, "commit 4f1c2e9\n    Move billing DB to the new cluster\n\n config/billing.env | 2 +-\n\n-DB_PORT=54328\n+DB_PORT=54329")],
             int(blocks * 0.8): [
                call(9002, "run_command", {"cmd": "pytest tests/billing -q"}),
                result(9002, "..........F.....F..........F....\nFAILED tests/billing/test_ledger.py::test_rollover_rounding\n"
                             "FAILED tests/billing/test_invoice.py::test_batch_retry_backoff\nFAILED tests/billing/test_queue.py::test_lease_expiry\n"
                             "3 failed, 29 passed in 41.2s")]}
    for i in range(1, blocks):
        msgs += facts.get(i, [])
        if i % 2:
            msgs += [call(i, "read_file", {"path": f"src/billing/{rng.choice(WORDS)}_{i}.py"}), result(i, filler_file(rng, 12))]
        else:
            msgs += [call(i, "run_command", {"cmd": f"grep -rn {rng.choice(WORDS)} logs/"}), result(i, filler_log(rng, 30))]
        msgs.append({"role": "assistant", "content": f"Nothing conclusive in step {i}; continuing."})
    return msgs


QUESTIONS = [
    ("port", "Which port does the billing database use now? Answer with the number only.",
     lambda m: "54329" in (m.get("content") or "") and "54328" not in (m.get("content") or "")),
    ("tests", "Which tests failed in the last test run? List their names.",
     lambda m: all(t in (m.get("content") or "") for t in ("test_rollover_rounding", "test_batch_retry_backoff", "test_lease_expiry"))),
    ("oncall", "Who should I route urgent issues to this week? Answer with the name only.",
     lambda m: "Mirela" in (m.get("content") or "")),
    ("upload", "Upload reports/flaky.txt to the right bucket.",
     lambda m: any(c["function"]["name"] == "upload_file" and json.loads(c["function"]["arguments"]).get("bucket") == "basalt-12"
                   for c in m.get("tool_calls") or [])),
]


def post(path, body, timeout=1800):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 502 or attempt == 2:
                raise
            time.sleep(2)


def prompt_tokens(msgs):
    text = "\n".join(m.get("content") or json.dumps(m.get("tool_calls")) for m in msgs)
    return len(post(f"/upstream/{MODEL}/tokenize", {"content": text})["tokens"])


blocks = 100
for _ in range(4):
    n = prompt_tokens(transcript(blocks))
    if abs(n - TARGET) < TARGET * 0.05:
        break
    blocks = max(10, int(blocks * TARGET / n))
history = transcript(blocks)
log = open(f"{LABEL}.longctx.jsonl", "w")
scores = {}
for name, question, check in QUESTIONS:
    ok = 0
    for _ in range(REPEATS):
        t = time.time()
        try:
            data = post("/v1/chat/completions", {"model": MODEL, "messages": history + [{"role": "user", "content": question}],
                                                 "tools": TOOLS, "max_tokens": 6000})
            msg = data["choices"][0]["message"]
            passed = bool(check(msg))
            usage = data.get("usage")
        except Exception as e:
            msg, passed, usage = {"error": str(e)}, False, None
        ok += passed
        log.write(json.dumps({"q": name, "ok": passed, "seconds": round(time.time() - t, 1), "usage": usage,
                              "content": (msg.get("content") or "")[:500], "tool_calls": msg.get("tool_calls"), "error": msg.get("error")}) + "\n")
        log.flush()
    scores[name] = ok
    print(f"{LABEL} {name}: {ok}/{REPEATS}", flush=True)
print("LONGCTX " + json.dumps({"label": LABEL, "blocks": blocks, "scores": scores, "total": sum(scores.values()), "max": REPEATS * len(QUESTIONS)}), flush=True)
