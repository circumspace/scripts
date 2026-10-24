import json
import os
import re
import sys
import urllib.request

URL = os.environ.get("LLAMA_SWAP", "http://localhost:8080") + "/v1/chat/completions"
SOURCE = open(sys.argv[1]).read()
FUNC = re.search(r"^def (\w+)", SOURCE, re.M)[1]
TASKS = {
    "edit": f"Here is a Python file:\n```python\n{SOURCE}\n```\nReturn the complete file with the function `{FUNC}` renamed to `{FUNC}_renamed` everywhere. Output only the full file in one python code block, no explanation.",
    "fresh": "Write a Python module implementing a thread-safe LRU cache with TTL expiry, a decorator to memoize functions with it, and unit tests using unittest. Output only code.",
}


def run(prompt, temperature):
    body = {"model": os.environ.get("MODEL", "default"), "messages": [{"role": "user", "content": prompt}], "max_tokens": 6000,
            "temperature": temperature, "cache_prompt": False}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        t = json.load(r)["timings"]
    drafted, accepted = t.get("draft_n", 0), t.get("draft_n_accepted", 0)
    return {"tokens": t["predicted_n"], "write_tps": round(t["predicted_per_second"], 1),
            "draft_accept": f"{accepted}/{drafted}" if drafted else "-"}


for name, prompt in TASKS.items():
    for temperature in (0, 0.6):
        print(json.dumps({"variant": sys.argv[2], "task": name, "temperature": temperature, **run(prompt, temperature)}), flush=True)
