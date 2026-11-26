# -*- coding: utf-8 -*-
"""从模拟仓账本生成看板数据 sim_portfolio.json（含实时价/浮盈/买卖流水）。
用法: python tools/sync_sim.py
数据源: C:/Users/hjzha/WorkBuddy/Claw/paper-trading/portfolio.json
"""
import json, os, urllib.request, datetime

SRC = r"C:/Users/hjzha/WorkBuddy/Claw/paper-trading/portfolio.json"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sim_portfolio.json")
UA = {"User-Agent": "Mozilla/5.0"}


def fetch_quotes(codes):
    if not codes:
        return {}
    try:
        txt = urllib.request.urlopen(
            urllib.request.Request("http://qt.gtimg.cn/q=" + ",".join(codes), headers=UA),
            timeout=10).read().decode("gbk", "ignore")
        out = {}
        for ln in txt.strip().split(";"):
            if "=" not in ln:
                continue
            var, val = ln.split("=", 1)
            raw = var.replace("v_", "").strip()  # e.g. sz300308 / sh600000
            f = val.strip().strip('"').split("~")
            if len(f) > 32:
                try:
                    out[raw] = {"price": float(f[3]), "pct": float(f[32])}
                except Exception:
                    pass
            # 兼容：也用纯数字代码建键
            if len(f) > 32 and f[2]:
                try:
                    out.setdefault(f[2], {"price": float(f[3]), "pct": float(f[32])})
                except Exception:
                    pass
        return out
    except Exception:
        return {}


def main():
    pf = json.load(open(SRC, encoding="utf-8"))
    acct = pf["account"]
    positions = pf.get("positions", [])
    trades = pf.get("trades", [])
    quotes = fetch_quotes([p["code"] for p in positions])

    pos_view = []
    float_pl = 0.0
    for p in positions:
        q = quotes.get(p["code"], {})
        price = q.get("price", 0)
        cost = p["avg_cost"]
        shares = p["shares"]
        pl = round((price - cost) * shares, 2) if price else 0
        float_pl += pl
        # T+1 可卖数量
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        sellable = sum(l["shares"] for l in p.get("lots", []) if l.get("date", "") < today)
        pos_view.append({
            "code": p["code"], "name": p["name"], "shares": shares,
            "cost": cost, "price": price, "pct": q.get("pct", 0),
            "float_pl": pl, "float_pct": round((price / cost - 1) * 100, 2) if cost and price else 0,
            "batches": p.get("batches", 0), "entry_time": p.get("entry_time", ""),
            "sellable_today": sellable, "locked_today": shares - sellable,
        })

    # 买卖流水：最近30条，最新在前
    trade_view = []
    for t in trades[-30:][::-1]:
        trade_view.append({
            "time": t.get("time", ""), "action": t.get("action", ""),
            "name": t.get("name", ""), "code": t.get("code", ""),
            "price": t.get("price", 0), "shares": t.get("shares", 0),
            "amount": t.get("amount", 0), "rule": t.get("rule", ""),
            "reason": t.get("reason", ""),
        })

    data = {
        "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": {
            "cash": acct["cash"], "position_value": acct["position_value"],
            "total_asset": acct["total_asset"], "total_pnl": acct["total_pnl"],
            "total_return_pct": acct["total_return_pct"], "float_pl": round(float_pl, 2),
        },
        "positions": pos_view,
        "trades": trade_view,
        "note": "野人×六边形逻辑模拟仓 · 非投资建议 · A股T+1当日买入次日可卖",
    }
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("WROTE", OUT, "| positions", len(pos_view), "| trades", len(trade_view),
          "| float_pl", round(float_pl, 2))


if __name__ == "__main__":
    main()
