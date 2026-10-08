# P1 变更后复测报告
## 1. 概览与授权时间线
2026-10-02 | squad_lab.orders_big | #t5 / #t6 | 事件截止 09:23:33

**原样 SQL 未达 25 ms；显式尾缀列等价改写在本次小样本测试达标；应用未切换，P1 未关闭。**

09:10:52 用户确认当前为演示环境，授权隔离验证与生产步骤合并执行。该授权替代此前“先独立隔离”的流程；不是补做了独立环境验证。队长随后指定 diagnostician 为唯一数据库变更执行者，限制为已批准列/索引/统计采集及复测，不部署应用。[R0]

新增虚拟列 note_suffix4 和覆盖索引已核验，DDL JOB_ID 131/132 均 synced。变更后原 LIKE 的普通 EXPLAIN 仍全表扫描，5 次客户端 wall time 平均 187.787 ms；显式尾缀列查询为 IndexReader / IndexRangeScan，均值 19.429 ms。不能用后者数据冒称“原 SQL 已加速至 25 ms”。[R2、R3]

本版补充真实变更和复测，不覆盖截至 09:06:49 的阶段版。报告员仅复核附件并重新计算指标，未执行数据库操作。[R6]

| 时间（UTC+8） | 事件 | 证据 |
|---|---|---|
| 08:55:55 | 用户报告订单查询大面积超时；实际影响面未量化 | R6 |
| 09:06:49 | 授权先隔离验证再生产；要求 25 ms 级对比 | R6 |
| 09:10:52 / 09:11:30 | 演示环境合并授权 / 队长限定执行范围 | R0 |
| 09:12:08-09:12:10 | 前检、12 个常量边界样本、原 SQL 5 次基线 | R1 |
| 09:18:27 | 用户要求继续 #t6，创建列/索引并复测 | R0 |
| 09:19:08-09:19:32 | 重新检查结构，创建列/索引及 ANALYZE | R2 |
| 09:19:47-09:19:48 | 同连接同快照，原样/改写交替各 5 次 | R3 |
| 09:21:14 | 末检统计和两组普通 EXPLAIN | R4 |
| 09:23:33 | 队长核验变更与复测；应用改写仍需批准及入口 | R0 |

**当前影响边界：**固定参数的等价结果和数据库访问路径已取得证据；应用 deadline、失败 trace、连接池/重试、峰值负载及端到端超时率仍缺，不据此宣布业务恢复。[R0、R3、R6]

<!-- pagebreak -->
## 2. 关键指标：严格分开三组样本
单位均为客户端 wall time，ms，包含往返和取回结果；不是纯服务端耗时。[R1、R3]

| 查询组 | 5 次均值 | 中位数 | 最小值 | 最大值 |
|---|---:|---:|---:|---:|
| 变更前原 LIKE | 197.354 | 196.900 | 194.321 | 200.764 |
| 变更后原 LIKE | 187.787 | 182.458 | 181.404 | 210.613 |
| 变更后显式尾缀列 | 19.429 | 19.353 | 18.800 | 20.108 |

| 轮次 | 变更前原 LIKE | 变更后原 LIKE | 变更后显式尾缀列 |
|---|---:|---:|---:|
| 1 | 196.666 | 210.613 | 18.843 |
| 2 | 198.117 | 181.404 | 18.800 |
| 3 | 196.900 | 182.914 | 20.039 |
| 4 | 200.764 | 182.458 | 20.108 |
| 5 | 194.321 | 181.544 | 19.353 |

以上从每次未舍入 wall_ms 重算，最后显示三位小数。同期变更后原样/改写均值之比为 9.665 倍（约 9.67）；该倍数仅适用于本次串行样本，不是应用吞吐或 SLO 改善倍数。

**可比范围：**变更后两组在连接 98566154、REPEATABLE-READ、START TRANSACTION WITH CONSISTENT SNAPSHOT 下交替串行运行。前测在 09:12 的独立连接和较早快照进行，不能声称三组全在同一连接/快照。没有给出缓存命中、预热控制或峰值并发证据。[R1、R3]

**结果一致性：**15 次聚合均返回 COUNT=129、SUM=12771.00；变更后 10 次来自同快照。12 个常量样本的旧/新谓词均一致，覆盖 NULL、空串、短串、Unicode、尾随空格等；不代表任意长度或其他通配符参数都已通过语义验证。[R1、R3]

