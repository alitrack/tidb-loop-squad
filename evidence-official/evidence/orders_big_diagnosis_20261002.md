# orders_big 诊断与待审批方案｜2026-10-02

## 结论边界
本轮仅执行元数据 SELECT、SHOW 和普通 EXPLAIN。未执行业务聚合、DDL、ANALYZE、KILL、配置修改或 EXPLAIN ANALYZE。
确认目标 SQL 的全表扫描机制；未确认它足以解释全部应用超时，未执行修复，未宣告恢复。

## 新证据与口径
本机采集 08:57:52–09:00:05（UTC+8）。数据库 NOW=08:57:52.360159、UTC_TIMESTAMP=00:57:52.360160，session.time_zone=+08:00，system_time_zone=UTC；版本 v8.5.3-serverless。统计 SHOW 内时间原样保留，未将其与 DDL 时间直接相减。

| 来源及附件 | 确认事实 |
|---|---|
| SHOW CREATE TABLE / SHOW INDEX；metadata_20261002.json | 当前 squad_lab.orders_big 仅 PRIMARY(id)，二级索引=0；note varchar(256)、status varchar(16)、amount decimal(10,2)，utf8mb4_bin |
| INFORMATION_SCHEMA.TABLES / SHOW STATS_META；同上 | 元数据 Row_count=262144，Modify_count=0；不是本轮 COUNT(*) |
| SHOW STATS_HEALTHY / SHOW STATS_HISTOGRAMS；同上 | Healthy=100；histograms 仅 id 一条 |
| INFORMATION_SCHEMA.DDL_JOBS；同上 | 该表可见 8 条记录均 synced；最近 JOB_ID=130 建表，128 删表发生在 127 add index 之后。旧索引不能当作当前索引，也不能证明 10 月 2 日发生变更 |
| STATEMENTS_SUMMARY_HISTORY；target_sample_20261002.json | 已知 digest 最新可见一条样本窗口 08:56:42–08:57:43；样本见下 |
| 普通 EXPLAIN；explain_20261002.json | TableFullScan estRows=262144；Selection estRows=209.72；stats:partial[status:unInitialized, note:unInitialized]；SHOW WARNINGS 返回0条 |
| HISTORY.PLAN；target_sample_20261002.json | 历史样本 TableFullScan actRows=262144、Selection actRows=129、聚合1行；proc_keys=262144、total_keys=262146、扫描key字节22347651；root=189.1ms、TiKV process=187.3ms、wait=28.5µs |
| SHOW VARIABLES / SHOW STATS_LOCKED；stats_20261002.json | analyze_version=2、analyze_column_options=PREDICATE、auto_analyze=ON、ratio=0.5、stats_load_sync_wait=500；该表 stats_locked 返回0条 |

**失败项**：辅助探测 SHOW STATS_COL_USAGE 返回 1064 语法错误；不是零条、不是权限拒绝；不用于结论。
所有实际 SQL、成功/失败标志及返回值在四份 JSON 的 queries/results 中。

目标 digest：8c720334eba435f01617c9475a9118fd3af0c7ed1ef96c27b7757e0ea5b9cba8
plan_digest：f647fd78aa620ee4d77394eacd7227b6c41fd47a5cd433720d083f29c2939dae

