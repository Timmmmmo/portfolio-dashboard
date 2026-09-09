#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并写入 intel_state.json（Dashboard 情报流+市场总结的数据源）。
新情报插入最前，按 (tag|txt) 去重，保留最近30条。

用法:
  python update_intel.py --feed feed.json --summary summary.md
  feed.json: [{"t":"HH:MM","tag":"板块/股票标签","cat":"up|dn|warn|info","txt":"正文"}, ...]（新的放最前）
  summary.md: A股市场总结 markdown（覆盖写入）
"""
import argparse, json, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'intel_state.json')
MAX_FEED = 30

def load_state():
    if os.path.exists(STATE):
        try:
            with open(STATE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {'updated': '', 'feed': [], 'summary': ''}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed', required=True)
    ap.add_argument('--summary', required=True)
    ap.add_argument('--label', default='', help='附注标签，如 盘中/收盘，会加在updated后')
    a = ap.parse_args()

    with open(a.feed, 'r', encoding='utf-8') as f:
        new_items = json.load(f)
    with open(a.summary, 'r', encoding='utf-8') as f:
        summary = f.read().strip()

    state = load_state()
    seen = set()
    merged = []
    for it in new_items + state.get('feed', []):
        key = (it.get('tag', ''), it.get('txt', ''))
        if not it.get('txt') or key in seen:
            continue
        seen.add(key)
        merged.append(it)
        if len(merged) >= MAX_FEED:
            break

    now = datetime.now()
    updated = now.strftime('%Y-%m-%d %H:%M')
    if a.label:
        updated += ' ' + a.label
    state['updated'] = updated
    state['feed'] = merged
    state['summary'] = summary
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    print(f'ok: feed={len(merged)} updated={updated}')

if __name__ == '__main__':
    main()
