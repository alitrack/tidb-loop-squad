import os,json,time,datetime,pathlib,importlib.util,statistics
s=importlib.util.spec_from_file_location("db",os.path.join(os.getcwd(),"skills/dba_inspect.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
path=pathlib.Path("evidence/repair_preflight_20261002.json")
out={"started_at":datetime.datetime.now().astimezone().isoformat(),"checks":[]}
c=m.connect()
def q(name,sql):
 t=time.perf_counter();item={"name":name,"sql":sql,"at":datetime.datetime.now().astimezone().isoformat()}
 try:
  with c.cursor() as cur:
   cur.execute(sql);item["rows"]=[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()] if cur.description else [];item["ok"]=True
 except Exception as e:item.update(ok=False,error=str(e));raise
 finally:
  item["wall_ms"]=(time.perf_counter()-t)*1000;out["checks"].append(item);path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
 return item["rows"]
try:
 q("clock","SELECT NOW(6) db_now, UTC_TIMESTAMP(6) db_utc, @@session.time_zone tz")
 q("structure","SHOW CREATE TABLE squad_lab.orders_big")
 inds=q("indexes","SHOW INDEX FROM squad_lab.orders_big")
 assert len(inds)==1 and inds[0]["Key_name"]=="PRIMARY","Unexpected schema; stop"
 mem=q("memory","SELECT MEMORY_CURRENT,MEMORY_LIMIT FROM INFORMATION_SCHEMA.MEMORY_USAGE LIMIT 1")[0]
 assert int(mem["MEMORY_CURRENT"])/int(mem["MEMORY_LIMIT"])<.7,"Memory gate"
 locks=q("locks","SELECT COUNT(*) n FROM INFORMATION_SCHEMA.DATA_LOCK_WAITS")[0];assert locks["n"]==0
 q("ddl","SELECT JOB_ID,JOB_TYPE,STATE FROM INFORMATION_SCHEMA.DDL_JOBS WHERE TABLE_NAME='orders_big' ORDER BY JOB_ID DESC LIMIT 5")
 boundary="""SELECT note, note LIKE '%-042' old_match, RIGHT(note,4)='-042' new_match,
 ((note LIKE '%-042') <=> (RIGHT(note,4)='-042')) same
 FROM (SELECT CAST(NULL AS CHAR(256) CHARACTER SET utf8mb4) COLLATE utf8mb4_bin note
 UNION ALL SELECT '' UNION ALL SELECT '042' UNION ALL SELECT '-042'
 UNION ALL SELECT 'abc-042' UNION ALL SELECT '中文-042' UNION ALL SELECT 'abc-042 '
 UNION ALL SELECT 'abc-042x' UNION ALL SELECT 'ABC-042' UNION ALL SELECT 'x%-042'
 UNION ALL SELECT 'abc-043' UNION ALL SELECT '🙂-042') t"""
 rows=q("boundary_semantics",boundary);assert all(r["same"]==1 for r in rows)
 sql="SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big WHERE note LIKE '%-042' AND status='new'"
 q("explain_before","EXPLAIN FORMAT='brief' "+sql)
 q("snapshot_begin","START TRANSACTION WITH CONSISTENT SNAPSHOT")
 base=[]
 for i in range(5):
  r=q("baseline_original_"+str(i+1),sql);base.append(r)
  assert out["checks"][-1]["wall_ms"]<2000,"Latency gate >2s"
 assert all(r==base[0] for r in base)
 q("snapshot_end","ROLLBACK")
 out["baseline_wall_ms"]=[x["wall_ms"] for x in out["checks"] if x["name"].startswith("baseline_original_")]
 out["baseline_mean_ms"]=statistics.mean(out["baseline_wall_ms"])
 out["baseline_median_ms"]=statistics.median(out["baseline_wall_ms"])
 out["all_gates_passed"]=True
finally:
 c.close();out["ended_at"]=datetime.datetime.now().astimezone().isoformat();path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
 print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
