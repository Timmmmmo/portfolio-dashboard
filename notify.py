#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Server酱推送 — 盘中关键警报 + 盘后复盘
用法:
  python notify.py --mode alert            # 只推新增止损/减仓警报
  python notify.py --mode review           # 收盘复盘全量
  python notify.py --mode alert --also-review  # 盘中警报；若北京时间>=15:00 则改推复盘
环境变量:
  SERVERCHAN_KEY  Server酱 SendKey（缺省则跳过推送，exit 0）
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, 'notify_state.json')
SIGNAL_PATH = os.path.join(ROOT, 'trader_signal.json')
BJT = timezone(timedelta(hours=8))


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def now_bjt():
    return datetime.now(BJT)


def send_serverchan(key, title, desp, short='操盘台'):
    """POST 到 Server酱 Turbo。返回 (ok, msg)。"""
    url = f'https://sctapi.ftqq.com/{key}.send'
    data = urllib.parse.urlencode({
        'title': title[:100],
        'desp': desp,
        'short': short,
    }).encode('utf-8')
    last = ''
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers={
                'User-Agent': 'portfolio-dashboard/notify',
                'Content-Type': 'application/x-www-form-urlencoded',
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode('utf-8', 'ignore')
            try:
                resp = json.loads(body)
                if resp.get('code') in (0, 200) or resp.get('errno') == 0:
                    return True, body[:200]
                last = body[:200]
            except Exception:
                return True, body[:200]
        except Exception as e:
            last = str(e)
            import time
            time.sleep(1.5 * (attempt + 1))
    return False, last


def load_state():
    st = load_json(STATE_PATH, {})
    today = now_bjt().strftime('%Y-%m-%d')
    if st.get('date') != today:
        st = {'date': today, 'pushed': []}
    return st


def critical_signals(trader):
    """止损 + 减仓，用于盘中警报"""
    out = []
    for s in trader.get('signals') or []:
        sig = s.get('signal') or {}
        action = sig.get('action')
        if action in ('stop', 'reduce'):
            out.append({
                'code': s.get('code', ''),
                'name': s.get('name', s.get('code', '')),
                'action': action,
                'action_cn': sig.get('action_cn', action),
                'reason': sig.get('reason', ''),
                'price': sig.get('price', 0),
                'chg': sig.get('chg', 0),
                'pnl': sig.get('pnl', 0),
                'stop': sig.get('stop', 0),
                'target': sig.get('target', 0),
                'pos': sig.get('pos_pct', sig.get('pos', 0)),
            })
    return out


def format_alert(items, market):
    lines = []
    title_tag = '止损警报' if any(i['action'] == 'stop' for i in items) else '减仓提醒'
    lines.append(f"**【A股操盘台】{title_tag}**\n")
    for i in items:
        lines.append(f"### {i['name']} · {i['action_cn']}")
        lines.append(f"- 原因：{i['reason']}")
        if i['price']:
            lines.append(f"- 现价：{i['price']}  涨跌：{i['chg']:+.2f}%  浮盈：{i['pnl']:+.2f}%")
        if i['stop']:
            lines.append(f"- 止损/止盈：{i['stop']} / {i['target']}")
        if i['pos'] is not None:
            lines.append(f"- 建议仓位：{i['pos']}%")
        lines.append('')
    m = market or {}
    lines.append(f"---\n市场：**{m.get('regime_cn', '--')}**（温度 {m.get('score', '--')}）· "
                 f"风险 {m.get('risk_cn', '--')} · 平均涨跌 {m.get('avg_chg', 0):+.2f}%")
    ts = m.get('update_time') or os.environ.get('NOTIFY_TS', '')
    if not ts:
        ts = now_bjt().strftime('%Y-%m-%d %H:%M')
    lines.append(f"\n数据时间 {ts} · 仅供参考，不构成投资建议")
    return '\n'.join(lines)


def format_review(trader):
    m = trader.get('market') or {}
    lines = []
    lines.append(f"**【A股操盘台】收盘复盘** {now_bjt().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(f"## 市场状态")
    lines.append(f"- 状态：**{m.get('regime_cn', '--')}** · 温度 **{m.get('score', '--')}**")
    lines.append(f"- 风险：{m.get('risk_cn', '--')} · 平均涨跌 {m.get('avg_chg', 0):+.2f}%")
    lines.append(f"- 说明：{m.get('regime_note', '')}\n")

    lines.append('## 今日操盘剧本')
    for p in trader.get('playbook') or []:
        lines.append(f"- {p}")
    lines.append('')

    lines.append('## 持仓信号')
    for s in trader.get('signals') or []:
        sig = s.get('signal') or {}
        price = sig.get('price', 0)
        chg = sig.get('chg', 0)
        pnl = sig.get('pnl', 0)
        lines.append(
            f"- **{s.get('name', s.get('code'))}** [{sig.get('action_cn', '--')}] "
            f"现价 {price} ({chg:+.2f}%) 浮盈 {pnl:+.2f}% · {sig.get('reason', '')}"
        )
    lines.append('')

    sectors = trader.get('sectors') or []
    if sectors:
        lines.append('## 板块资金流 Top')
        top = sorted(sectors, key=lambda x: -(x.get('cum_inflow_yi') or x.get('main_inflow_yi', 0)))[:5]
        for s in top:
            v = s.get('cum_inflow_yi') or s.get('main_inflow_yi', 0)
            lines.append(f"- {s.get('name', '')}：**{v:+.2f}亿** ({s.get('chg', 0):+.2f}%)")

    lines.append(f"\n---\n数据时间 {trader.get('update_time', '')} · 仅供参考，不构成投资建议")
    return '\n'.join(lines)


def run_alert(trader, key):
    items = critical_signals(trader)
    if not items:
        print('alert: no critical signals')
        return
    state = load_state()
    pushed = set(state.get('pushed') or [])
    fresh = []
    for i in items:
        fp = f"{i['code']}:{i['action']}"
        if fp in pushed:
            print('alert: skip already pushed', fp)
            continue
        fresh.append(i)
        pushed.add(fp)
    if not fresh:
        print('alert: all already pushed today')
        return
    title = '【A股操盘台】止损警报' if any(i['action'] == 'stop' for i in fresh) else '【A股操盘台】减仓提醒'
    if len(fresh) == 1:
        title = f"【A股操盘台】{fresh[0]['name']} {fresh[0]['action_cn']}"
    desp = format_alert(fresh, trader.get('market'))
    ok, msg = send_serverchan(key, title, desp)
    print('alert: sent', ok, msg[:120])
    if ok:
        state['pushed'] = sorted(pushed)
        save_json(STATE_PATH, state)


def run_review(trader, key):
    title = f"【A股操盘台】收盘复盘 {(trader.get('market') or {}).get('regime_cn', '')}"
    desp = format_review(trader)
    ok, msg = send_serverchan(key, title, desp)
    print('review: sent', ok, msg[:120])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['alert', 'review'], default='alert')
    ap.add_argument('--also-review', action='store_true',
                    help='alert 模式下，若北京时间>=15:00 则改推复盘')
    a = ap.parse_args()

    key = os.environ.get('SERVERCHAN_KEY', '').strip()
    if not key:
        print('notify: SERVERCHAN_KEY 未配置，跳过推送')
        return 0

    trader = load_json(SIGNAL_PATH, None)
    if not trader:
        print('notify: trader_signal.json 缺失，跳过')
        return 0

    mode = a.mode
    if a.also_review and mode == 'alert':
        bjt = now_bjt()
        if (bjt.hour, bjt.minute) >= (15, 0) or bjt.hour >= 15:
            mode = 'review'
            print('notify: after close, switch to review')

    if mode == 'review':
        run_review(trader, key)
    else:
        run_alert(trader, key)
    return 0


if __name__ == '__main__':
    sys.exit(main())
