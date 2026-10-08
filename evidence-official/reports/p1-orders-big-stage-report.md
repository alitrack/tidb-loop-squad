# P1 事故阶段报告
## 1. 概览与时间线
2026-10-02 | squad_lab.orders_big | #t2 / #t3 / #t4 / #t5

**阶段：只读取证完成；09:06:49 已获“先隔离验证、再生产”修复授权，执行结果待证据；P1 未关闭。**

报告事件截止 09:06:49；实测取证截止 09:00:05。授权不等于执行完成；截至报告截点尚未收到变更及复测证据，不宣布业务恢复。

用户于 08:55:55 反馈“订单查询大面积超时，orders_big 相关查询延迟飙高”。这是业务报告的症状，受影响用户数、请求数、接口范围、开始时间及超时率尚未量化。[E0]

已确认目标 SQL 的全表扫描机制：当前仅有主键，目标尾缀过滤没有匹配的过滤访问路径；普通 EXPLAIN 与已有执行样本相互印证。尚未确认该扫描足以解释应用大面积超时。[E2-E4]

本报告仅复核附件并汇总，未连接数据库。inspector 的 6 项补充查询和 10 项巡检合计 16 项均成功；diagnostician 的 15 项诊断中 14 项成功，辅助 SHOW STATS_COL_USAGE 返回 1064，已保留失败，不作为零值。[E1、E2]

| 时间（10 月 2 日，UTC+8） | 事件与状态 | 证据 |
|---|---|---|
| 08:55:55 / 08:56:13 | 用户告警 / 队长接管；只读取证 | E0 |
| 08:57:15 | 完整巡检采集 | E1 |
| 08:57:50 | 目标近窗 SQL 取证，会话时区核验 | E1 |
| 08:57:52 | 表结构确认仅 PRIMARY(id) | E2 |
| 08:59:23 / 08:59:44 | 事务时钟复核 / 目标样本补查 | E1 |
| 08:59:55 / 09:00:05 | 读取历史 PLAN / 普通 EXPLAIN 验证 | E3、E4 |
| 09:03:28 | 队长验收 #t3；仅取证通过，P1 未关闭 | E0 |
| 09:04:18 / 09:05:29 | #t4 提交方案 / 队长审阅通过；请求隔离验证审批 | E5、E0 |
| 09:06:49 | 用户授权先隔离验证再生产，要求同一业务 SQL 的 25 ms 级对比 | E0 |

取证人员报告本轮未执行 DDL、KILL、ANALYZE、配置修改或业务聚合查询。历史 PLAN 为已有样本，未执行 EXPLAIN ANALYZE。[E1、E5]

<!-- pagebreak -->
## 2. 关键指标与采样口径
来源：INFORMATION_SCHEMA.STATEMENTS_SUMMARY_HISTORY，08:57:50 查询。条件为窗口结束时间不早于查询时 NOW()-30 分钟、文本含 orders_big，且 schema 或库限定名匹配 squad_lab；按窗口记录 SUM_LATENCY 降序 LIMIT 10。实际 5 条窗口记录、3 个 digest，覆盖 08:51:38 至 08:57:43，并非 10 个独立 SQL。[E1]

下表仅汇总目标 digest 的三窗，耗时单位 ms；原始 latency 为 ns，除以 1,000,000 换算。

| 目标窗口 | 次数 | 总耗时 | 平均 | 最大 |
|---|---:|---:|---:|---:|
| 08:54:40-08:55:41 | 283 | 51,809.569 | 183.073 | 201.298 |
| 08:55:41-08:56:42 | 500 | 91,768.736 | 183.537 | 203.239 |
| 08:56:42-08:57:43 | 202 | 37,100.217 | 183.664 | 199.176 |
| 原始值合并 | 985 | 180,678.523 | 183.430 | 203.239 |

总原始值 180,678,522,939 ns；加权平均 = 总耗时 / 985。先相加已舍入行值会少 0.001 ms，因此采用原始值汇总。三窗各次平均 processed keys=262,144、total keys=262,146、返回行数=1，错误/警告均为 0；key 数不是返回行数，也不是应用超时数。[E1]

| 08:57:15 巡检项（INFORMATION_SCHEMA 下） | 实测与边界 |
|---|---|
| DATA_LOCK_WAITS / DEADLOCKS | 0 / 0，仅当时可见记录 |
| CLUSTER_PROCESSLIST | 非 Sleep 且 TIME>5 秒为 0 条，非完整长事务检查 |
| MEMORY_USAGE | 当前 75,554,816 / 限额 1,717,986,918 bytes；4.4%；峰值 106,037,248 bytes |
| DDL_JOBS | 最近 10 条均 synced；最新 JOB_ID=130，不能代替当前索引检查 |
| STATEMENTS_SUMMARY_HISTORY | 默认全可见窗 07:16:42-08:57:15：3,957 次，错误/警告为 0，无近窗过滤 |

其他两条 Top10 记录为 COUNT(?) FROM orders_big：1 次、99.737 ms；SHOW INDEX：1 次、3.194 ms。08:59:23 的覆盖查询已见 7 条/5 个 digest，窗口至 08:58:43，是另一次采样，不混入本次 Top10。[E1]

