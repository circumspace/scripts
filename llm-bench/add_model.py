import json
import sys

import yaml

original, target, name, path, ncmoe, extra, sampling, ctx = sys.argv[1:9]
config = yaml.safe_load(open(original))
config["models"][name] = {
    "timeouts": {"responseHeader": 0},
    "name": name,
    "description": f"Benchmark candidate {path}",
    "cmd": (f"${{server}} --load-mode none -m /models/{path} --alias {name} "
            f"--n-cpu-moe {ncmoe} -c {ctx} -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 "
            f"--reasoning-budget 2048 --cache-ram 6144 -np 1 {extra}"),
    "filters": {"setParamsByID": {name: json.loads(sampling)}},
    "capabilities": {"tools": True, "context": int(ctx)},
}
yaml.safe_dump(config, open(target, "w"), sort_keys=False, width=1000)
