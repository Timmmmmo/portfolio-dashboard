#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
细分板块资金流 — 行业 + 概念板块主力净流入，含当日分钟序列
输出 sector_flow.json 供 Dashboard 折线图使用。
盘中由前端每 60 秒 live 刷新；Actions 注入用于首屏回填。
"""
import json
import sys
import urllib.request
from datetime import datetime

CF_EM = 'https://push2delay.eastmoney.com/api/qt'
CF_EM_PUSH = 'https://push2.eastmoney.com/api/qt'
CF_UT = 'fa5fd1943c7b386f1725622f7d9f5fcf'
H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://data.eastmoney.com/',
    'Accept': '*/*',
    'Connection': 'keep-alive',
}


def _get_json(url, timeout=12, retries=5):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=H)
            raw = urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'ignore')
            return json.loads(raw)
        except Exception as e:
            last = e
            import time
            time.sleep(1.2 * (i + 1))
    raise last


def fetch_top_sectors(kind='industry', n=6):
    """
    kind: industry → fs=m:90+t:2  |  concept → fs=m:90+t:3
    返回主力净流入 top N
    """
    fs = 'm:90+t:2+f:!50' if kind == 'industry' else 'm:90+t:3+f:!50'
    url = (
        f'{CF_EM}/clist/get?pn=1&pz={n}&po=1&np=1&fltt=2&invt=2'
        f'&fid=f62&fs={fs}&fields=f12,f14,f62,f3&ut={CF_UT}'
    )
    try:
        data = _get_json(url)
    except Exception as e:
        print('clist_err', kind, e, file=sys.stderr)
        try:
            data = _get_json(url.replace(CF_EM, CF_EM_PUSH))
        except Exception as e2:
            print('clist_err2', kind, e2, file=sys.stderr)
            return []
    out = []
    for it in (data.get('data') or {}).get('diff') or []:
        code = it.get('f12') or ''
        name = it.get('f14') or ''
        inflow = float(it.get('f62') or 0) / 1e8
        chg = float(it.get('f3') or 0)
        if code and name:
            out.append({
                'code': code,
                'name': name,
                'type': kind,
                'main_inflow_yi': round(inflow, 2),
                'chg': round(chg, 2),
            })
    return out


def fetch_minute_kline(secid, lmt=240):
    """当日分钟主力净流入序列 → [{'t':'09:31','v':亿}] (单分钟净流入)"""
    params = (
        f'lmt={lmt}&klt=1&secid=90.{secid}'
        f'&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56&ut={CF_UT}'
    )
    text = None
    for base in (CF_EM, CF_EM_PUSH):
        try:
            data = _get_json(f'{base}/stock/fflow/kline/get?{params}')
            text = (data.get('data') or {}).get('klines') or []
            if text:
                break
        except Exception as e:
            print('kline_err', secid, e, file=sys.stderr)
    if not text:
        return []
    points = []
    prev = 0.0
    for line in text:
        parts = line.split(',')
        if len(parts) < 2:
            continue
        t = parts[0].split(' ')[-1] if ' ' in parts[0] else parts[0]
        try:
            cum = float(parts[1]) / 1e8  # f52 为当日累计主力净流入(亿)
        except Exception:
            continue
        delta = round(cum - prev, 4)
        prev = cum
        points.append({'t': t, 'v': delta, 'cum': round(cum, 4)})
    return points


def build():
    now = datetime.now()
    industries = fetch_top_sectors('industry', 5)
    concepts = fetch_top_sectors('concept', 5)
    sectors = industries + concepts

    for s in sectors:
        mins = fetch_minute_kline(s['code'], 240)
        s['points'] = mins
        # f52 已是累计，取末值
        s['cum_inflow_yi'] = round(mins[-1]['cum'], 2) if mins else s.get('main_inflow_yi', 0)

    return {
        'update_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date': now.strftime('%Y-%m-%d'),
        'sectors': sectors,
    }


if __name__ == '__main__':
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"sectors={len(result['sectors'])} "
        f"pts={sum(len(s.get('points', [])) for s in result['sectors'])}",
        file=sys.stderr,
    )