<!-- pagebreak -->
## 3. 异常、已确认机制与因果边界
目标样本 SQL：[E3]
```sql
SELECT COUNT(*), SUM(amount)
FROM squad_lab.orders_big
WHERE note LIKE '%-042' AND status='new';
```

| 验证点 | 实测 | 结论层级 |
|---|---|---|
| SHOW CREATE TABLE / SHOW INDEX | 仅 PRIMARY(id)，二级索引为 0 | 当前结构事实 [E2] |
| SHOW STATS_META / HISTOGRAMS | Row_count=262,144，Modify_count=0；仅 id 直方图 | Healthy=100 不代表列统计齐全 [E2] |
| 普通 EXPLAIN | TableFullScan estRows=262,144；status/note unInitialized | 全扫计划及列统计缺失 [E4] |
| 历史 PLAN | 实扫 262,144 keys，过滤 129 行，聚合 1 行 | 扫描放大机制确认 [E3] |
| 历史 PLAN 时间 | root 189.1 ms；TiKV process 187.3 ms，wait 28.5 µs | 单样本以处理耗时为主，不外推全局 [E3] |
| 仅改 RIGHT(note,4) | 仍 TableFullScan，估算 262,144 | 仅改函数写法不是已验证修复 [E4] |

**机制结论：**当前无过滤索引，尾缀条件在全扫后过滤；补统计不会自行创建索引访问路径。旧 add index JOB_ID=127 在后续 drop=128 / create=130 之前，不代表当前有索引，也不能证明 10 月 2 日发生过结构变更。[E2、E5]

**未闭合的应用超时因果：**缺应用 deadline、失败请求时间/trace、连接池等待、并发、重试和端到端延迟。约 0.19 秒 DB 样本不足以单独证明大面积超时的充分原因；数据库错误为零也不能否定应用超时。需由应用侧提供同时间同 SQL 的请求链路并对齐。[E0、E5]

**时区与事务限制：**本轮 NOW 与 UTC_TIMESTAMP 相差 8 小时，会话 +08:00、系统 UTC，已核验；不沿用 9 月 30 日的“会话时区未核验”。但 CLUSTER_TIDB_TRX 的 START_TIME 与会话时钟存在口径差。无时长过滤、LIMIT 100 的补查返回 1 条 Idle，和 NOW 相减为 28,799 秒、和 UTC 相减为 0 秒；不采信前者为长事务时长，不宣称全局长事务为零。[E1]

<!-- pagebreak -->
## 4. 已授权流程与待执行验证
本节转述已审阅的 #t4 方案。其在 09:04 时为待审批候选；09:06:49 用户授权该修复流程。这里仍是方案，不是执行记录。[E0、E5]

**最新授权：**按诊断员方案创建虚拟列及联合覆盖索引，先隔离验证再上生产，保留风险与回滚预案，完成后复测同一业务 SQL，回报 25 ms 级对比。隔离验证不能跳过；具体环境、执行边界及切换范围由队长落实，不沿用 9 月 30 日旧授权。[E0]

**前置门槛：**业务确认固定 4 字符尾缀语义。隔离副本以同一快照比较旧/新 COUNT、SUM 完全一致，覆盖 NULL、短字符串、大小写、Unicode、尾随空格、空结果和 SUM 为 NULL；实际参数不得被擅自简化为固定尾缀。不能把尾缀 LIKE 改成前缀 LIKE。

**建议方向：**虚拟生成尾缀列 + 联合覆盖索引 + 显式列查询。不依赖自动表达式替换，不开启 unsafe substitute。
```sql
-- 已授权流程中的方案 SQL；不是已执行记录
ALTER TABLE squad_lab.orders_big
  ADD COLUMN note_suffix4 VARCHAR(4)
  CHARACTER SET utf8mb4 COLLATE utf8mb4_bin
  GENERATED ALWAYS AS (RIGHT(note,4)) VIRTUAL;
CREATE INDEX idx_orders_status_suffix4_amount
  ON squad_lab.orders_big(status,note_suffix4,amount);
ANALYZE TABLE squad_lab.orders_big
  COLUMNS status,note,note_suffix4,amount;
EXPLAIN FORMAT='brief'
SELECT COUNT(*), SUM(amount)
FROM squad_lab.orders_big
WHERE status='new' AND note_suffix4='-042';
```

期望验证等值 IndexRangeScan；覆盖成立时可能采用 IndexReader。此为候选预期，不能保证精确扫描 129 keys 或特定耗时，须以实际计划和受控执行验证。[E5]

**执行前需落实：**语义与等价性负责人、隔离验证许可、生产 DDL/统计采集权限、资源余量和低峰窗口、灰度范围、回退责任人、观测阈值及业务 SLO。生产步骤必须以隔离验证通过为前提；新增或超出方案的操作不得自动扩展授权。

**风险：**索引回填及 ANALYZE 消耗 CPU/IO；索引增加磁盘和写放大；生成列语义或应用改写不一致会影响结果。不能改查询或尾缀不固定时，#t4 提出另评估 (status,note,amount) 覆盖索引，但它仍需残余尾缀过滤，状态选择性与宽列成本尚未量化，不建议直接生产建设。[E5]

