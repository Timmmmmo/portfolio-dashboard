#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
操盘手引擎 — 市场温度计 + 个股信号 + 今日操盘建议
输出 trader_signal.json，供 index.html 渲染指挥舱。
"""
import json
import sys
import urllib.request
from datetime import datetime

# ============ 持仓配置（与 Dashboard 默认持仓一致，Actions 会读 portfolio 配置时可外置）============
HOLDINGS = [
    {'code': 'sh688106', 'name': '金宏气体', 'cost': 30.27, 'shares': 0, 'sector': '特气/氦气', 'logic': '半导体特气国产替代'},
    {'code': 'sh688114', 'name': '华大智造', 'cost': 68.15, 'shares': 0, 'sector': '基因测序', 'logic': 'AI医疗+测序龙头'},
    {'code': 'sz002594', 'name': '比亚迪', 'cost': 90.74, 'shares': 0, 'sector': '新能源车', 'logic': '销量全球第一+出海'},
    {'code': 'sz000021', 'name': '深科技', 'cost': 46.75, 'shares': 0, 'sector': '存储封测', 'logic': 'HBM/存储封测链'},
    {'code': 'hk00981', 'name': '中芯国际(H)', 'cost': 58.68, 'shares': 0, 'sector': 'AI芯片', 'logic': '最先进制程代工'},
    {'code': 'sh600399', 'name': '抚顺特钢', 'cost': 6.63, 'shares': 0, 'sector': '特钢', 'logic': '军工特钢'},
    {'code': 'sh601020', 'name': '华钰矿业', 'cost': 69.83, 'shares': 0, 'sector': '黄金/锑矿', 'logic': '锑资源+黄金'},
    {'code': 'sz300346', 'name': '南大光电', 'cost': 53.22, 'shares': 0, 'sector': '光刻胶', 'logic': 'ArF光刻胶国产替代'},
    {'code': 'bj872808', 'name': '曙光数创', 'cost': 83.18, 'shares': 0, 'sector': '液冷', 'logic': '数据中心液冷'},
    {'code': 'sh600338', 'name': '西藏珠峰', 'cost': 18.75, 'shares': 0, 'sector': '锂矿/铅锌', 'logic': '盐湖提锂预期'},
]

INDICES = [
    ('sh000001', '上证指数'),
    ('sz399001', '深证成指'),
    ('sz399006', '创业板指'),
    ('sh000688', '科创50'),
]

H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'}


def _get(url, enc='gbk', timeout=12):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=H), timeout=timeout
    ).read().decode(enc, 'ignore')


def fetch_qt(codes):
    """腾讯行情批量: code -> dict"""
    out = {}
    try:
        txt = _get('https://qt.gtimg.cn/q=' + ','.join(codes), 'gbk')
        for line in txt.strip().split(';'):
            if '~' not in line:
                continue
            try:
                key = line.split('=')[0].replace('var ', '').strip()
                if key.startswith('v_'):
                    key = key[2:]
                p = line.split('"')[1].split('~')
                if len(p) > 32 and p[3]:
                    out[key] = {
                        'code': key,
                        'name': p[1] or key,
                        'price': float(p[3]),
                        'prev': float(p[4]) if p[4] else float(p[3]),
                        'chg': float(p[32]) if p[32] else 0,
                        'high': float(p[33]) if len(p) > 33 and p[33] else 0,
                        'low': float(p[34]) if len(p) > 34 and p[34] else 0,
                        'vol_wan': float(p[6]) if p[6] else 0,
                        'amount_wan': float(p[37]) if len(p) > 37 and p[37] else 0,
                        'pe': float(p[39]) if len(p) > 39 and p[39] else 0,
                    }
            except Exception:
                continue
    except Exception as e:
        print('qt_err', e, file=sys.stderr)
    return out


def fetch_market_breadth():
    """尝试获取涨跌家数（新浪），失败则返回 None"""
    try:
        txt = _get('https://hq.sinajs.cn/list=s_sh000001', 'gbk')
        # 简易：无完整涨跌家数则用指数涨跌推断
    except Exception:
        pass
    return None


# ============ 市场温度 ============
def market_temperature(idx_data):
    """0-100，越高越积极"""
    score = 50
    changes = []
    for code, name in INDICES:
        d = idx_data.get(code)
        if d:
            changes.append(d['chg'])
    if changes:
        avg = sum(changes) / len(changes)
        score += avg * 8  # ±5% → ±40
        up_cnt = sum(1 for c in changes if c > 0)
        score += (up_cnt - len(changes) / 2) * 4
    # 成交额：上证 amount_wan 单位万元
    sh = idx_data.get('sh000001')
    if sh and sh.get('amount_wan'):
        amt_yi = sh['amount_wan'] / 10000  # 亿
        if amt_yi > 12000:
            score += 8
        elif amt_yi > 9000:
            score += 3
        elif amt_yi < 6000:
            score -= 10
    score = max(0, min(100, score))
    return round(score, 1)


def regime_from_score(score, avg_chg):
    if score >= 72:
        return 'attack', '进攻', '多头格局，可积极参与主线'
    if score >= 58:
        return 'bull', '偏多', '结构性机会，持仓为主'
    if score >= 42:
        return 'swing', '震荡', '高抛低吸，控制仓位'
    if score >= 28:
        return 'defense', '防守', '减仓弱势票，等待企稳'
    return 'cash', '空仓观望', '风险释放期，现金为王'


# ============ 个股信号 ============
def stock_signal(q, cost):
    """返回 dict: action, action_cn, stop, target, pos_pct, reason"""
    price = q['price']
    chg = q['chg']
    prev = q['prev'] or price
    pnl = (price - cost) / cost * 100 if cost > 0 else 0

    # 止损/止盈位
    stop = round(cost * 0.93, 2) if cost > 0 else round(price * 0.95, 2)
    target = round(cost * 1.15, 2) if cost > 0 else round(price * 1.10, 2)

    # 简易技术位
    if q.get('low') and q['low'] > 0:
        stop = round(min(stop, q['low'] * 0.98), 2) if cost > 0 else round(q['low'] * 0.98, 2)

    # 信号
    if cost > 0 and price <= stop:
        action, action_cn, pos_pct = 'stop', '止损', 0
        reason = f'跌破止损位 {stop}，无条件离场'
    elif chg <= -5:
        action, action_cn, pos_pct = 'reduce', '减仓', 30
        reason = f'当日大跌 {chg:.1f}%，减仓控风险'
    elif pnl <= -8:
        action, action_cn, pos_pct = 'reduce', '减仓', 30
        reason = f'浮亏 {pnl:.1f}%，减仓或设好止损'
    elif chg >= 5:
        action, action_cn, pos_pct = 'hold', '持有', 80
        reason = f'强势拉升 {chg:+.1f}%，持有待涨，上移止损'
    elif pnl >= 15:
        action, action_cn, pos_pct = 'reduce', '减仓', 50
        reason = f'浮盈 {pnl:.1f}% 达止盈区，兑现部分'
    elif chg >= 2 and pnl >= 0:
        action, action_cn, pos_pct = 'hold', '持有', 70
        reason = f'温和上涨 {chg:+.1f}%，趋势健康'
    elif chg > -2 and pnl > -5:
        action, action_cn, pos_pct = 'hold', '持有', 60
        reason = f'横盘整理，持有观察'
    elif chg < -2:
        action, action_cn, pos_pct = 'watch', '观望', 40
        reason = f'走弱 {chg:+.1f}%，不加仓，盯止损'
    else:
        action, action_cn, pos_pct = 'hold', '持有', 50
        reason = '无明确信号，按计划持有'

    return {
        'action': action,
        'action_cn': action_cn,
        'stop': stop,
        'target': target,
        'pos_pct': pos_pct,
        'reason': reason,
        'pnl': round(pnl, 2),
        'price': price,
        'chg': chg,
    }


# ============ 今日操盘剧本 ============
def build_playbook(regime, score, avg_chg, signals):
    lines = []
    if regime == 'attack':
        lines.append('【进攻】仓位可提至 7-8 成，聚焦主线龙头回调低吸')
        lines.append('重点跟踪今日资金流入板块，逢回调加仓强势票')
    elif regime == 'bull':
        lines.append('【偏多】仓位 5-6 成，持仓为主，弱票换强票')
        lines.append('关注相对强弱，跑输指数的标的优先调仓')
    elif regime == 'swing':
        lines.append('【震荡】仓位 4-5 成，高抛低吸，不追高')
        lines.append('冲高兑现、急跌接筹，单日振幅大时减仓过夜风险')
    elif regime == 'defense':
        lines.append('【防守】仓位降至 3 成以下，只留核心持仓')
        lines.append('跌破止损的票坚决离场，不抱幻想')
    else:
        lines.append('【空仓观望】风险释放期，现金为王')
        lines.append('等待缩量企稳或标志性阳线再进场')

    stops = [s for s in signals if s['signal']['action'] == 'stop']
    if stops:
        names = '、'.join(s['name'] for s in stops)
        lines.append(f'⚠️ 触及止损：{names}，执行离场纪律')

    reduces = [s for s in signals if s['signal']['action'] == 'reduce']
    if reduces:
        names = '、'.join(s['name'] for s in reduces[:4])
        lines.append(f'🔻 建议减仓：{names}')

    adds = [s for s in signals if s['signal']['action'] == 'hold' and s['signal'].get('chg', 0) > 2]
    if adds:
        names = '、'.join(s['name'] for s in adds[:4])
        lines.append(f'🔺 走势健康可持有/加仓：{names}')

    lines.append(f'大盘温度 {score} 分 · 平均涨跌 {avg_chg:+.2f}% · 严格执行止损纪律')
    return lines


def load_intel_feed():
    """读取 intel_state.json 的情报流（相对脚本目录）"""
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(base, 'intel_state.json'), 'intel_state.json'):
        try:
            with open(path, encoding='utf-8') as f:
                state = json.load(f)
            feed = state.get('feed', [])
            if feed:
                return feed[:30]
        except Exception:
            continue
    return []


def load_sector_flow():
    """简易板块：从腾讯/东财接口拉板块资金流，失败返回占位"""
    sectors = []
    try:
        # 东方财富板块资金流（前10）
        url = ('https://push2.eastmoney.com/api/qt/clist/get?'
               'pn=1&pz=12&po=1&np=1&fltt=2&invt=2&fid=f62&fs=m:90+t:2&'
               'fields=f12,f14,f62,f3')
        txt = urllib.request.urlopen(
            urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}),
            timeout=10
        ).read().decode('utf-8', 'ignore')
        data = json.loads(txt)
        for it in (data.get('data') or {}).get('diff') or []:
            name = it.get('f14', '')
            inflow = it.get('f62')
            pct = it.get('f3')
            if name and inflow is not None:
                try:
                    inflow_yi = float(inflow) / 1e8
                except Exception:
                    inflow_yi = 0
                sectors.append({
                    'name': name,
                    'value': round(inflow_yi, 2),
                    'chg': float(pct) if pct is not None else 0,
                })
    except Exception as e:
        print('sector_err', e, file=sys.stderr)
    return sectors[:10]


def main():
    codes = [c for c, _ in INDICES] + [h['code'] for h in HOLDINGS]
    raw = fetch_qt(codes)

    idx_data = {c: raw[c] for c, _ in INDICES if c in raw}
    score = market_temperature(idx_data)
    changes = [idx_data[c]['chg'] for c in idx_data]
    avg_chg = round(sum(changes) / len(changes), 2) if changes else 0
    regime, regime_cn, regime_note = regime_from_score(score, avg_chg)

    signals = []
    for h in HOLDINGS:
        q = raw.get(h['code'])
        if not q:
            signals.append({**h, 'signal': {
                'action': 'watch', 'action_cn': '观望', 'stop': 0, 'target': 0,
                'pos_pct': 0, 'reason': '暂无行情数据', 'pnl': 0, 'price': 0, 'chg': 0
            }})
            continue
        sig = stock_signal(q, h['cost'])
        signals.append({
            'code': h['code'], 'name': q['name'] or h['name'],
            'sector': h['sector'], 'logic': h['logic'],
            'cost': h['cost'], 'shares': h['shares'],
            'signal': sig,
        })

    playbook = build_playbook(regime, score, avg_chg, signals)

    # 简单风险
    total_cost = sum(h['cost'] * h['shares'] for h in HOLDINGS if h['shares'])
    n = len([s for s in signals if s['signal']['action'] != 'watch'])
    risk = 'low'
    if score < 40 or any(s['signal']['action'] == 'stop' for s in signals):
        risk = 'high'
    elif score < 55 or any(s['signal']['action'] == 'reduce' for s in signals):
        risk = 'mid'

    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'market': {
            'score': score,
            'regime': regime,
            'regime_cn': regime_cn,
            'regime_note': regime_note,
            'avg_chg': avg_chg,
            'risk': risk,
            'risk_cn': {'low': '低风险', 'mid': '中风险', 'high': '高风险'}[risk],
            'indices': [
                {'code': c, 'name': idx_data[c]['name'], 'price': idx_data[c]['price'],
                 'chg': idx_data[c]['chg']} for c, _ in INDICES if c in idx_data
            ],
        },
        'signals': signals,
        'playbook': playbook,
        'intel_feed': load_intel_feed(),
        'sectors': load_sector_flow(),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
