import json, os, sys, time, urllib.request

URL = os.environ.get("LLAMA_SWAP", "http://localhost:8080") + "/v1/chat/completions"
MODEL = os.environ.get("MODEL", "default")
PROMPTS = {
    "colleague": "A colleague of mine constantly seeks approval, and it irritates me far more than it should. A friend suggested "
                 "this might say something about me. Help me explore that from a Jungian perspective, without flattering me.",
    "dream": "Last night I dreamt I was locked out of my childhood home while a stranger inside rearranged the furniture. "
             "Explore what this might mean using Jungian ideas such as the shadow and the persona. Be concrete, and say "
             "where the interpretation is speculative.",
    "explain": "Explain the difference between the shadow and the persona in Jung's psychology to a thoughtful adult with no "
               "background, in about 300 words, with one everyday example of each.",
    "story": "Write a 400-word short story about a lighthouse keeper who receives a letter from herself, dated twenty years "
             "in the future. Literary tone, no twist ending.",
    "rewrite": "Rewrite this as a kind but honest email to a friend: \"You cancelled on me three times this month. I'm done "
               "planning things if you won't show up. Either commit or don't.\"",
    "argue": "Make the strongest case for and against keeping a daily journal, in two paragraphs of roughly equal weight. "
             "Then say which side you find more convincing and why.",
    "brief": "Schreibe einen Brief von etwa 200 Wörtern an dein jüngeres Ich mit 16 Jahren. Ehrlich, warm, ohne Kitsch.",
}

out = open(f"{sys.argv[1]}.writing.jsonl", "w")
for name, prompt in PROMPTS.items():
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 6000}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.load(r)
    msg = data["choices"][0]["message"]
    out.write(json.dumps({"prompt": name, "seconds": round(time.time() - t, 1), "usage": data.get("usage"),
                          "reasoning_chars": len(msg.get("reasoning_content") or ""), "content": msg.get("content")},
                         ensure_ascii=False) + "\n")
    out.flush()
    print(f"{sys.argv[1]} {name}: {data.get('usage', {}).get('completion_tokens')} tokens", flush=True)
