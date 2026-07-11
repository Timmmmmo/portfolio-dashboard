#!/usr/bin/env python3
"""每整点获取财经新闻 + 逻辑判断"""
import urllib.request, urllib.parse, json, sys, re
from datetime import datetime, timedelta
from html import unescape

def fetch_news():
    """从多个源获取财经新闻"""
    news = []
    
    # Source 1: 财联社搜索 - 获取最新股市消息
    keywords = ['A股', '股市', '半导体', 'CXO', '新能源', 'AI']
    for kw in keywords:
        try:
            url = f"https://www.cls.cn/searchPage?keyword={urllib.parse.quote(kw)}&type=all"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='replace')
            
            # Extract news text snippets
            texts = re.findall(r'【([^】]+(?:半导体|AI|CXO|医保|芯片|涨停|跌停|大涨|大跌|利好|利空)[^】]*)】', data)
            for t in texts[:3]:
                clean = unescape(re.sub(r'<[^>]+>', '', t)).strip()
                if clean and len(clean) > 8:
                    news.append({'time': datetime.now().strftime('%H:%M'), 'title': clean, 'content': clean})
        except:
            pass
    
    # Source 2: 新浪财经新闻
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=15"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
        for item in data.get('result',{}).get('data',[]):
            title = unescape(re.sub(r'<[^>]+>', '', item.get('title','')))
            if title and len(title) > 8:
                news.append({'time': item.get('ctime','')[-8:], 'title': title[:120], 'content': title[:150]})
    except:
        pass
    
    # Deduplicate
    seen = set()
    unique = []
    for n in news:
        key = n['title'][:25]
        if key not in seen:
            seen.add(key)
            unique.append(n)
    
    return unique[:15]

def analyze(news_texts):
    """逻辑判断"""
    all_text = ' '.join(news_texts)
    rules = [
        ('半导体/AI', '半导体|芯片|HBM|AI芯片|算力|光刻|封测', '产业链催化，利好国产替代'),
        ('AI应用', 'AI|大模型|GPT|Manus|Agent|人工智能', '科技主线催化'),
        ('CXO/医药', 'CXO|创新药|泰格|药明|康龙|生物医药', '板块低位，投融资回暖'),
        ('氦气/特气', '氦气|特气|出口管制|稀有气体', '利好金宏等国内供应商'),
        ('新能源车', '新能源车|比亚迪|宁德|电动车|锂电池', '出海进展催化'),
        ('存储/封测', '存储|DRAM|NAND|HBM|封测|深科技', '利好封测产业链'),
        ('低空经济', '低空经济|飞行汽车|eVTOL|通航', '政策催化方向'),
        ('固态电池', '固态电池|钠离子|下一代电池', '技术迭代方向'),
        ('消费', '消费|白酒|食品|旅游|内需', '内需复苏进度'),
        ('地缘政治', '制裁|关税|地缘|冲突|中美', '关注潜在风险'),
        ('资金面', '北向|外资|流入|流出|成交量', '市场情绪指标'),
        ('短线情绪', '涨停|连板|妖股|游资', '市场活跃度'),
    ]
    result = []
    found = set()
    for topic, pat, comment in rules:
        if re.search(pat, all_text):
            k = pat.split('|')[0]
            if k not in found:
                found.add(k)
                result.append({'topic': topic, 'comment': comment})
    return result[:8]

def main():
    news = fetch_news()
    texts = [n['title'] for n in news]
    analysis = analyze(texts)
    
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'news': news[:10],
        'analysis': analysis,
        'total': len(news),
        'status': 'ok' if news else 'no_data'
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"News: {len(news)}, Analysis: {len(analysis)}", file=sys.stderr)

if __name__ == '__main__':
    main()