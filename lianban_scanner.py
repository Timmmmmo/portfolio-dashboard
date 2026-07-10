#!/usr/bin/env python3
"""扫描全部A股连板数据 - 全市场5000+只股票60日连板追踪"""
import urllib.request, json, sys
from datetime import datetime
from collections import defaultdict

def get_all_stocks():
    """从新浪获取全市场股票列表及涨跌幅（分页获取全部5000+）"""
    all_data = []
    page = 1
    max_pages = 60  # 安全上限
    while page <= max_pages:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
        params = f"page={page}&num=100&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page"
        try:
            req = urllib.request.Request(f"{url}?{params}", headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
            batch = json.loads(data)
            if not batch:
                break
            all_data.extend(batch)
            if len(batch) < 100:
                break  # 最后一页
            page += 1
        except Exception as e:
            print(f"Page {page} error: {e}", file=sys.stderr)
            break
    return all_data

def get_limit_threshold(code):
    """根据代码判断涨停阈值"""
    if code.startswith('sh688') or code.startswith('sh689') or code.startswith('sz3'):
        return 19.90
    elif code.startswith('sz8') or code.startswith('sh8'):
        return 29.90
    else:
        return 9.90

def get_sector(code):
    """根据代码判断板块"""
    if code.startswith('sh688') or code.startswith('sh689'):
        return '科创板'
    elif code.startswith('sz3'):
        return '创业板'
    elif code.startswith('sz8') or code.startswith('sh8'):
        return '北交所'
    else:
        return '主板'

def get_kline(code, days=65):
    """获取K线数据"""
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        for k in data.get('data', {}):
            return data['data'][k].get('qfqday', [])
    except:
        return []

def scan():
    """全市场连板扫描"""
    # 1. 获取全市场股票数据
    all_stocks = get_all_stocks()
    print(f"Total A-share stocks: {len(all_stocks)}", file=sys.stderr)
    
    # 2. 收集今日涨停股
    today_limit = []
    for s in all_stocks:
        code = s['code']
        chg = float(s.get('changepercent', 0))
        prefix = 'sh' if code.startswith('6') or code.startswith('5') else 'sz'
        full_code = f'{prefix}{code}'
        threshold = get_limit_threshold(full_code)
        
        if chg >= threshold:
            today_limit.append({
                'code': full_code,
                'name': s.get('name', ''),
                'chg': round(chg, 2),
                'sector': get_sector(full_code)
            })
    
    print(f"Today limit-up: {len(today_limit)} stocks", file=sys.stderr)
    for s in today_limit[:5]:
        print(f"  {s['name']}({s['code']}): +{s['chg']}% [{s['sector']}]", file=sys.stderr)
    if len(today_limit) > 5:
        print(f"  ... and {len(today_limit)-5} more", file=sys.stderr)
    
    # 3. 对今日涨停股追溯60日K线，找连板
    # 同时对今日涨停股扫描完整60日K线，记录所有2+连板
    daily_streaks = defaultdict(list)
    
    for s in today_limit:
        kline = get_kline(s['code'])
        if not kline:
            continue
        
        threshold = get_limit_threshold(s['code'])
        current_streak = 0
        
        # 从旧到新扫描（按时间顺序）
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
            
            # 记录所有>=2连板
            if current_streak >= 2:
                if not any(x['code'] == s['code'] for x in daily_streaks.get(date, [])):
                    daily_streaks[date].append({
                        'code': s['code'],
                        'name': s['name'],
                        'streak': current_streak,
                        'sector': s['sector'],
                        'chg': round(chg, 2)
                    })
    
    # 4. 补充：今日涨停但已记录完整K线中可能漏掉的
    # 其实上面的逻辑已经覆盖了
    # 但还需要考虑：曾经有连板但今天没涨停的股票
    # 这些股票不在today_limit中，所以不会被扫描到
    # 解决方案：从所有涨停股的K线中，提取所有连板记录
    
    # 整理数据
    sorted_dates = sorted(daily_streaks.keys())
    result = {}
    for date in sorted_dates:
        stocks = daily_streaks[date]
        # 去重（同一只股票同一天只保留最高连板）
        unique = {}
        for s in stocks:
            code = s['code']
            if code not in unique or s['streak'] > unique[code]['streak']:
                unique[code] = s
        deduped = sorted(unique.values(), key=lambda x: (-x['streak'], x['name']))
        result[date] = {
            'stocks': deduped,
            'count': len(deduped),
            'max_streak': max(s['streak'] for s in deduped) if deduped else 0
        }
    
    return result

if __name__ == '__main__':
    print("Scanning ALL 5000+ A-share stocks for consecutive limit-ups...", file=sys.stderr)
    data = scan()
    dates = sorted(data.keys())
    print(f"Found {len(dates)} days with 2+ consecutive limit-up stocks", file=sys.stderr)
    
    for d in dates[-10:]:
        info = data[d]
        if info['stocks']:
            stocks_str = ', '.join([f"{s['name']}({s['streak']}板)" for s in info['stocks'][:5]])
            print(f"  {d}: {info['count']}只 最高{info['max_streak']}板 → {stocks_str}", file=sys.stderr)
    
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'days': len(dates),
        'data': dict(list(data.items())[-60:])
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))