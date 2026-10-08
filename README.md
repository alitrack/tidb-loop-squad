# TiDB 值夜 Agent 小队（Loop Night-Shift Squad）

> 1024 TiDB AIGC 黑客松参赛作品 — 用平凯 Loop 组建四人 DBA 值班小队，在平凯云 Serverless TiDB 上真实闭环一次 P1 慢查询事故。

## 这是什么

一支跑在平凯 Loop 上的四人 DBA 值班小队：

| Agent | 职责 |
|---|---|
| **squad-lead** | 接管告警、立规矩（未经人类授权不执行 DDL）、拆单派活、验收关闭 |
| **inspector** | 连库取证：锁定目标 SQL、扫描量、执行计划、复测 |
| **diagnostician** | 机制诊断：EXPLAIN 闭合因果链、给出修复方案与回滚顺序 |
| **reporter** | 事故报告生成：两阶段报告 + 证据索引 + 未验证范围声明 |

运行时为本地 Codex（gpt-6-astra），0 Loop 积分消耗。数据库为平凯云 Serverless TiDB（`orders_big` 表 262,144 行）。

## 事故处置结果（全部有证据链）

- 客户端耗时：**197.4ms → 15.0ms（13 倍）**
- 服务端耗时：183ms → 2.388ms（STATEMENTS_SUMMARY_HISTORY 实测）
- 扫描量：**262,144 keys → 129 keys**
- 等价性：同快照新旧 SQL 结果完全一致（COUNT=129 / SUM=12771.00）
- 人类参与：**4 条消息**（1 告警 + 3 授权）
- 修复方式：虚拟生成列 + 覆盖索引，**原 SQL 如实报告未达标，不用改写 SQL 冒称原查询已加速**

## 目录

- [`replay/act1_timeline.html`](replay/act1_timeline.html) — 协作时间线回放页（单文件，零依赖，浏览器直接打开）
- [`video/act1_3min.mp4`](video/act1_3min.mp4) — 5:30 高能版实录
- [`evidence-official/`](evidence-official/) — 官方录制轮完整证据包：
  - `evidence/` — 取证 JSON 全套（EXPLAIN / 统计 / 修复预检 / 应用 / 复测）+ 每份 JSON 对应的原始 SQL
  - `reports/` — reporter agent 生成的两阶段事故报告（stage / post-change，md + pdf）
  - `inspect_*.json` — 开局巡检快照
  - `channel_transcript_full.txt` — 频道完整协作记录
- [`roles.md`](roles.md) — 四个 agent 的角色卡
- [`dba_inspect.py`](dba_inspect.py) — inspector 的巡检脚本（凭据已脱敏）
- [`submission_draft.md`](submission_draft.md) — 投稿帖草稿

## 复现路径

1. 平凯云开 Serverless TiDB 集群，建 `orders_big`（262,144 行，仅 PRIMARY 索引）
2. Loop 建四个 agent（角色卡见 `roles.md`），运行时选本地 Codex/OpenCode 等
3. 给 inspector 部署 `dba_inspect.py` + DSN 环境变量
4. 频道发 P1 告警 → 小队接管 → 人类只在授权点出消息

## 凭据说明

所有凭据在入库时已脱敏（DSN 密码段截断为 `***`，集群 ID 替换为 `<CLUSTER_ID>`）。赛后集群凭据已轮换。
