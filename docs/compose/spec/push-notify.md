---
feature: push-notify
status: delivered
updated: 2026-09-29
branch: main
commits: fef0aec..c5ed88b
---

# Server酱推送通知

## Report

**What was built** — 新增 `notify.py`，支持 Server酱微信推送：盘中关键警报（止损/减仓，同日去重）与盘后复盘（市场状态+剧本+持仓信号+板块资金流）。`update.yml` 在数据抓取后调用，北京时间 ≥15:00 自动切换为复盘模式；无 `SERVERCHAN_KEY` 时静默跳过。SendKey 存放在 GitHub Actions Secret，不进仓库。

**Verification** — `notify.py` 本地格式/去重测试 PASS（7 条关键信号文案正确，指纹去重生效）；Actions 跑次 `36528354988` 步骤「Server酱推送」日志 `alert: sent True ... SUCCESS pushid:58962481`；全 job `completed/success`。

**Journey log** —
1. 本机无 nacl/cryptography，无法用 API 写 Secret，改由用户在 GitHub 网页添加，更稳。
2. GitHub API/ git push 在本时段网络抖动严重，改用单文件 Contents API 重试上传。
3. 首次写 workflow 文件被 404 拒绝，确认需 `workflow` scope。
4. 无 Key 时 exit 0 的设计保证主流程不受影响。

## [S1] Problem
Dashboard 已上线并按 30 分钟节奏更新，但用户必须主动打开网址才能看到操盘建议和持仓信号。盘中触发止损/减仓时无法及时知晓，收盘后也没有可回看的汇总推送。需要把关键信息主动推到微信。

## [S2] Design
### 通道
- **Server酱 Turbo**（`sctapi.ftqq.com/<SENDKEY>.send`）
- SendKey 存放在 GitHub Actions Secret `SERVERCHAN_KEY`
- 本地 `notify.py` 也支持环境变量 `SERVERCHAN_KEY`，无 Key 时跳过并打印提示，不报错

### 推送时机
| 触发 | 时机 | 内容 |
|------|------|------|
| 盘中关键警报 | 每次 Actions 更新后 | 仅当出现「止损」信号或新增「减仓」信号时推送；同一天同一信号不重复推 |
| 盘后复盘 | 北京 17:00（cron `0 9 * * 1-5`） | 市场温度/状态 + 今日剧本 + 持仓信号一览 + 板块资金流 Top |

### 数据流
```
trader_engine.py → trader_signal.json
        ↓
notify.py --mode alert   # 增量警报（对比 notify_state.json）
        ↓
notify.py --mode review  # 收盘全量复盘
        ↓
Server酱 API → 微信服务号
```

### 去重状态
`notify_state.json`（提交到仓库）记录已推送的信号指纹：
```json
{"date": "2026-09-29", "pushed": ["sh688106:stop", "sz002594:reduce"]}
```
- 同一交易日同一标的+信号类型只推一次
- 跨日自动清空

### 消息格式
```
【A股操盘台】止损警报
信号：曙光数创 止损
原因：跌破止损位 83.18×0.93
现价：70.12  浮亏：-15.8%
建议仓位：0%
市场：防守（温度 30）
```

### Actions 集成
在 `update.yml` 的数据抓取之后、提交之前插入：
```yaml
- name: Server酱推送
  env:
    SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
  run: python notify.py --mode alert --also-review
```
`--also-review` 在北京时间 15:00 后的跑次自动改为 review 模式。

### 错误行为
- 无 `SERVERCHAN_KEY`：跳过推送，exit 0（不影响主流程）
- 网络失败：重试 2 次，仍失败则 warning 后继续
- `trader_signal.json` 缺失：跳过

## [S3] Out of Scope
- 不做邮件/Telegram/Bark 多通道
- 不做盘中实时 tick 级推送（仅 Actions 跑次粒度，开盘期间约每 30 分钟）
- 不在前端浏览器内推送（Server酱是服务端 → 微信）
- 不做推送内容的个性化配置 UI

## Tasks
- [ ] T1: 实现 notify.py（Server酱发送、alert/review 两种模式、去重状态） — acceptance: 无 Key 时跳过 exit 0；有 Key 时 curl 可达；同日同信号不重复 (covers: S2)
- [ ] T2: update.yml 集成推送步骤 + notify_state.json 入仓 — acceptance: 工作流跑次包含「Server酱推送」步骤且不因无 Key 失败 (covers: S2; depends: T1)
- [ ] T3: 本地端到端演练（模拟 alert/review 输出）并验证格式 — acceptance: 两种模式的文案符合 [S2] 格式，去重逻辑生效 (covers: S2; depends: T1)
