"""Reads the PhD Tracker through the Notion API and writes site/data.json."""
import json, os, sys, urllib.request, datetime

TOKEN = os.environ["NOTION_TOKEN"]
SOURCE = os.environ.get("NOTION_DATA_SOURCE", "8b8f2fdf-b45f-4cd2-86aa-557fa3be1e20")
STATUS_PROP = "Status (you set)"

def call(path, body):
    req = urllib.request.Request(
        "https://api.notion.com/v1/" + path,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Notion-Version": "2025-09-03", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

pages, cursor = [], None
while True:
    body = {"page_size": 100}
    if cursor:
        body["start_cursor"] = cursor
    res = call("data_sources/%s/query" % SOURCE, body)
    pages += res["results"]
    if not res.get("has_more"):
        break
    cursor = res["next_cursor"]

def title(p):
    t = p["properties"].get("Name", {}).get("title", [])
    return "".join(x.get("plain_text", "") for x in t).strip()

def select(p, name):
    v = p["properties"].get(name, {})
    o = v.get("select") or v.get("status")
    return o["name"] if o else None

def rel(p, name):
    return [x["id"] for x in p["properties"].get(name, {}).get("relation", [])]

chapters = [p for p in pages if select(p, "Level") == "Chapter"]
# The real parent property is the one that is empty on every Chapter row.
parent_prop = "Parent item"
for cand in ("Parent item", "Sub-item"):
    if all(not rel(c, cand) for c in chapters):
        parent_prop = cand
        break
parent_ids = set()
for p in pages:
    parent_ids.update(rel(p, parent_prop))

weights = {}
for c in chapters:
    w = c["properties"].get("Weight %", {}).get("number")
    if w:
        weights[select(c, "Chapter") or title(c)] = w

counts = {n: {"done": 0, "prog": 0, "todo": 0} for n in weights}
for p in pages:
    if not title(p) or p["id"] in parent_ids:
        continue
    ch = select(p, "Chapter")
    if ch not in counts:
        continue
    st = select(p, STATUS_PROP) or "Not started"
    key = "done" if st == "Done" else "prog" if st == "In progress" else "todo"
    counts[ch][key] += 1

out = {
    "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="minutes"),
    "chapters": [dict(name=n, weight=w, **counts[n]) for n, w in sorted(weights.items(), key=lambda x: -x[1])],
}
os.makedirs("site", exist_ok=True)
json.dump(out, open("site/data.json", "w"), indent=1)
print(json.dumps(out))
