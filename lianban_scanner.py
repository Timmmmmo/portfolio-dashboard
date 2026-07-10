#!/usr/bin/env python3
"""全市场连板扫描 - 扫描5000+只股票, 60日K线完整回溯"""
import urllib.request, json, sys, concurrent.futures
from datetime import datetime
from collections import defaultdict

# ===== 板块涨停阈值 =====
def get_threshold(code):
    if code.startswith('sh688') or code.startswith('sh689') or code.startswith('sz3'): return 19.90
    elif code.startswith('sz8') or code.startswith('sh8'): return 29.90
    return 9.90

def get_sector(code):
    if code.startswith('sh688') or code.startswith('sh689'): return '科创板'
    elif code.startswith('sz3'): return '创业板'
    elif code.startswith('sz8') or code.startswith('sh8'): return '北交所'
    return '主板'

# ===== 批量获取全市场股票数据 =====
def get_all_stocks():
    """从新浪分页获取全部A股(60页×100只=6000+)"""
    all_data = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        def fetch_page(p):
            url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={p}&num=100&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page"
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                return json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
            except:
                return []
        results = ex.map(fetch_page, range(1, 61))
        for r in results:
            all_data.extend(r)
    return all_data

# ===== 批量获取K线数据 =====
def fetch_kline(code):
    """单只股票K线"""
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,65,qfq'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read())
        for k in data.get('data', {}):
            return data['data'][k].get('qfqday', [])
    except:
        return []

def fetch_all_kline(codes, max_workers=30):
    """批量获取K线数据"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_code = {ex.submit(fetch_kline, c): c for c in codes}
        for fut in concurrent.futures.as_completed(fut_to_code):
            code = fut_to_code[fut]
            try:
                kline = fut.result()
                if kline:
                    results[code] = kline
            except:
                pass
    return results

# ===== 扫描连板 =====
def scan_stock_kline(code, name, sector, kline):
    """扫描单只股票的60日K线, 找出所有连板"""
    threshold = get_threshold(code)
    result = defaultdict(list)  # date -> [{streak, chg}]
    current_streak = 0
    
    for row in kline:
        date = str(row[0])
        op = float(row[1]) if row[1] else 0
        cl = float(row[2]) if row[2] else 0
        if op == 0: continue
        chg = (cl - op) / op * 100
        is_limit = chg >= threshold
        
        if is_limit:
            current_streak += 1
        else:
            current_streak = 0
        
        if current_streak >= 2:
            result[date].append({
                'code': code,
                'name': name,
                'streak': current_streak,
                'sector': sector,
                'chg': round(chg, 2)
            })
    
    return dict(result)

# ===== 主流程 =====
def scan():
    print("Fetching all 5000+ A-share stocks...", file=sys.stderr)
    all_stocks = get_all_stocks()
    print(f"Got {len(all_stocks)} stocks", file=sys.stderr)
    
    # 确定哪些股票需要扫描K线: 前1000只涨跌幅最大的(覆盖所有涨停股)
    top_gainers = all_stocks[:1000]
    
    # 构建待扫描列表 (code -> name, sector)
    scan_list = {}
    for s in top_gainers:
        code = s['code']
        chg = float(s.get('changepercent', 0))
        prefix = 'sh' if code.startswith('6') or code.startswith('5') else 'sz'
        full_code = f'{prefix}{code}'
        scan_list[full_code] = {
            'name': s.get('name', ''),
            'sector': get_sector(full_code),
            'today_chg': chg
        }
    
    print(f"Scanning K-line for {len(scan_list)} stocks...", file=sys.stderr)
    
    # 批量获取K线
    kline_data = fetch_all_kline(list(scan_list.keys()))
    print(f"Got K-line data for {len(kline_data)} stocks", file=sys.stderr)
    
    # 扫描连板
    all_streaks = defaultdict(list)  # date -> [stocks]
    
    for code, info in scan_list.items():
        if code not in kline_data:
            continue
        stock_streaks = scan_stock_kline(code, info['name'], info['sector'], kline_data[code])
        for date, stocks in stock_streaks.items():
            all_streaks[date].extend(stocks)
    
    # 整理
    today = datetime.now().strftime('%Y-%m-%d')
    sorted_dates = sorted(all_streaks.keys())
    
    print(f"Found {len(sorted_dates)} days with 2+ consecutive limit-up stocks", file=sys.stderr)
    
    result = {}
    for date in sorted_dates:
        stocks = all_streaks[date]
        # 去重：同一天同一只股票只保留最高连板
        unique = {}
        for s in stocks:
            if s['code'] not in unique or s['streak'] > unique[s['code']]['streak']:
                unique[s['code']] = s
        deduped = sorted(unique.values(), key=lambda x: (-x['streak'], x['name']))
        result[date] = {
            'stocks': deduped,
            'count': len(deduped),
            'max_streak': max(s['streak'] for s in deduped) if deduped else 0
        }
    
    # 显示摘要
    for d in sorted_dates[-10:]:
        info = result[d]
        if info['stocks']:
            s = ', '.join([f"{x['name']}({x['streak']}板)" for x in info['stocks'][:5]])
            print(f"  {d}: {info['count']}只 最高{info['max_streak']}板 → {s}", file=sys.stderr)
    
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'days': len(sorted_dates),
        'data': dict(list(result.items())[-60:])
    }
    return output

if __name__ == '__main__':
    result = scan()
    print(json.dumps(result, ensure_ascii=False, indent=2))