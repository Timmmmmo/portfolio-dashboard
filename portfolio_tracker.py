#!/usr/bin/env python3
"""持仓跟踪分析 - 每日盘后/周末生成持仓分析报告"""
import urllib.request, json, sys, re
from datetime import datetime

HOLDINGS = {
    'hk00981': {'name': '中芯国际(H)', 'sector': 'AI芯片', 'desc': '中国最先进制程代工厂'},
    'sz000021': {'name': '深科技', 'sector': '存储封测', 'desc': '存储封测铲子龙头'},
    'sh603650': {'name': '彤程新材', 'sector': '光刻胶', 'desc': 'ArF/KrF光刻胶国产龙头'},
    'sh688106': {'name': '金宏气体', 'sector': '特气/氦气', 'desc': '氦气不可替代+出口禁令受益'},
    'sh688114': {'name': '华大智造', 'sector': '基因测序', 'desc': '国产测序唯一标的'},
    'sh688507': {'name': '索辰科技', 'sector': 'CAE仿真', 'desc': '国产CAE+军工市占率第一'},
    'sz002594': {'name': '比亚迪', 'sector': '新能源车', 'desc': '全球销量冠军'},
    'sz000762': {'name': '西藏矿业', 'sector': '锂矿', 'desc': '锂矿周期底部'},
    'sz300174': {'name': '元力股份', 'sector': '超级电容', 'desc': '底部企稳中'},
}

def fetch_prices():
    """获取持仓实时价格"""
    codes = ','.join(HOLDINGS.keys())
    try:
        req = urllib.request.Request(f'https://qt.gtimg.cn/q={codes}', headers={'User-Agent': 'Mozilla/5.0'})
        data = urllib.request.urlopen(req, timeout=8).read().decode('gbk')
        prices = {}
        for line in data.split(';'):
            if '~' not in line: continue
            eq = line.find('=')
            if eq < 0: continue
            code = line[:eq].replace('var ', '').strip()
            parts = line[eq+2:line.rfind('"')].split('~')
            if len(parts) > 4:
                price = float(parts[3]) if parts[3] else 0
                prev = float(parts[4]) if parts[4] else price
                chg = ((price - prev) / prev * 100) if prev else 0
                prices[code] = {'price': price, 'chg': round(chg, 2)}
        return prices
    except:
        return {}

def analyze_portfolio(prices, news_analysis):
    """基于持仓数据和新闻分析生成跟踪报告"""
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    period = '周末' if is_weekend else '盘后'
    
    reports = []
    for code, info in HOLDINGS.items():
        p = prices.get(code, {})
        pr = p.get('price', 0)
        chg = p.get('chg', 0)
        
        # 基础状态
        if pr == 0:
            status = '⏳ 等待数据'
            signal = 'hold'
        elif chg > 3:
            status = '🔥 强势'
            signal = 'buy'
        elif chg > 1:
            status = '📈 上涨'
            signal = 'buy'
        elif chg < -5:
            status = '⚠️ 大跌关注'
            signal = 'watch'
        elif chg < -3:
            status = '📉 回调'
            signal = 'watch'
        else:
            status = '💤 横盘'
            signal = 'hold'
        
        reports.append({
            'code': code,
            'name': info['name'],
            'sector': info['sector'],
            'price': pr,
            'chg': chg,
            'status': status,
            'signal': signal,
            'desc': info['desc']
        })
    
    # 整合新闻分析
    news_summary = []
    if news_analysis:
        for a in news_analysis[:5]:
            news_summary.append(f"{a['topic']}: {a['comment']}")
    
    return {
        'update_time': now.strftime('%Y-%m-%d %H:%M'),
        'period': period,
        'date': now.strftime('%Y-%m-%d'),
        'holdings': reports,
        'news_summary': news_summary,
        'total': len(reports)
    }

def main():
    prices = fetch_prices()
    
    # Try to read news analysis if available
    news_analysis = []
    try:
        with open('news_data.json') as f:
            nd = json.load(f)
            news_analysis = nd.get('analysis', [])
    except:
        pass
    
    report = analyze_portfolio(prices, news_analysis)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Portfolio: {report['total']} holdings, period: {report['period']}", file=sys.stderr)

if __name__ == '__main__':
    main()