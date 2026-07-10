#!/usr/bin/env python3
"""生成持仓Dashboard HTML - 由GitHub Actions定时调用"""
import urllib.request, json, re, os, sys
from datetime import datetime

# ========== 配置 ==========
HOLDINGS = [
    ('sh688981', '中芯国际', 'AI芯片制造龙头', '半导体制造→AI芯片→HBM/GPU', '中国最先进制程，AI芯片刚需', '地缘政治限制设备进口'),
    ('sz000021', '深科技', '存储封测铲子', '封测→长鑫/长存→AI服务器', 'HBM挤压通用DRAM→封测需求增，14.7亿扩产', 'HBM仍在研发'),
    ('sh603650', '彤程新材', '光刻胶国产替代', '光刻胶→晶圆制造→芯片', 'ArF/KrF光刻胶国产龙头，中芯绑定深', '高端光刻胶仍在验证'),
    ('sh688106', '金宏气体', '特气/氦气龙头', '氦气/特气→半导体制造', '氦气物理不可替代，90%进口，国产替代', 'PE 219偏高'),
    ('sh688114', '华大智造', '基因测序国产龙头', '测序仪→医院/药企→精准医疗', '国产测序唯一标的，全球第三', '集采政策风险'),
    ('sh688507', '索辰科技', 'CAE仿真软件', 'CAE软件→军工/车企→研发', '国产CAE龙头，军工市占率第一', '客户拓展慢'),
    ('sz002594', '比亚迪', '新能源车龙头', '新能源车→电池→出海', '销量全球第一，出海加速', '价格战激烈'),
    ('sz000762', '西藏矿业', '锂矿', '锂矿→碳酸锂→电池', '罗洄说还没到底，等信号', '锂价低迷'),
    ('sz300174', '元力股份', '超级电容/活性炭', '超级电容→储能→新能源', '从底部企稳中', '市场规模有限')
]

def fetch_stock_data(code_list):
    codes = ','.join(code_list)
    url = f'https://qt.gtimg.cn/q={codes}'
    try:
        req = urllib.request.Request(url)
        data = urllib.request.urlopen(req, timeout=10).read().decode('gbk')
        result = {}
        for line in data.strip().split(';'):
            if line.strip() and '~' in line:
                try:
                    code_key = line.split('=')[0].replace('var ', '').strip()
                    parts = line.split('~')
                    result[code_key] = parts
                except: pass
        return result
    except Exception as e:
        print(f"Stock fetch error: {e}", file=sys.stderr)
        return {}

def fetch_global_data():
    req = urllib.request.Request('https://hq.sinajs.cn/list=hf_NQ,hf_HSI,hf_GC,hf_CL',
        headers={'Referer': 'https://finance.sina.com.cn/'})
    try:
        data = urllib.request.urlopen(req, timeout=8).read().decode('gbk')
        result = {}
        for line in data.strip().split(';'):
            if line.strip() and '"' in line:
                vals = line.split('"')[1].split(',')
                if vals[0] and float(vals[0]) > 0:
                    name = vals[-1] if vals[-1] else "?"
                    price = float(vals[0])
                    prev = float(vals[7]) if vals[7] else price
                    chg = round((price - prev) / prev * 100, 2) if prev else 0
                    result[name] = (price, chg)
        return result
    except Exception as e:
        print(f"Global fetch error: {e}", file=sys.stderr)
        return {}

def safe_idx(idx_data, code, idx=0):
    """安全获取指数数据"""
    key = f'v_{code}'
    if key in idx_data:
        try:
            parts = idx_data[key]
            name = parts[1]
            p = float(parts[3])
            c = float(parts[4])
            chg = round((p-c)/c*100, 2) if c else 0
            return (name, p, chg)
        except:
            pass
    return ('--', 0, 0)

def safe_stock(stock_data, code):
    """安全获取股票数据"""
    key = f'v_{code}'
    if key in stock_data:
        try:
            parts = stock_data[key]
            p = float(parts[3])
            c = float(parts[4])
            chg = round((p-c)/c*100, 2) if c else 0
            return (p, chg)
        except:
            pass
    return (0, 0)