<!-- pagebreak -->
## 5. 回滚、复测与恢复门槛
以下为 #t4 提出的待确认验收标准，不是已达成指标。[E5]

用户另要求 25 ms 级对比数据：应报告相同业务语义下的实际旧/新 SQL、参数、数据量、并发、缓存条件及计时口径。25 ms 是待复测目标，不是已有结果；不可把单次历史样本与聚合均值直接混作同口径前后对照。[E0]

### 回滚顺序与触发判断
等价性失败、计划未按目标访问索引，或写延迟/资源出现不可接受回归时，不扩大灰度并按审批预案回退；“不可接受”的具体阈值须先明确。

1. 先撤回应用新查询/发布，确认没有调用方引用 note_suffix4。
2. 再经批准删除本次新增索引和列，不得反序。
```sql
DROP INDEX idx_orders_status_suffix4_amount
  ON squad_lab.orders_big;
ALTER TABLE squad_lab.orders_big DROP COLUMN note_suffix4;
```
3. 回退旧查询会恢复原全扫风险；应用限流/降级需另行审批。元数据回退不等于性能恢复。
4. ANALYZE 不承诺一键逆转；本次 Serverless 统计导入恢复能力未验证，不能把 LOAD STATS 当成可用回滚。

### 分层验收，缺一不宣布业务恢复
| 层次 | 待验证门槛 |
|---|---|
| 语义与计划 | 同快照旧新 COUNT/SUM 一致；普通 EXPLAIN 无目标 TableFullScan，实际使用新索引等值访问 |
| 数据库受控负载 | 同参数/数据量/并发；平均 processed keys 较 262,144 降低至少 99%（<=2,621）；平均 DB 耗时 <50 ms；逐请求 p95 <100 ms；错误不增加 |
| 稳定观察 | 至少连续两个完整 5 分钟观测段；覆盖峰值并发与代表参数，写延迟和资源无不可接受回归 |
| 应用恢复 | 端到端 p95/p99、超时率满足已确认 SLO；连接池无异常排队；队长核对请求链路后决定是否关闭 P1 |

上述数值门槛仍待业务 SLO 确认。statement summary 的平均/最大值不能推导 p95；复测按本次授权及隔离优先顺序执行，不自行扩展为无界 EXPLAIN ANALYZE。

### 后续防复发建议
表重建/迁移后自动检查必需索引；监测目标 digest 的 processed keys、plan_digest、错误和耗时；检查谓词列统计，不只看 Healthy；补充尾缀检索语义与迁移回归用例。本次未建立可比长期基线，不输出趋势改善结论。[E5]

<!-- pagebreak -->
## 6. 巡检明细与证据索引
证据以 10 月 2 日本轮附件为准，未用 9 月 30 日巡检快照替代本次实测。所有实际取证 SQL、成功/失败标志及完整返回值均保留在源 JSON；本报告 SQL 中的变更段仅为候选，不是已执行操作。

| 编号 | 来源及可定位字段 |
|---|---|
| E0 | 本频道用户告警 08:55:55（msg 44c261a1）；队长接管 08:56:13（cbf548db）；#t3 验收 09:03:28（16d39955）；#t4 审阅 09:05:29（96674b5d）；用户授权 09:06:49（b06a3638） |
| E1 | inspect_20261002_085750_orders_big_evidence.json；附件 att_kdspylj3u9025y；checks 按 name 定位 orders_big_top10、clock、transaction_clock_check、target_sample_and_plan；full_inspection / full_inspection_queries |
| E2 | orders_big_diagnostic_evidence_20261002.json；附件 att_fymzwts8tkb1n7；metadata_20261002.json 的 queries/results；stats_20261002.json 含辅助探测失败 |
| E3 | 同 E2 合集的 target_sample_20261002.json / results.target_sample.rows[0]：QUERY_SAMPLE_TEXT、PLAN_DIGEST、PLAN |
| E4 | 同 E2 合集的 explain_20261002.json / results.explain_exact、explain_suffix_rewrite_no_index |
| E5 | orders_big_diagnosis_20261002.md；附件 att_sbtor0y7v0el5m；修复候选、风险/回滚/复测；诊断员 09:04:18 交付 |

目标 digest：
`8c720334eba435f01617c9475a9118fd3af0c7ed1ef96c27b7757e0ea5b9cba8`

plan_digest：
`f647fd78aa620ee4d77394eacd7227b6c41fd47a5cd433720d083f29c2939dae`

诊断来源说明：#t4 引用了 TiDB 官方生成列、执行计划、统计与索引策略文档。报告员转述其已交付方案，不额外扩展未经验证的产品能力。
- https://docs.pingcap.com/tidb/stable/generated-columns/
- https://docs.pingcap.com/tidb/stable/explain-overview/
- https://docs.pingcap.com/tidb/stable/statistics/
- https://docs.pingcap.com/tidb/stable/sql-tuning-best-practice/

**报告边界：取证已完成，机制已确认，应用因果未闭合；修复流程已授权，尚无执行/复测证据，业务恢复未验收。**
