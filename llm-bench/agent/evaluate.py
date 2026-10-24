import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
LABEL = sys.argv[2] if len(sys.argv) > 2 else "model"
SAMPLING = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
REPEATS = 3


def chat(messages, tools=None, max_tokens=12000, **extra):
    body = {"messages": messages, "max_tokens": max_tokens, **SAMPLING, **extra}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(f"{BASE}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = json.load(r)
    return data["choices"][0]["message"], data.get("usage", {}), time.time() - t


def fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


WEATHER = fn("get_weather", "Current weather for a city", {"city": {"type": "string"}, "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, ["city"])
STOCK = fn("get_stock_price", "Latest stock price for a ticker symbol", {"ticker": {"type": "string"}}, ["ticker"])
EMAIL = fn("send_email", "Send an email", {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, ["to", "subject", "body"])
CAL = fn("create_event", "Create a calendar event", {
    "title": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD"},
    "duration_minutes": {"type": "integer"}, "attendees": {"type": "array", "items": {"type": "string"}}},
    ["title", "date", "duration_minutes", "attendees"])
LOOKUP = fn("find_user", "Find a user's email address by full name", {"name": {"type": "string"}}, ["name"])
SEARCH = fn("web_search", "Search the web", {"query": {"type": "string"}}, ["query"])
ALL = [WEATHER, STOCK, EMAIL, CAL, LOOKUP, SEARCH]


def calls(msg):
    out = []
    for c in msg.get("tool_calls") or []:
        try:
            out.append((c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"), c.get("id", "x")))
        except json.JSONDecodeError:
            out.append((c["function"]["name"], None, c.get("id", "x")))
    return out


def t_single():
    m, *_ = chat([{"role": "user", "content": "What's the weather in Lisbon right now, in celsius?"}], ALL)
    c = calls(m)
    return len(c) == 1 and c[0][0] == "get_weather" and "lisbon" in str(c[0][1].get("city", "")).lower() and c[0][1].get("unit") in (None, "celsius")


def t_select():
    m, *_ = chat([{"role": "user", "content": "How much is NVIDIA stock trading at?"}], ALL)
    c = calls(m)
    return len(c) == 1 and c[0][0] == "get_stock_price" and str(c[0][1].get("ticker", "")).upper() == "NVDA"


def t_abstain():
    m, *_ = chat([{"role": "user", "content": "What is 17 times 23? Answer with just the number."}], ALL)
    return not calls(m) and "391" in (m.get("content") or "")


def t_parallel():
    msgs = [{"role": "user", "content": "Compare the current weather in Oslo and in Cairo."}]
    found = set()
    for _ in range(3):
        m, *_ = chat(msgs, ALL)
        c = calls(m)
        if not c:
            break
        found |= {str(a.get("city", "")).lower() for n, a, _ in c if n == "get_weather" and a}
        msgs += [m] + [{"role": "tool", "tool_call_id": i, "content": json.dumps({"temp_c": 10})} for *_, i in c]
    return {"oslo", "cairo"} <= found


def t_types():
    m, *_ = chat([{"role": "user", "content": "Schedule a 45 minute 'Design review' on 2026-11-03 with ana@x.io and ben@x.io."}], ALL)
    c = calls(m)
    if len(c) != 1 or c[0][0] != "create_event" or not c[0][1]:
        return False
    a = c[0][1]
    return a.get("date") == "2026-11-03" and a.get("duration_minutes") == 45 and isinstance(a.get("attendees"), list) and sorted(a["attendees"]) == ["ana@x.io", "ben@x.io"]


def t_chain():
    msgs = [{"role": "user", "content": "Email Maria Schmidt that the meeting moved to Friday. You don't know her address."}]
    m, *_ = chat(msgs, ALL)
    c = calls(m)
    if not c or c[0][0] != "find_user":
        return False
    msgs += [m, {"role": "tool", "tool_call_id": c[0][2], "content": json.dumps({"email": "m.schmidt@corp.de"})}]
    m, *_ = chat(msgs, ALL)
    c = calls(m)
    return len(c) == 1 and c[0][0] == "send_email" and c[0][1] and c[0][1].get("to") == "m.schmidt@corp.de" and "friday" in json.dumps(c[0][1]).lower()


def t_use_result():
    msgs = [{"role": "user", "content": "Who won the 2031 Tour de France? Search for it."}]
    m, *_ = chat(msgs, ALL)
    c = calls(m)
    if not c or c[0][0] != "web_search":
        return False
    msgs += [m, {"role": "tool", "tool_call_id": c[0][2], "content": json.dumps({"results": [{"title": "Tour de France 2031", "snippet": "Kasimir Vellenga won the 2031 Tour de France ahead of ..."}]})}]
    m, *_ = chat(msgs, ALL)
    return not calls(m) and "vellenga" in (m.get("content") or "").lower()


TOOL_TESTS = [t_single, t_select, t_abstain, t_parallel, t_types, t_chain, t_use_result]

CODING = [
    ("Write a Python function `roman_to_int(s: str) -> int` that converts a Roman numeral (I..MMMCMXCIX) to an integer.",
     "assert roman_to_int('MCMXCIV')==1994; assert roman_to_int('III')==3; assert roman_to_int('XLIX')==49; assert roman_to_int('MMMCMXCIX')==3999"),
    ("Write a Python function `merge_intervals(xs: list[list[int]]) -> list[list[int]]` that merges overlapping or touching closed intervals and returns them sorted.",
     "assert merge_intervals([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]; assert merge_intervals([[1,4],[4,5]])==[[1,5]]; assert merge_intervals([])==[]; assert merge_intervals([[5,7],[1,2]])==[[1,2],[5,7]]"),
    ("Write a Python function `lru_cache_ops(capacity: int, ops: list) -> list` simulating an LRU cache. ops contains ('put', k, v) or ('get', k). Return the results of each get in order (-1 if missing). put on an existing key updates it and makes it most recent.",
     "assert lru_cache_ops(2,[('put',1,1),('put',2,2),('get',1),('put',3,3),('get',2),('put',4,4),('get',1),('get',3),('get',4)])==[1,-1,-1,3,4]; assert lru_cache_ops(1,[('put',1,1),('put',1,5),('get',1)])==[5]"),
    ("Write a Python function `eval_expr(s: str) -> int` that evaluates an integer arithmetic expression with + - * / (integer division truncating toward zero), parentheses, unary minus and spaces. Do not use eval or exec.",
     "assert eval_expr('1 + 2 * 3')==7; assert eval_expr('(1+2)*3')==9; assert eval_expr('-7/2')==-3; assert eval_expr('2*(3+-(4-6))')==10; assert eval_expr(' 14 - 3 - 2 ')==9"),
    ("Write a Python function `top_k_words(text: str, k: int) -> list[str]` returning the k most frequent words (case-insensitive, words are runs of letters a-z and apostrophes), ties broken alphabetically.",
     "assert top_k_words('the cat and the hat and THE bat', 2)==['the','and']; assert top_k_words('b a c a b', 3)==['a','b','c']; assert top_k_words(\"don't stop, don't\", 1)==[\"don't\"]"),
    ("Write a Python function `shortest_path(grid: list[str]) -> int` where grid rows contain '.', '#', 'S', 'E'. Return the minimum number of 4-directional steps from S to E avoiding '#', or -1 if unreachable.",
     "assert shortest_path(['S.#','..#','#.E'])==4; assert shortest_path(['S#E'])==-1; assert shortest_path(['SE'])==1"),
    ("Write a Python function `parse_duration(s: str) -> int` converting strings like '1h30m', '45s', '2d4h', '1h 5m 10s' to total seconds. Units: d,h,m,s. Raise ValueError on invalid input like '' or '5x' or 'h'.",
     "assert parse_duration('1h30m')==5400; assert parse_duration('45s')==45; assert parse_duration('2d4h')==187200; assert parse_duration('1h 5m 10s')==3910\nfor bad in ['','5x','h','1h-2m']:\n    try:\n        parse_duration(bad); raise SystemExit('no error for '+repr(bad))\n    except ValueError: pass"),
    ("Write a Python function `longest_palindrome(s: str) -> str` returning the longest palindromic substring (the first one if several have the same length).",
     "assert longest_palindrome('babad')=='bab'; assert longest_palindrome('cbbd')=='bb'; assert longest_palindrome('a')=='a'; assert longest_palindrome('forgeeksskeegfor')=='geeksskeeg'"),
    ("Write a Python function `topo_order(deps: dict[str, list[str]]) -> list[str]` where deps maps a task to the tasks it depends on. Return an order where every task comes after its dependencies; among available tasks pick alphabetically first. Raise ValueError on cycles. Tasks only mentioned as dependencies are included too.",
     "assert topo_order({'b':['a'],'c':['a','b']})==['a','b','c']; assert topo_order({'x':[],'a':[]})==['a','x']; assert topo_order({'d':['c'],'b':[]})==['b','c','d']\ntry:\n    topo_order({'a':['b'],'b':['a']}); raise SystemExit('no cycle error')\nexcept ValueError: pass"),
    ("Write a Python function `rle_decode(s: str) -> str` decoding strings like '3[a]2[bc]' -> 'aaabcbc', supporting nesting like '3[a2[c]]' -> 'accaccacc' and plain letters between groups.",
     "assert rle_decode('3[a]2[bc]')=='aaabcbc'; assert rle_decode('3[a2[c]]')=='accaccacc'; assert rle_decode('2[abc]3[cd]ef')=='abcabccdcdcdef'; assert rle_decode('10[x]')=='x'*10"),
    ("Write a Python function `matrix_spiral(m: list[list[int]]) -> list[int]` returning the elements in clockwise spiral order starting top-left.",
     "assert matrix_spiral([[1,2,3],[4,5,6],[7,8,9]])==[1,2,3,6,9,8,7,4,5]; assert matrix_spiral([[1,2,3,4],[5,6,7,8],[9,10,11,12]])==[1,2,3,4,8,12,11,10,9,5,6,7]; assert matrix_spiral([])==[]; assert matrix_spiral([[1],[2]])==[1,2]"),
    ("Write a Python function `min_coins(coins: list[int], amount: int) -> int` returning the fewest coins summing to amount, or -1 if impossible.",
     "assert min_coins([1,2,5],11)==3; assert min_coins([2],3)==-1; assert min_coins([1],0)==0; assert min_coins([186,419,83,408],6249)==20"),
]


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    return max(blocks, key=len) if blocks else (text or "")


def run_tests(code, tests):
    with tempfile.TemporaryDirectory() as d:
        open(f"{d}/t.py", "w").write(code + "\n\n" + tests + "\nprint('PASS')\n")
        try:
            r = subprocess.run(["podman", "run", "--rm", "--network", "none", "--memory", "512m", "-v", f"{d}:/w:ro,z",
                                "docker.io/library/python:3.13-alpine", "python", "/w/t.py"], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False, "timeout"
        return "PASS" in r.stdout, (r.stdout + r.stderr)[-800:]


LOG = open(f"{LABEL}.replies.jsonl", "w")
ONLY = sys.argv[4] if len(sys.argv) > 4 else "all"


def main():
    report = {"label": LABEL, "tools": {}, "coding": []}
    t0 = time.time()
    for t in (TOOL_TESTS if ONLY in ("all", "tools") else []):
        ok = 0
        for _ in range(REPEATS):
            try:
                ok += bool(t())
            except Exception as e:
                print(f"  {t.__name__} error: {e}", file=sys.stderr)
        report["tools"][t.__name__] = ok
        print(f"tool {t.__name__}: {ok}/{REPEATS}", flush=True)
    tool_time = time.time() - t0
    gen_tokens, gen_time = 0, 0.0
    for i, (task, tests) in enumerate(CODING if ONLY in ("all", "coding") else []):
        try:
            m, usage, dt = chat([{"role": "user", "content": task + " Reply with the complete function in one ```python code block. Standard library only."}])
            gen_tokens += usage.get("completion_tokens", 0)
            gen_time += dt
            ok, out = run_tests(extract_code(m.get("content")), tests)
            LOG.write(json.dumps({"task": i, "ok": ok, "usage": usage, "content": m.get("content"), "reasoning_chars": len(m.get("reasoning_content") or ""), "test_output": out}) + "\n")
            LOG.flush()
        except Exception as e:
            print(f"  coding {i} error: {e}", file=sys.stderr)
            ok = False
        report["coding"].append(ok)
        print(f"code {i}: {'pass' if ok else 'FAIL'}", flush=True)
    report["tool_score"] = sum(report["tools"].values())
    report["tool_max"] = REPEATS * len(TOOL_TESTS)
    report["coding_score"] = sum(report["coding"])
    report["coding_max"] = len(CODING)
    report["tool_minutes"] = round(tool_time / 60, 1)
    report["coding_avg_seconds"] = round(gen_time / len(CODING), 1)
    report["coding_avg_tokens"] = round(gen_tokens / len(CODING))
    print("RESULT " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
