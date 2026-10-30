import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(D, "page_template.html")).read()
races = open(os.path.join(D, "races.json")).read()
money = open(os.path.join(D, "money.json")).read() if os.path.exists(os.path.join(D, "money.json")) else "{}"
meta = open(os.path.join(D, "meta.json")).read() if os.path.exists(os.path.join(D, "meta.json")) else '{"asof":"","source":""}'
for k, v in (("/*RACES*/[]", races), ("/*MONEY*/{}", money), ('/*META*/{asof:"", source:""}', meta)):
    assert t.count(k) == 1, k
    t = t.replace(k, v)
open(sys.argv[1], "w").write(t)
print("built", len(t))