原样本及本轮验证：
```sql
EXPLAIN FORMAT='brief'
SELECT COUNT(*), SUM(amount)
FROM squad_lab.orders_big
WHERE note LIKE '%-042' AND status='new';

-- 反证“只改函数写法就能提速”，不实际执行业务查询
EXPLAIN FORMAT='brief'
SELECT COUNT(*), SUM(amount)
FROM squad_lab.orders_big
WHERE RIGHT(note,4)='-042' AND status='new';
```
两者均 TableFullScan，estRows=262144。历史 PLAN 是服务器已记录的执行证据，并非本轮运行 EXPLAIN ANALYZE。
官方定义普通 EXPLAIN 不执行目标查询、estRows 为估计量：[执行计划说明](https://docs.pingcap.com/tidb/stable/explain-overview/)。

## 假说与证实/证伪
1. **过滤访问路径缺失造成扫描放大——已证实机制。** 如果成立，应看到当前无过滤索引、目标计划全表扫描、实际处理key接近全表量。三项均符合：0个二级索引、扫描262144、过滤129。不能把聚合返回1行当作过滤选择性。
2. **谓词列统计未初始化——已证实；是全部慢查询的唯一根因——不成立为已证结论。** 如果存在，应看到 SHOW 缺列且 EXPLAIN 标记 unInitialized；两者均出现。当前甚至没有可选二级索引，单独 ANALYZE 不能创造范围访问路径。Healthy=100由修改数/总行数口径产生，不保证列统计完整。[统计信息](https://docs.pingcap.com/tidb/stable/statistics/)
3. **只把 LIKE 改为 RIGHT 就能解决——已证伪当前计划假说。** 两份普通 EXPLAIN 均全扫。
4. **该扫描是应用大面积超时的充分原因——未证实。** 若成立，应有同时间同SQL请求链路、超时阈值与端到端延迟/排队对应，并在受控变更后恢复。现只有数据库样本约189ms；缺应用deadline、连接池等待、重试/并发、超时错误和请求trace。数据库SUM_ERRORS=0不能否认应用超时。
5. **等待为本样本主耗时——不获支持，不做全局排除。** 历史 PLAN 的 process=187.3ms、wait=28.5µs；这是单样本，不等价于全局锁等待或资源健康。全局锁、内存、长事务证据由 inspector 独立交付。

inspector首批三个窗口（08:54:40–08:57:43）均为同一digest：283/500/202次、每次AVG_PROCESSED_KEYS=262144，SUM_ERRORS=0；合计985次，总180678.523ms、加权均183.430ms、最大203.239ms。已读回核对 inspector 附件 inspect_20261002_085750_orders_big_evidence.json 的 orders_big_top10，以原始纳秒相加得到总180678.522939ms（显示三位为180678.523ms），非本人重复全量取数。该Top10实际为5条窗口记录/3个digest；上述汇总仅取目标digest三条。

## 修复候选：仅供审批，全部未执行
优先确认业务是否长期使用“固定4字符尾缀 + status”等值条件。当前样本 %-042 是尾缀匹配；不能擅自改成前缀 LIKE '-042%'。
若该语义成立，建议**虚拟生成尾缀列 + 联合覆盖索引 + 显式列查询**。不依赖优化器自动表达式替换，不打开 unsafe substitute。TiDB支持虚拟生成列索引，且 ALTER TABLE 不能添加 stored 生成列：[生成列及限制](https://docs.pingcap.com/tidb/stable/generated-columns/)。

```sql
-- 仅审批后先在隔离副本/测试环境验证，再安排生产变更窗口
ALTER TABLE squad_lab.orders_big
  ADD COLUMN note_suffix4 VARCHAR(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin
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

预期而非实测：等值范围 IndexRangeScan，若覆盖成立为 IndexReader，扫描量接近匹配项而非262144；必须以实际计划验证，不能保证精确129 keys或耗时。
索引列中加入amount用于聚合覆盖；会增加写放大、磁盘与回填消耗。[联合/覆盖索引与成本](https://docs.pingcap.com/tidb/stable/sql-tuning-best-practice/)

语义门槛：在隔离副本以相同快照比对旧/新 COUNT、SUM完全一致，覆盖NULL、长度不足4、大小写、Unicode、尾随空格、空结果及SUM为NULL；并确认实际生产参数不是任意长度或包含其他通配符。未通过不得发布。
若不能改查询且尾缀形式不固定，可另评估(status,note,amount)覆盖索引；它只能按status范围缩小并残余过滤note，不能承诺尾缀可seek，且note较宽/状态可能低选择性，未量化前不建议直接生产建索引。不能仅因现有统计缺失就强制hint或只跑ANALYZE作为最终修复。

## 风险、回滚、复测
- 建索引回填、ANALYZE均增加CPU/IO与资源成本；须确认权限、余量和低峰窗口；目前诊断授权不含执行。
- 先应用灰度再扩大；线上回退先撤回新查询/发布，再删除本次新增索引和列，顺序不可反。
```sql
-- 仅经批准、确认应用不再引用后：
DROP INDEX idx_orders_status_suffix4_amount ON squad_lab.orders_big;
ALTER TABLE squad_lab.orders_big DROP COLUMN note_suffix4;
```
- 元数据恢复不代表性能恢复，回退旧查询会恢复原全扫风险，需保留应用限流/降级预案（另行审批）。
- ANALYZE不可承诺简单一键逆转；本次Serverless能力未验证统计导入恢复，不能以LOAD STATS作为已可用回滚。应先在隔离环境验证影响。
- 复测先普通EXPLAIN，计划需无目标TableFullScan、等值访问实际新索引；随后经授权在受控负载下执行真实SQL，不作无界EXPLAIN ANALYZE。
- 建议数据库验收门槛（待业务SLO确认）：同参数/数据量/并发下，平均processed keys较262144下降至少99%（<=2621），平均DB耗时<50ms、采集逐请求p95<100ms、错误数不增加；这些是目标，不是已达成或预测保证。Statement summary的均/最大值不能推导p95。
- 至少连续两个完整5分钟观测段、覆盖峰值并发及代表参数；旧新结果一致，写延迟/资源无不可接受回归。
- 业务恢复需单独满足端到端p95/p99及超时率的既定SLO、连接池无异常排队，且队长核对应用请求链路；未提供阈值前不能关闭P1。
- 预防：表重建/迁移后自动校验必需索引；对目标digest监测processed keys、plan_digest、错误及延迟；监测谓词列统计是否初始化，不能只看Healthy；为尾缀检索建立明确字段语义及迁移回归用例。

## inspector 交叉证据复核（原始附件已读取）
08:57:15 的 INFORMATION_SCHEMA.DATA_LOCK_WAITS=0、DEADLOCKS可见记录=0、CLUSTER_PROCESSLIST非Sleep且TIME>5秒=0；
MEMORY_USAGE当前75554816 / 限额1717986918 bytes（4.4%），峰值106037248 bytes。均只代表采样时可见状态，不反推告警前全局不存在等待或资源压力。
CLUSTER_TIDB_TRX有限样本的START_TIME与会话NOW存在8小时时钟口径差；不以28799秒作为长事务时长，不报告全局长事务为零。