def generate_html(stock_data, global_data):
    now = datetime.now()
    time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    bjt_h = now.hour + 8 if now.utcoffset() else now.hour
    is_market = (bjt_h >= 9 and bjt_h < 15) or (bjt_h == 9 and now.minute >= 30)
    refresh_interval = 120 if is_market else 1800
    
    # 指数
    idx_names = {'sh000001':'上证指数','sz399001':'深证成指','sz399006':'创业板指','sh000688':'科创50'}
    idx_html = ''
    for code, label in idx_names.items():
        name, price, chg = safe_idx(stock_data, code)
        color = '#34d399' if chg > 0 else ('#f87171' if chg < 0 else '#94a3b8')
        is_kc = 'style="border:1px solid #334155"' if code == 'sh000688' else ''
        kc_name = '<span style="color:#38bdf8">科创50 🚀</span>' if code == 'sh000688' else label
        idx_html += f'<div class="index-item" {is_kc}><div class="name">{kc_name}</div><div class="val" style="color:{color}">{price:.2f}</div><div class="pct" style="color:{color}">{chg:+.2f}%</div></div>'
    
    # 全球
    global_rows = ''
    for name, (price, chg) in global_data.items():
        c = 'up' if chg > 0 else ('down' if chg < 0 else 'flat')
        global_rows += f'<div class="global-item"><span class="g-name">{name}</span><span class="g-val">{price:.1f}</span><span class="chg chg-{c}">{"+" if chg>0 else ""}{chg}%</span></div>'
    
    # 持仓
    portfolio_rows = ''
    for code, cname, desc, chain, logic, risk in HOLDINGS:
        price, chg = safe_stock(stock_data, code)
        chg_class = 'up' if chg > 0.5 else ('down' if chg < -0.5 else 'flat')
        chg_str = f"+{chg}%" if chg > 0 else f"{chg}%"
        
        sig = 'buy' if chg > 5 else ('watch' if chg < -3 else ('sell' if chg < -5 else 'hold'))
        sig_text = '🔥强势' if chg > 5 else ('📈上涨' if chg > 2 else ('⚠️关注' if chg < -3 else ('💀警惕' if chg < -5 else '持有')))
        
        price_str = f'{price:.2f}' if price else '--'
        
        portfolio_rows += f'''
    <div class="card">
      <div class="card-header"><span class="card-dot" style="background:{"#34d399" if chg>0 else "#f87171"}"></span>{desc}</div>
      <div class="price-row">
        <span class="price-val">{price_str}</span>
        <span class="chg chg-{chg_class}">{chg_str}</span>
      </div>
      <div class="chain">🔗 {chain}</div>
      <div class="msg msg-info">✅ {logic}</div>
      <div class="msg msg-warn">⚠️ {risk}</div>
      <div class="signal sig-{sig}">{sig_text}</div>
    </div>'''
    
    # 新闻
    news_items = [
        ('今', '科创50', f'7连涨后今日回调', 'info'),
        ('今', '深科技', f'两天从51→61，+19.7%验证封测逻辑', 'ok'),
        ('今', '华大', '基因测序赛道回暖，+4.63%', 'ok'),
        ('今', '金宏', '关注36支撑位，氦气逻辑未破', 'warn'),
        ('昨夜', '美股', '纳指+1.30%，纳指100+1.62%，科技强势', 'ok'),
        ('昨夜', 'SK海力士', 'ADR上市计划筹集40万亿韩元', 'info'),
        ('7/9', '罗洄头', '沉默第3天，判断全部应验', 'info'),
        ('7/9', '科创50', '昨日+8.41%创纪录！中芯涨停+13.74%', 'ok')
    ]
    news_html = ''
    for t, tag, text, tp in news_items:
        tc = '#34d399' if tp == 'ok' else ('#f87171' if tp == 'warn' else '#38bdf8')
        news_html += f'<div class="news-item"><span class="news-time">{t}</span><span class="news-tag" style="color:{tc}">{tag}</span><span class="news-text">{text}</span></div>'
    
    # 分析
    analysis = [
        ('🧠', '科创50今日回调正常，7连涨后休息一下', 'hold'),
        ('🔥', '深科技验证"存储封测铲子"逻辑，HBM挤压通用DRAM', 'buy'),
        ('💡', '华大加速，基因测序是AI在医疗最直接的应用', 'buy'),
        ('⚠️', '金宏跌至36.4，氦气逻辑未破(物理不可替代)，36支撑', 'watch'),
        ('📊', '中芯从173回落，涨停后正常回调，AI芯片逻辑不变', 'hold'),
        ('🌍', '纳指+1.30%+日经+1.71%→全球科技共振仍在', 'hold')
    ]
    analysis_html = ''
    for tag, text, tp in analysis:
        analysis_html += f'<div class="analysis-item"><span class="analysis-tag analysis-{tp}">{tag}</span><span class="news-text">{text}</span></div>'
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="{refresh_interval}">
<title>📊 持仓实时Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;padding:16px}}
h1{{font-size:22px;display:flex;align-items:center;gap:8px}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px}}
.stats{{font-size:12px;color:#94a3b8;display:flex;gap:12px;align-items:center}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;margin-bottom:16px}}
.card{{background:#1e293b;border-radius:10px;padding:14px;border:1px solid #334155}}
.card-header{{font-size:13px;color:#38bdf8;margin-bottom:8px;display:flex;align-items:center;gap:6px}}
.card-dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.price-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.price-val{{font-size:24px;font-weight:700}}
.chg{{padding:2px 8px;border-radius:4px;font-size:14px;font-weight:600}}
.chg-up{{background:#064e3b;color:#34d399}}
.chg-down{{background:#450a0a;color:#f87171}}
.chg-flat{{background:#1e293b;color:#94a3b8}}
.chain{{font-size:11px;color:#64748b;padding:6px 8px;background:#0f172a;border-radius:6px;margin-top:6px;line-height:1.5}}
.msg{{background:#0f172a;border-radius:6px;padding:6px 8px;margin-top:6px;font-size:11px;line-height:1.5;border-left:2px solid #38bdf8}}
.msg-warn{{border-left-color:#f87171}}
.msg-info{{border-left-color:#38bdf8}}
.signal{{text-align:right;font-size:11px;margin-top:4px;padding:2px 8px;border-radius:4px;display:inline-block;float:right}}
.sig-buy{{background:#064e3b;color:#34d399}}
.sig-hold{{background:#1e293b;color:#fbbf24}}
.sig-watch{{background:#450a0a;color:#f87171}}
.sig-sell{{background:#7f1d1d;color:#ef4444}}
.index-grid,.global-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-bottom:12px}}
.index-item,.global-item{{background:#0f172a;border-radius:8px;padding:8px;text-align:center}}
.index-item .name{{font-size:11px;color:#64748b}}
.index-item .val{{font-size:16px;font-weight:700;margin:2px 0}}
.index-item .pct{{font-size:12px}}
.g-name{{font-size:11px;color:#94a3b8;display:block}}
.g-val{{font-size:14px;font-weight:700;display:block;margin:2px 0}}
.news-section,.analysis-section{{background:#1e293b;border-radius:10px;padding:14px;border:1px solid #334155;margin-bottom:16px}}
.section-title{{font-size:13px;color:#38bdf8;margin-bottom:8px;display:flex;align-items:center;gap:6px}}
.news-item{{padding:6px 0;border-bottom:1px solid #0f172a;font-size:12px;display:flex;gap:8px;align-items:flex-start}}
.news-item:last-child{{border:none}}
.news-tag{{background:#0f172a;padding:1px 6px;border-radius:3px;font-size:10px;white-space:nowrap}}
.news-time{{color:#475569;font-size:10px;white-space:nowrap}}
.news-text{{color:#cbd5e1}}
.analysis-item{{padding:4px 0;font-size:12px;display:flex;gap:8px;align-items:flex-start}}
.analysis-tag{{background:#0f172a;padding:1px 6px;border-radius:3px;font-size:10px;white-space:nowrap}}
.analysis-buy{{color:#34d399}}
.analysis-hold{{color:#fbbf24}}
.analysis-watch{{color:#f87171}}
.footer{{text-align:center;color:#475569;font-size:11px;padding:12px;border-top:1px solid #1e293b;margin-top:16px}}
</style>
</head>
<body>

<div class="header">
  <h1>📊 持仓实时Dashboard</h1>
  <div class="stats">
    <span>🟢 实时</span>
    <span>{time_str}</span>
    <span>每{refresh_interval}秒自动刷新</span>
  </div>
</div>

<div class="card" style="margin-bottom:12px">
  <div class="index-grid">{idx_html}</div>
  <div class="global-grid">{global_rows}</div>
</div>

<div class="grid">{portfolio_rows}</div>

<div class="news-section">
  <div class="section-title">📰 相关新闻</div>
  {news_html}
</div>

<div class="analysis-section">
  <div class="section-title">🧠 底层逻辑判断</div>
  {analysis_html}
</div>

<div class="footer">
  📊 每{refresh_interval}秒自动刷新 | 数据来源: 腾讯财经API | Generated at {time_str}
</div>

</body>
</html>'''

if __name__ == '__main__':
    print("Fetching stock data...", file=sys.stderr)
    stock_codes = ['sh000001','sz399001','sz399006','sh000688'] + [h[0] for h in HOLDINGS]
    stock_data = fetch_stock_data(stock_codes)
    print(f"Got {len(stock_data)} stocks", file=sys.stderr)
    
    print("Fetching global data...", file=sys.stderr)
    global_data = fetch_global_data()
    print(f"Got {len(global_data)} global items", file=sys.stderr)
    
    html = generate_html(stock_data, global_data)
    print(html)