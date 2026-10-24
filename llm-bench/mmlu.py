import glob
import json
import os
import re
import sys
import urllib.request

URL = os.environ.get("LLAMA_SWAP", "http://localhost:8080") + "/v1/chat/completions"

# Usage: mmlu.py <model> <lm_eval samples dir> <out.jsonl>
# MMLU-Pro zero-shot on the questions an lm_eval mmlu_pro run used. Few-shot chat turns
# without visible reasoning lead both models to answer inside their reasoning and leave
# the final message empty; here the answer is read from the final message, else from the
# reasoning, and the source is recorded.
ANSWER = re.compile(r"answer is \(?([A-J])\)?")
docs = [json.loads(l)["doc"] for f in sorted(glob.glob(f"{sys.argv[2]}/**/samples_mmlu_pro_*.jsonl", recursive=True)) for l in open(f)][: int(os.environ.get("LIMIT", 10**6))]
out = open(sys.argv[3], "w")
counts = {"correct": 0, "from_content": 0, "from_reasoning": 0, "none": 0}
for d in docs:
    options = "\n".join(f"{chr(65 + i)}. {o}" for i, o in enumerate(d["options"]))
    prompt = (f"The following is a multiple choice question about {d['category']}. Think step by step and then finish "
              f"your answer with \"The answer is (X)\" where X is the correct letter choice.\n\n"
              f"Question: {d['question']}\nOptions:\n{options}")
    body = {"model": sys.argv[1], "messages": [{"role": "user", "content": prompt}], "max_tokens": 6000}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    msg = json.load(urllib.request.urlopen(req, timeout=1800))["choices"][0]["message"]
    content, reasoning = msg.get("content") or "", msg.get("reasoning_content") or ""
    found = ANSWER.findall(content)
    source = "from_content" if found else None
    if not found:
        found = ANSWER.findall(reasoning)
        source = "from_reasoning" if found else "none"
    pred = found[-1] if found else None
    counts[source] += 1
    counts["correct"] += pred == d["answer"]
    out.write(json.dumps({"id": d["question_id"], "category": d["category"], "answer": d["answer"], "pred": pred, "source": source,
                          "content": content[-400:]}, ensure_ascii=False) + "\n")
    out.flush()
print("MMLU " + json.dumps({"model": sys.argv[1], "n": len(docs), **counts, "accuracy": round(counts["correct"] / len(docs), 4)}), flush=True)
