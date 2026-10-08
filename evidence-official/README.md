# 幕1 正式录制存档 — 2026-10-02

## 现场信息
- 时间：2026-10-02 08:55 告警 → 09:34 P1 关闭，全程 ~39 分钟
- 运行时：四 agent 全部 **Codex 本地运行时**（0 Loop credit）
- 事件编号：#t2（主任务），子任务 #t3 取证 / #t4 诊断 / #t5 报告 / #t6 变更 / #t7 切换验收
- 集群：平凯云 Serverless，squad_lab.orders_big 262,144 行

## 剧情时间线（频道实录见 channel_transcript_full.txt，464 行）
| 时刻 | 事件 |
|---|---|
| 08:55 | 人类发 P1 告警（风暴压载中：985 次 ×183ms） |
| 08:56 | squad-lead 接管，拆 #t3/#t4 派单 |
| 08:58 | inspector 首批证据：digest 8c720334…，AVG 183ms，扫描 262,144 keys/次 |
| 08:59-09:00 | diagnostician 结构核验+机制闭合：LIKE '%-042' 前置通配+无二级索引=全表扫；EXPLAIN estRows=262144 |
| 09:04 | diagnostician 交付方案：虚拟生成列 note_suffix4=RIGHT(note,4) + 覆盖索引 (status,note_suffix4,amount) |
| 09:06 | **人类授权①**：批准修复方案（先隔离验证再生产） |
| 09:10 | **人类授权②**：演示环境，隔离验证与生产合并执行 |
| 09:19 | DDL 131/132 synced（add column + add index）；基线复测 197.354ms |
| 09:22 | 复测结果：改写 SQL 19.429ms（9.67×）；原样 LIKE 仍 187.787ms（诚实报告未混报） |
| 09:25 | **人类授权③**：批准应用侧查询改写切换 |
| 09:32 | inspector #t7 切换+新复测：15.017ms 均值，服务端 2.388ms，IndexRangeScan actRows=129 |
| 09:34 | squad-lead 宣告 P1 关闭 |

## 核心数字（对外宣传用，全部有证据）
- 客户端 wall time：**197.4ms → 15.0ms（13×）**；服务端：183ms → **2.388ms**
- 扫描量：**262,144 keys → 129 keys**
- 等价性：新旧 SQL 同快照 COUNT=129、SUM=12771.00 完全一致
- 人类全程仅 **4 条消息**（告警/授权修复/合并执行/批准切换）
- 新 digest：b5f88a17…，plan_digest：502a48d1…（HISTORY 服务端证据）

## 叙事亮点（剪辑线索）
1. **真实失败与诚实归因**：先加索引不解决原 LIKE（选择度问题+前置通配），小队如实报"原 SQL 未达标"，不拿改写 SQL 的数字冒称原 SQL 加速——squad-lead 原话"不能用改写 SQL 的数据冒称原 SQL 已加速"值得特写
2. **流程严谨**：队长坚持"先隔离验证再生产"，人类拍板合并执行——体现人机协作决策链
3. **证据链完整**：每个结论带表名+指标值+附件，reporter 出 6 页阶段报告 + 5 页变更后报告（PDF）
4. **插播事故**：09:11 Codex 额度耗尽导致 diagnostician 静默 ~8 分钟，人类催办+额度重置后恢复（剪辑时掐掉 09:12-09:19 空档）

## 文件清单
- `channel_transcript_full.txt` — 频道全量实录（464 行）
- `p1-orders-big-stage-report-20261002.pdf` — reporter 阶段报告（6 页，截止 09:06:49）
- `p1-orders-big-post-change-report-20261002.pdf` — reporter 变更后报告（5 页，截止 09:23:33）
- `reports/` — reporter 工作目录（含 md 源）
- `evidence/` — diagnostician 全部证据 JSON + 修复脚本 + 诊断 md + inspector demo SQL
  - `orders_big_repair_evidence_20261002.json` — 修复+复测核心证据
  - `orders_big_diagnosis_20261002.md` — 诊断报告（15 项检查）
  - `repair_apply.py / repair_verify.py / repair_preflight.py` — agent 自写修复脚本
- `demo_release_20261002_093203.json` — #t7 切换验收证据
- `inspect_*.json` — inspector 巡检快照

## 后续待办
- [ ] 幕2（悲观锁之夜）/ 幕3（统计过期）排练与录制
- [ ] 回放 Web 页（协作时间线）
- [ ] 剪映剪辑（≤3min ≤100MB），掐掉额度耗尽空档
- [ ] D11（10/14 前）发帖 + 社媒拉票