**25 ms 结论：**改写的 5 次实测均低于 25 ms；原样 SQL 的变更后 5 次均超过 25 ms。只证明受控串行小样本达到该目标，不能证明逐请求 p95、峰值负载或持续稳定达标。

历史服务端三窗的 985 次、均值 183.430 ms，以及历史 PLAN 单次 189.1 ms 仍保留在阶段版，但不与本次客户端均值混算。[R6]

<!-- pagebreak -->
## 3. 实际变更与扫描机制
以下是附件记录的实际执行 SQL，不再是仅供审批的候选：[R2]
```sql
ALTER TABLE squad_lab.orders_big
 ADD COLUMN note_suffix4 VARCHAR(4)
 CHARACTER SET utf8mb4 COLLATE utf8mb4_bin
 GENERATED ALWAYS AS (RIGHT(note,4)) VIRTUAL;
CREATE INDEX idx_orders_status_suffix4_amount
 ON squad_lab.orders_big(status,note_suffix4,amount);
ANALYZE TABLE squad_lab.orders_big
 COLUMNS status,note,note_suffix4,amount;
```

| 动作 | 实际状态 / 耗时 | 证据 |
|---|---|---|
| 创建虚拟列 | JOB_ID=131，synced；客户端 280.101 ms | R2 |
| 创建覆盖索引 | JOB_ID=132，synced；客户端 21.779 秒 | R2 |
| ANALYZE | ok=true；客户端 1.922 秒；有警告及提示 | R2 |
| 结构复核 | 变更前仅 PRIMARY；变更后虚拟列及三列索引可见 | R2 |

INFORMATION_SCHEMA.DDL_JOBS 记录：131 开始 09:19:08.273、结束 09:19:08.523；132 开始 09:19:08.573、结束 09:19:30.273。这是表内时间，与客户端 wall time 分开，不混用。[R2、R3]

```sql
-- 原样：仍 TableFullScan，估算扫描 262144
SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big
WHERE note LIKE '%-042' AND status='new';
-- 等价改写：IndexReader -> 新索引 IndexRangeScan
SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big
WHERE note_suffix4='-042' AND status='new';
```

**机制更新：**此前“当前只有主键”仅对变更前成立。现有过滤索引，但本次原 LIKE 计划没有使用该访问路径；显式引用尾缀列才得到索引范围计划。09:19 和 09:21 两次普通 EXPLAIN 均支持这一结论。[R2-R4]

新计划 IndexRangeScan 的 estRows=1 是估算，不能写成“实扫 1 key”。COUNT=129 是聚合计数结果，也不能直接冒充新方案实际 processed keys；本附件未提供新计划实际扫描 key 数，不宣布“扫描下降 99%”已验收。[R3、R4]

<!-- pagebreak -->
## 4. 异常保留、回滚与恢复边界
### 统计警告与采样限制
ANALYZE 成功不等于无警告或统计完整：[R2、R4]
- Warning 1105：ANALYZE 列清单未列 id，但该列统计用于索引/主键/扩展统计计算。
- Note 1105：自动调整采样率至 0.419617，原文依据 min(1,110000/262144)。
- 09:21 末检 SHOW STATS_HISTOGRAMS 中联合索引 allLoaded；note_suffix4 单列仍为 Distinct_count=0、Null_count=262144，计划估算 1 与实际聚合计数 129 不符。不能解释为真实列值全 NULL，也不宣称估计准确；诊断员未追加试探性变更。

内存来源 INFORMATION_SCHEMA.MEMORY_USAGE：变更前 74,997,760 bytes（约 4.4%）；ANALYZE 后 236,937,216（约 13.8%）；复测末检 112,197,632（约 6.5%），限额均为 1,717,986,918 bytes。INFORMATION_SCHEMA.DATA_LOCK_WAITS 在前检及复测末检均为 0。仅为离散采样，不是峰值或全过程无阻塞证明。[R2、R3]

### 应用切换与验收待办
当前未发布应用改写；继续执行原 LIKE 的业务不能据本报告宣称已获得 19.429 ms 路径。需批准固定尾缀查询切换并提供代码/发布入口，落实灰度和回退负责人。[R0]

