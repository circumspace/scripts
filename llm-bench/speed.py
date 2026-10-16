import concurrent.futures
import json
import sys
import urllib.request

FILLER = " ".join(
    f"Result {i}: The {['northern','southern','eastern','western'][i % 4]} district reported {i * 37 % 1000} new households, "
    f"a {i % 9 + 1}.{i % 7} percent change, while council member {['Ahn','Berg','Costa','Diallo','Eze'][i % 5]} proposed plan {i}."
    for i in range(110)
)
PROMPT = f"Here are search results:\n{FILLER}\n\nSummarize the three most notable trends in five sentences."


def probe(base, model_kwargs):
    body = {"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 256, "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": False, **model_kwargs}
    req = urllib.request.Request(f"{base}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        t = json.load(r)["timings"]
    return {"prompt_tokens": t["prompt_n"], "read_tps": round(t["prompt_per_second"], 1), "write_tps": round(t["predicted_per_second"], 1)}


def main():
    bases = sys.argv[1:]
    for b in bases:
        probe(b, {})
        print("alone", b, probe(b, {}), flush=True)
    if len(bases) > 1:
        with concurrent.futures.ThreadPoolExecutor(len(bases)) as ex:
            results = list(ex.map(lambda b: probe(b, {}), bases))
        for b, r in zip(bases, results):
            print("together", b, r, flush=True)


if __name__ == "__main__":
    main()
