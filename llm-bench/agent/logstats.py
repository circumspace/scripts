import json
import re
import sys

prompt_ms = prompt_tok = gen_ms = gen_tok = accepted = drafted = requests = 0
for line in sys.stdin:
    if m := re.search(r"prompt eval time =\s*([\d.]+) ms /\s*(\d+) tokens", line):
        prompt_ms += float(m[1]); prompt_tok += int(m[2]); requests += 1
    elif m := re.search(r"\beval time =\s*([\d.]+) ms /\s*(\d+) tokens", line):
        gen_ms += float(m[1]); gen_tok += int(m[2])
    elif m := re.search(r"draft acceptance = [\d.]+ \(\s*(\d+) accepted /\s*(\d+) generated", line):
        accepted += int(m[1]); drafted += int(m[2])
print(json.dumps({
    "requests": requests,
    "read_tokens": prompt_tok, "read_tps": round(prompt_tok / (prompt_ms / 1000), 1) if prompt_ms else None,
    "written_tokens": gen_tok, "write_tps": round(gen_tok / (gen_ms / 1000), 1) if gen_ms else None,
    "guesses_accepted": f"{accepted}/{drafted}",
}))
