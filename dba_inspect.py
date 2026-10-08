#!/usr/bin/env python3
"""dba_inspect.py — TiDB 值夜小队 · 巡检员技能 v1
直连平凯云 TiDB（MySQL 协议），输出结构化巡检单。
用法: python3 dba_inspect.py [--json]
依赖: pip install pymysql
连接串优先读环境变量 TIDB_DSN (mysql://user:pass@host:port/db)
"""
import os, sys, json, argparse
import pymysql
from urllib.parse import urlparse

DSN = os.environ.get(
    "TIDB_DSN",
    "mysql://<CLUSTER_ID>.root:goDpB0G4o6pIEzRP@gateway01.cn-shanghai.aliyun.pingkai.cn:4000/sys",
)

CHECKS = [
    ("top_sql", """SELECT LEFT(digest_text,80) sql_text, exec_count,
        ROUND(avg_latency/1e6,1) avg_ms, ROUND(max_latency/1e6,1) max_ms,
        ROUND(sum_latency/1e6,1) total_ms, AVG_RESULT_ROWS avg_rows
        FROM information_schema.statements_summary_history
        ORDER BY sum_latency DESC LIMIT 10""", "statements_summary_history"),
    ("lock_waits", """SELECT COUNT(*) waiting_txns FROM information_schema.data_lock_waits""",
     "data_lock_waits"),
    ("deadlocks", """SELECT COUNT(*) deadlock_cnt FROM information_schema.deadlocks""",
     "deadlocks"),
    ("long_txns", """SELECT id, user, db, time AS sec, LEFT(info,60) current_sql
        FROM information_schema.cluster_processlist WHERE command!='Sleep' AND time > 5
        ORDER BY time DESC LIMIT 10""", "cluster_processlist"),
    ("ddl_jobs_recent", """SELECT JOB_ID job_id, JOB_TYPE job_type, DB_NAME db,
        TABLE_NAME tbl, STATE state, CREATE_TIME created
        FROM information_schema.ddl_jobs ORDER BY JOB_ID DESC LIMIT 10""", "ddl_jobs"),
    ("memory", """SELECT MEMORY_CURRENT used_bytes, MEMORY_LIMIT limit_bytes,
        MEMORY_MAX_USED max_used_bytes,
        ROUND(MEMORY_CURRENT*100/(MEMORY_LIMIT+1),1) used_pct
        FROM information_schema.memory_usage LIMIT 1""", "memory_usage"),
    ("summary_tables", """SELECT table_name FROM information_schema.tables
        WHERE table_schema='information_schema' LIMIT 3""", "tables(连通哨兵)"),
]

def connect():
    u = urlparse(DSN)
    return pymysql.connect(
        host=u.hostname, port=u.port or 4000, user=u.username,
        password=u.password or "", database=(u.path or "/sys").lstrip("/") or "sys",
        ssl={"ssl": {}}, connect_timeout=10, read_timeout=30,
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out, c = {}, connect()
    cur = c.cursor()
    for name, sql, src in CHECKS:
        try:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            out[name] = {"ok": True, "source": src, "rows": rows}
        except Exception as e:
            out[name] = {"ok": False, "source": src, "error": str(e)[:120]}
    c.close()
    # 巡检快照落盘（历史库，供趋势对比）——失败不阻断
    try:
        import pathlib, json as j
        p = pathlib.Path.home() / ".tidb_squad" / "history"
        p.mkdir(parents=True, exist_ok=True)
        (p / f"inspect_{__import__('time').strftime('%Y%m%d_%H%M%S')}.json").write_text(
            j.dumps(out, ensure_ascii=False, default=str))
    except Exception:
        pass
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str)
          if args.json else render(out))

def render(o):
    lines = ["=" * 46, "TiDB 值夜巡检单", "=" * 46]
    for k, v in o.items():
        lines.append(f"\n[{k}]  来源: {v['source']}  {'✅' if v['ok'] else '❌ ' + v.get('error','')}")
        if v["ok"]:
            for r in v["rows"][:6]:
                lines.append("  " + " | ".join(f"{kk}={vv}" for kk, vv in list(r.items())[:7]))
    lines.append("\n(完)")
    return "\n".join(lines)

if __name__ == "__main__":
    main()