| 已验证 | 尚未验证 / 下一关 |
|---|---|
| DDL synced；列/索引存在 | 应用真实调用是否切换及其端到端收益 |
| 当前参数同快照结果一致 | 代表参数、业务完整语义和持续负载回归 |
| 改写小样本均值 19.429 ms | 峰值并发、两个完整 5 分钟段、逐请求 p95/p99 |
| 普通 EXPLAIN 使用新索引 | 实际 processed keys 下降门槛、资源/写延迟回归 |

阶段版的 DB 均值 <50 ms、p95 <100 ms、processed keys 下降至少 99% 等为待确认门槛。不能用客户端 5 次样本替代全部验收。应用超时率、deadline、连接池、重试与 trace 仍需对齐；P1 不关闭。[R0、R6]

### 回滚预案（未执行）
先撤回所有引用 note_suffix4 的应用查询，确认无依赖后再经批准 DROP INDEX，最后 DROP COLUMN。原 SQL 全扫风险会重新暴露；统计采集不可承诺一键逆转。本附件中的 ROLLBACK 是结束只读一致性快照，不是撤销 DDL。[R1-R3、R6]
```sql
DROP INDEX idx_orders_status_suffix4_amount
 ON squad_lab.orders_big;
ALTER TABLE squad_lab.orders_big DROP COLUMN note_suffix4;
```

<!-- pagebreak -->
## 5. 巡检明细与证据索引
新增主证据附件：orders_big_repair_evidence_20261002.json，ID att_xc9sk0bw31wi0d。其包含四个具名 JSON；checks 按 name 定位，保留 sql、at、ok、wall_ms 及完整 rows。末检使用 queries/results。[R1-R4]

| 编号 | 可回溯位置 |
|---|---|
| R0 | 频道授权 09:10:52（msg 114b15ac）；派单 09:11:30（34f61e6f）；继续执行 09:18:27（1d21dc9a）；队长验收 09:23:33（bf096437） |
| R1 | repair_preflight_20261002.json：boundary_semantics、explain_before、snapshot_begin/end、baseline_original_1..5；started_at / ended_at |
| R2 | repair_apply_20261002.json：add_column、create_index、analyze、analyze_warnings、ddl_state、structure_before/after、indexes_after、memory_before/after |
| R3 | repair_verify_20261002.json：clock_connection、snapshot_begin/end、original_1..5、rewrite_1..5、explain_original/rewrite、ddl_final、locks_after、memory_after；两组 timing 与 same_snapshot_equal |
| R4 | repair_final_metadata_20261002.json：results.histograms、explain_original、explain_rewrite；collection_start/end |
| R5 | 诊断员 #t6 回报 09:22:13（msg 6c56fe74），声明未部署应用、未执行回滚、未追加试探性变更 |
| R6 | 阶段版 Markdown：att_y6qb5b3farx03b；阶段版 PDF：att_si91p992kbwhmr；保留 E0-E5 索引、历史原始附件、此前授权与时区限制 |

### 复核方法与未掩盖事项
- 报告员逐项读取变更附件，按每次未舍入 wall_ms 重算均值/中位数/范围和同期比值；检查 15 次聚合返回值及 12 个常量样本，核验 DDL 状态与前后结构。
- 不用任务 done、脚本 completed 或消息回报单独替代变更证据；数据库侧以实际结构和 DDL_JOBS、查询结果交叉核对。
- 先前 inspector 16 项成功与 diagnostician 15 项中 14 成功、1 项 SHOW STATS_COL_USAGE 的 1064 失败保留在阶段版；本次 ANALYZE 的 1105 警告是另一事项，不抹平、不混为同一错误。
- 本次会话时区 +08:00 已核验；统计 SHOW 时间保留原值，不与 DDL 时钟直接相减。此前长事务 START_TIME 的时钟口径限制未被此次修复消除，不推断全局长事务为零。
- 此次数据库 SQL 的实际执行来自 diagnostician；报告员没有重新取数、执行 DDL、改变应用或独立证明应用恢复。

**最终边界：数据库变更已核验；原样 SQL 未达 25 ms；等价改写仅在本次受控小样本达到目标；应用未切换，恢复未验收。**
