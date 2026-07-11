#!/usr/bin/env python3
"""整点获取财经新闻 + 链接 + 逻辑判断"""
import urllib.request, urllib.parse, json, sys, re
from datetime import datetime, timedelta
from html import unescape

def fetch_news():
    """获取20条热门财经新闻+链接"""
    news = []
    
    # Source 1: 新浪财经滚动新闻 (包含链接)
    try:
        for page in [1, 2]:
            url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=15&page={page}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = json.loads(urllib.request.urlopen(req, timeout=8).read().decode('utf-8'))
            for item in data.get('result',{}).get('data',[]):
                title = unescape(re.sub(r'<[^>]+>', '', item.get('title',''))).strip()
                link = item.get('url', '') or item.get('link', '')
                ctime = item.get('ctime', '')
                # Format time
                t = ctime[-8:] if len(ctime) >= 8 else ctime
                if title and len(title) > 8:
                    news.append({'time': t, 'title': title[:150], 'content': title[:150], 'url': link})
    except Exception as e:
        print(f"Sina error: {e}", file=sys.stderr)
    
    # Source 2: 财联社搜索 (热门关键词)
    keywords = ['A股', '股市', '半导体', 'CXO', '新能源', 'AI', '涨停', '行情']
    for kw in keywords:
        try:
            url = f"https://www.cls.cn/searchPage?keyword={urllib.parse.quote(kw)}&type=all"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=8).read().decode('utf-8', errors='replace')
            
            # Extract news with links
            # CLS links are like https://www.cls.cn/detail/XXXXX
            items = re.findall(r'<a[^>]*href="(https?://www\.cls\.cn/detail/\d+)"[^>]*>([^<]+)</a>', data)
            for link, title in items[:3]:
                title = unescape(re.sub(r'<[^>]+>', '', title)).strip()
                if title and len(title) > 8:
                    # Check for duplicates
                    if not any(title[:20] == n['title'][:20] for n in news):
                        news.append({'time': datetime.now().strftime('%H:%M'), 'title': title[:150], 'content': title[:150], 'url': link})
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
    
    return unique[:20]

def analyze(news_texts):
    """逻辑判断"""
    all_text = ' '.join(news_texts)
    rules = [
        ('半导体/AI', '半导体|芯片|HBM|AI芯片|算力|光刻|封测', '产业链催化，利好国产替代'),
        ('AI应用', 'AI|大模型|GPT|Manus|Agent|人工智能', '科技主线持续催化'),
        ('CXO/医药', 'CXO|创新药|泰格|药明|康龙|生物医药', '板块低位，投融资回暖'),
        ('氦气/特气', '氦气|特气|出口管制|稀有气体', '利好金宏等国内供应商'),
        ('新能源车', '新能源车|比亚迪|宁德|电动车|锂电池', '出海进展催化'),
        ('存储/封测', '存储|DRAM|NAND|HBM|封测|深科技|SK海力士', '利好封测产业链'),
        ('低空经济', '低空经济|飞行汽车|eVTOL|通航', '政策催化方向'),
        ('固态电池', '固态电池|钠离子|下一代电池', '技术迭代方向'),
        ('地缘政治', '制裁|关税|地缘|冲突|中美|伊朗', '关注潜在风险'),
        ('资金面', '北向|外资|流入|流出|成交量|万亿', '市场情绪指标'),
        ('短线情绪', '涨停|连板|妖股|游资|解禁', '市场活跃度指标'),
        ('消费/游戏', '消费|白酒|旅游|游戏|暑期|票房', '内需复苏进度'),
        ('金融/券商', '券商|银行|保险|MSCI|富时', '权重股表现'),
        ('天气/灾害', '台风|暴雨|洪水|预警|灾害', '关注受损行业'),
    ]
    result = []
    found = set()
    for topic, pat, comment in rules:
        if re.search(pat, all_text):
            k = pat.split('|')[0]
            if k not in found:
                found.add(k)
                result.append({'topic': topic, 'comment': comment})
    return result[:10]

def main():
    news = fetch_news()
    texts = [n['title'] for n in news]
    analysis = analyze(texts)
    
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'news': news[:20],
        'analysis': analysis,
        'total': len(news),
        'status': 'ok' if news else 'no_data'
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"News: {len(news)}, Analysis: {len(analysis)}", file=sys.stderr)

if __name__ == '__main__':
    main()