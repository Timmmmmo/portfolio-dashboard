#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行情快照：指数(新浪,含成交额) + 关注标的(腾讯qt)。输出JSON到stdout。
用法: python snapshot_quotes.py [--stock-only]
"""
import json, ssl, sys, urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}

def get(u, enc='utf-8'):
    return urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=20, context=ctx).read().decode(enc, 'ignore')

# ---------------- 关注清单（合并去重版，与 Dashboard 一致） ----------------
INDICES = [('sh000001', '上证指数'), ('sz399001', '深证成指'), ('sz399006', '创业板指'), ('sh000688', '科创50')]
WATCH = [
    ('sh688106', '金宏气体'), ('sh688114', '华大智造'), ('sz002594', '比亚迪'),
    ('sz000021', '深科技'), ('hk00981', '中芯国际(H)'), ('sh688981', '中芯国际(A)'),
    ('sh600399', '抚顺特钢'), ('sh601020', '华钰矿业'), ('sz300346', '南大光电'),
    ('bj872808', '曙光数创'), ('sh600338', '西藏珠峰'), ('sh603650', '彤程新材'),
    ('sh688507', '索辰科技'), ('sz000762', '西藏矿业'), ('sz300174', '元力股份'),
    ('sh603127', '昭衍新药'),
]

def fetch_indices():
    """新浪指数：f[9] 为成交额(元)"""
    out = []
    try:
        txt = get('https://hq.sinajs.cn/list=' + ','.join(c for c, _ in INDICES), enc='gbk')
        for line in txt.strip().split('\n'):
            if '="' not in line:
                continue
            try:
                key = line.split('hq_str_')[1].split('=')[0]
                f = line.split('"')[1].split(',')
                if len(f) < 32 or not f[3]:
                    continue
                cur, pc = float(f[3]), float(f[2])
                out.append({
                    'code': key, 'name': f[0], 'cur': cur,
                    'pct': round((cur - pc) / pc * 100, 2) if pc else 0,
                    'amt_yi': round(float(f[9]) / 1e8, 0) if f[9] else 0,
                    'time': (f[30] + ' ' + f[31]).strip(),
                })
            except Exception:
                continue
    except Exception as e:
        print('idx_err', e, file=sys.stderr)
    return out

def _qt_fetch(codes):
    """返回 {code_key: parts_list}"""
    res = {}
    url = 'https://qt.gtimg.cn/q=' + codes
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/'})
    data = urllib.request.urlopen(req, timeout=20).read().decode('gbk', 'ignore')
    for line in data.strip().split(';'):
        if '~' not in line:
            continue
        try:
            key = line.split('=')[0].replace('var ', '').replace('v_', '').strip()
            p = line.split('"')[1].split('~')
            if len(p) >= 33 and p[3]:
                res[key] = p
        except Exception:
            continue
    return res

def fetch_stocks():
    """腾讯qt.gtimg.cn：p[1]名 p[3]现价 p[4]昨收 p[32]涨跌幅 p[30]时间（批量失败时逐只补拉）"""
    all_codes = [c for c, _ in WATCH]
    raw = {}
    # 批量，最多3次
    for _ in range(3):
        try:
            raw.update(_qt_fetch(','.join(all_codes)))
        except Exception as e:
            print('stk_batch_err', e, file=sys.stderr)
        if len(raw) >= len(all_codes):
            break
    # 逐只补缺
    for code in all_codes:
        if code in raw:
            continue
        try:
            got = _qt_fetch(code)
            if got:
                raw[code] = got[code]
        except Exception:
            continue
    out = {}
    for key, p in raw.items():
        try:
            cur = float(p[3]) if p[3] else 0
            pct = float(p[32]) if p[32] else 0
            out[key] = {'code': key, 'name': p[1] or key, 'cur': cur, 'pct': pct,
                        'time': p[30] if len(p) > 30 else ''}
        except Exception:
            continue
    result = []
    for code, label in WATCH:
        if code in out and out[code]['cur']:
            result.append(out[code])
        else:
            result.append({'code': code, 'name': label, 'cur': 0, 'pct': None, 'time': ''})
    return result

if __name__ == '__main__':
    stock_only = '--stock-only' in sys.argv
    data = {'watch': fetch_stocks()}
    if not stock_only:
        data['indices'] = fetch_indices()
    print(json.dumps(data, ensure_ascii=False))
