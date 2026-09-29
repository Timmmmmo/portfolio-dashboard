#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A股交易时段时钟 — 盘前/盘中/午休/盘后/休市"""
from datetime import datetime, time


def beijing_now():
    """返回本地时间（GitHub Actions 跑 UTC，这里统一按服务器时区，Actions 里用 TZ=Asia/Shanghai）"""
    return datetime.now()


def market_phase(dt=None):
    """
    返回 (phase, label, next_event_text)
    phase: pre | open | lunch | after | closed
    """
    dt = dt or beijing_now()
    if dt.weekday() >= 5:
        return 'closed', '周末休市', '下周一 09:00 开盘'
    t = dt.time()
    if t < time(8, 0):
        return 'closed', '休市', '今日 09:15 集合竞价'
    if t < time(9, 15):
        return 'closed', '休市', '今日 09:15 集合竞价'
    if t < time(9, 30):
        return 'pre', '盘前集合竞价', '09:30 连续竞价开盘'
    if t < time(11, 30):
        return 'open', '盘中 · 上午', '11:30-13:00 午休'
    if t < time(13, 0):
        return 'lunch', '午间休市', '13:00 下午开盘'
    if t < time(15, 0):
        return 'open', '盘中 · 下午', '15:00 收盘'
    if t < time(15, 30):
        return 'after', '盘后集合竞价/收盘', '15:00 已收盘'
    return 'after', '盘后', '明日 09:15 集合竞价'


def is_trading(dt=None):
    return market_phase(dt)[0] in ('pre', 'open', 'lunch')


def is_intraday(dt=None):
    return market_phase(dt)[0] == 'open'


def next_refresh_seconds(dt=None):
    """距离下一个整点/半点更新的秒数（开盘期间 30 分钟节奏）"""
    dt = dt or beijing_now()
    m, s = dt.minute, dt.second
    if m < 30:
        wait = (30 - m) * 60 - s
    else:
        wait = (60 - m) * 60 - s
    return max(1, wait)


if __name__ == '__main__':
    ph, label, nxt = market_phase()
    print(f'phase={ph} label={label} next={nxt}')
