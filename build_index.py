#!/usr/bin/env python3
"""report_*.html に付随する <id>.meta.json を集約して reports.json を作る。
index.html がこの reports.json を読んでタブを描画する。"""
import json, glob, os

entries = []
for f in sorted(glob.glob("*.meta.json")):
    try:
        entries.append(json.load(open(f, encoding="utf-8")))
    except Exception as e:
        print("skip", f, e)

# 新しい順
entries.sort(key=lambda e: e.get("date", ""), reverse=True)
json.dump(entries, open("reports.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"{len(entries)} reports indexed -> reports.json")
