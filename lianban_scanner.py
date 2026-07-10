#!/usr/bin/env python3
"""生成连板天梯图数据 - 由GH Actions定时调用"""
import urllib.request, json, sys
from datetime import datetime, timedelta

# 扫描热门股票池(成交额前200+龙虎榜常客)
STOCK_POOL = [
    # 科技/半导体
    'sh688981','sz000021','sh603650','sh688106','sh688012','sh002371','sh600171',
    'sh603019','sh688008','sh688126','sh688256','sh688396','sh688005','sh688169',
    # AI/软件
    'sz002230','sh688111','sh600588','sh688568','sh688590','sz300624',
    # 新能源
    'sz300750','sz002594','sh601012','sh600438','sz300274','sh600089',
    # 医药/基因
    'sh688114','sh603259','sz300760','sh600276','sz300347',
    # 金融/券商
    'sh600036','sh600030','sh601318','sh601166','sh600837','sh601688',
    # 军工
    'sh600760','sh600893','sh600862','sh600118','sh600391',
    # 有色/资源
    'sh601899','sh600547','sh600111','sh600010','sz000762',
    # 热门短线
    'sz300059','sh600519','sz000858','sh600809','sh600196',
    # 存储/封测/材料
    'sh603986','sh600584','sh600703','sh600745','sh002185',
    # 科创板热门
    'sh688777','sh688187','sh688223','sh688599','sh688390',
    'sh688200','sh688036','sh688981','sh688126','sh688396',
]

def get_kline(code, days=60):
    """获取60日K线数据"""
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        key = code
        if key not in data.get('data',{}):
            # Try alternative key format
            for k in data.get('data',{}):
                key = k
                break
        return data.get('data',{}).get(key,{}).get('qfqday',[])
    except:
        return []

def get_stock_name(code):
    """获取股票名称"""
    try:
        url = f'https://qt.gtimg.cn/q={code}'
        data = urllib.request.urlopen(url, timeout=5).read().decode('gbk')
        if '~' in data:
            return data.split('~')[1]
    except:
        pass
    return code

def scan_lianban():
    """扫描连板股票"""
    results = []
    
    for code in STOCK_POOL:
        kline = get_kline(code)
        if not kline:
            continue
        
        # 从最新向旧扫描
        current_streak = 0
        max_streak = 0
        today_chg = 0
        
        for i, row in enumerate(reversed(kline)):
            date = row[0]
            op_f = float(row[1]) if row[1] else 0
            cl_f = float(row[2]) if row[2] else 0
            if op_f == 0:
                continue
            chg = (cl_f - op_f) / op_f * 100
            
            if i == 0:
                today_chg = chg
            
            # 判断是否涨停
            is_limit = chg >= 9.90
            
            if is_limit:
                current_streak += 1
                if current_streak > max_streak:
                    max_streak = current_streak
            else:
                # 检查是否接近涨停(>7%但未涨停)
                if chg >= 7.0:
                    current_streak = 0  # 断板
                else:
                    current_streak = 0
                    break  # 不再强势，停止扫描
        
        limit_up = today_chg >= 9.90
        
        if max_streak >= 2 or (max_streak >= 1 and limit_up):
            name = get_stock_name(code)
            # 判断板块
            sector = '其他'
            if code.startswith('sh688') or code.startswith('sh689'):
                sector = '科创板'
            elif code.startswith('sz3'):
                sector = '创业板'
            elif code.startswith('sh6') or code.startswith('sh5'):
                sector = '主板'
            elif code.startswith('sz0') or code.startswith('sz2'):
                sector = '主板'
            
            results.append({
                'code': code,
                'name': name,
                'streak': max_streak,
                'chg': round(today_chg, 2),
                'limit_up': limit_up,
                'sector': sector
            })
    
    # 按连板数降序排列
    results.sort(key=lambda x: (-x['streak'], -x['chg']))
    return results

if __name__ == '__main__':
    print("Scanning for 连板 stocks...", file=sys.stderr)
    results = scan_lianban()
    print(f"Found {len(results)} stocks with 连板", file=sys.stderr)
    
    # 输出JSON
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total': len(results),
        'stocks': results
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))