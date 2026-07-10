#!/usr/bin/env python3
"""扫描60日连板数据 - 追踪连续2天以上涨停的股票连线"""
import urllib.request, json, sys
from datetime import datetime
from collections import defaultdict

STOCK_POOL = [
    'sh688981','sz000021','sh603650','sh688106','sh688012','sh002371','sh600171',
    'sh603019','sh688008','sh688126','sh688256','sh688396','sh688005','sh688169',
    'sz002230','sh688111','sh600588','sh688568','sh688590','sz300624',
    'sz300750','sz002594','sh601012','sh600438','sz300274','sh600089',
    'sh688114','sh603259','sz300760','sh600276','sz300347',
    'sh600036','sh600030','sh601318','sh601166','sh600837','sh601688',
    'sh600760','sh600893','sh600862','sh600118','sh600391',
    'sh601899','sh600547','sh600111','sh600010','sz000762',
    'sz300059','sh600519','sz000858','sh600809','sh600196',
    'sh603986','sh600584','sh600703','sh600745','sh002185',
    'sh688777','sh688187','sh688223','sh688599','sh688390',
    'sh688200','sh688036','sh600460','sh600584','sh600171',
    'sz002049','sz300308','sz300394','sz300502','sz300661',
    'sh688536','sh688180','sh688235','sh688266','sh688321',
    'sz002821','sz300015','sz300003','sz300529','sh600529',
    'sh600436','sh600763','sh601012','sh600438','sz300274',
    'sz300124','sz300014','sz300450','sh600884','sh688390',
    'sh688200','sh688036','sh600745','sh002185','sh600171',
    'sz002463','sz002916','sz300661','sh688126','sh688008',
    'sh688012','sh002371','sh600703','sh603986','sz300782',
    'sh600519','sh600809','sz000858','sh600196','sh600036',
    'sz300059','sz000002','sh600048','sh601166','sh600030',
    'sh600837','sh601688','sh601318','sh601628','sh601601',
    'sz002230','sh688111','sh600588','sh688568','sh688590',
    'sz300624','sz002624','sh603444','sh600118','sh600760',
    'sh600893','sh600862','sh600391','sh600150','sh600685',
    'sh600482','sz000768','sz000738','sz300347','sh603259',
    'sz300760','sh600276','sz300003','sz300015','sh600529',
    'sh688266','sh688185','sh688301','sz300750','sz300274',
    'sh600438','sh601012','sz002594','sz002460','sz002709',
    'sz300450','sh600884','sh603799','sh688005','sh688169',
    'sh688981','sh688256','sh688126','sh688396','sh688008',
    'sh688012','sh688200','sh688036','sh688223','sh688187',
    'sh688390','sh688777','sh688599','sh688536','sh688180',
    'sh688235','sh688266','sh688321','sz300059','sz000762',
    'sh600010','sh601899','sh600547','sh600111','sz002466',
    'sz002460','sh600392','sz000831','sz000021','sh688106',
    'sh603650','sh603986','sh688981','sh600584','sh600745',
    'sh002185','sz002049','sh688396',
]

def get_kline(code, days=65):
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        for k in data.get('data',{}):
            return data['data'][k].get('qfqday', [])
    except:
        return []

def get_name(code):
    try:
        url = f'https://qt.gtimg.cn/q={code}'
        d = urllib.request.urlopen(url, timeout=3).read().decode('gbk')
        if '~' in d: return d.split('~')[1]
    except: pass
    return code

def scan():
    """扫描所有股票，追踪连板数据"""
    # 先收集所有股票的K线
    all_data = {}  # code -> [(date, chg)]
    
    for code in STOCK_POOL:
        kline = get_kline(code)
        if not kline: continue
        daily = []
        for row in kline:
            date = str(row[0])
            op = float(row[1]) if row[1] else 0
            cl = float(row[2]) if row[2] else 0
            if op == 0: continue
            chg = (cl - op) / op * 100
            daily.append((date, chg))
        if daily:
            all_data[code] = daily
    
    print(f"Scanned {len(all_data)} stocks", file=sys.stderr)
    
    # 对每只股票追踪连板
    # 结果: date -> { 'stocks': [ {code, name, streak, sector}, ... ] }
    daily_streaks = defaultdict(list)
    
    for code, data in all_data.items():
        current_streak = 0
        
        for date, chg in data:
            # 根据板块判断涨停阈值
            # 主板(60xxxx/00xxxx/002xxx): 10%
            # 创业板(30xxxx): 20%
            # 科创板(688xxx/689xxx): 20%
            # 北交所(8xxxxx): 30%
            if code.startswith('sh688') or code.startswith('sh689') or code.startswith('sz3'):
                limit_chg = 19.90  # 科创/创业板 20%涨停
            elif code.startswith('sz8') or code.startswith('sh8'):
                limit_chg = 29.90  # 北交所 30%涨停
            else:
                limit_chg = 9.90   # 主板 10%涨停
            
            is_limit = chg >= limit_chg
            if is_limit:
                current_streak += 1
            else:
                current_streak = 0
            
            # 只有在连板>=2时才记录
            if current_streak >= 2:
                sector = '科创板' if code.startswith('sh688') else '创业板' if code.startswith('sz3') else '主板'
                daily_streaks[date].append({
                    'code': code,
                    'name': get_name(code),
                    'streak': current_streak,
                    'sector': sector,
                    'chg': round(chg, 2)
                })
    
    # 排序：按日期和连板数
    sorted_dates = sorted(daily_streaks.keys())
    
    result = {}
    for date in sorted_dates:
        stocks = daily_streaks[date]
        # 按连板数降序
        stocks.sort(key=lambda x: (-x['streak'], x['name']))
        result[date] = {
            'stocks': stocks,
            'count': len(stocks),
            'max_streak': max(s['streak'] for s in stocks) if stocks else 0
        }
    
    return result

if __name__ == '__main__':
    print("Scanning consecutive limit-up streaks...", file=sys.stderr)
    data = scan()
    dates = sorted(data.keys())
    print(f"Found {len(dates)} days with 2+ consecutive limit-up stocks", file=sys.stderr)
    
    # 显示最近几天的数据
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