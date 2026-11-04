#!/usr/bin/env python3
"""Keep the last good California numbers when the SoS feed returns zeros for a race/prop that already had votes (partial responses)."""
import json, sys
new, old = sys.argv[1], sys.argv[2]
try: n = json.load(open(new)); o = json.load(open(old))
except Exception: sys.exit(0)
fixed = []
for k, v in (o.get("races") or {}).items():
    x = (n.get("races") or {}).get(k)
    if (v.get("a") or 0) + (v.get("b") or 0) > 0 and (not x or (x.get("a") or 0) + (x.get("b") or 0) == 0): n.setdefault("races", {})[k] = v; fixed.append(k)
for k, v in (o.get("props") or {}).items():
    x = (n.get("props") or {}).get(k)
    if (v.get("yes") or 0) + (v.get("no") or 0) > 0 and (not x or (x.get("yes") or 0) + (x.get("no") or 0) == 0): n.setdefault("props", {})[k] = v; fixed.append("P" + k)
json.dump(n, open(new, "w"), separators=(",", ":"))
print("kept previous for:", fixed or "none")
