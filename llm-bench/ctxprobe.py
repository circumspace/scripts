import json, os, sys, time, urllib.request
sys.path.insert(0, sys.path[0])
import speed
URL = os.environ.get("LLAMA_SWAP", "http://localhost:8080") + "/v1/chat/completions"
MODEL = os.environ.get("PROBE_MODEL", os.environ.get("MODEL", "default"))

def run(prompt, max_tokens):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens,
            "temperature": 0, "cache_prompt": False}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                return json.load(r)["timings"]
        except urllib.error.HTTPError as e:
            if e.code != 502 or attempt == 2: raise
            time.sleep(2)

deep_tokens = int(sys.argv[2])
deep = "Here is a log to keep in mind:\n" + "\n".join(f"{i}: district {i%13} recorded {i*37%1000} units, plan {i%97}" for i in range(int(deep_tokens / 17))) + "\n\nWrite a 200-word essay about rivers. Do not mention the log."
run(speed.PROMPT, 16)
short = run(speed.PROMPT, 256)
d = run(deep, 200)
print(json.dumps({"variant": sys.argv[1],
    "short_prompt": short["prompt_n"], "read_tps": round(short["prompt_per_second"]), "write_tps": round(short["predicted_per_second"], 1),
    "deep_prompt": d["prompt_n"], "deep_read_tps": round(d["prompt_per_second"]), "deep_write_tps": round(d["predicted_per_second"], 1)}), flush=True)
