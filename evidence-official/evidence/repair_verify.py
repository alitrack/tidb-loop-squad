import os,json,time,datetime,pathlib,importlib.util,statistics
s=importlib.util.spec_from_file_location("db",os.path.join(os.getcwd(),"skills/dba_inspect.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
path=pathlib.Path("evidence/repair_verify_20261002.json");out={"started_at":datetime.datetime.now().astimezone().isoformat(),"checks":[]};c=m.connect()
assert json.loads(pathlib.Path("evidence/repair_apply_20261002.json").read_text()).get("completed"),"Apply not complete"
def q(name,sql):
 item={"name":name,"sql":sql,"at":datetime.datetime.now().astimezone().isoformat()};t=time.perf_counter()
 try:
  with c.cursor() as cur:
   cur.execute(sql);item["rows"]=[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()] if cur.description else [];item["ok"]=True
 except Exception as e:item.update(ok=False,error=str(e));raise
 finally:
  item["wall_ms"]=(time.perf_counter()-t)*1000;out["checks"].append(item);path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
 return item["rows"]
original="SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big WHERE note LIKE '%-042' AND status='new'"
rewrite="SELECT COUNT(*), SUM(amount) FROM squad_lab.orders_big WHERE note_suffix4='-042' AND status='new'"
try:
 q("clock_connection","SELECT NOW(6) db_now, UTC_TIMESTAMP(6) db_utc, CONNECTION_ID() connection_id, @@session.time_zone tz, @@session.transaction_isolation isolation_level")
 q("explain_original","EXPLAIN FORMAT='brief' "+original)
 q("explain_rewrite","EXPLAIN FORMAT='brief' "+rewrite)
 q("snapshot_begin","START TRANSACTION WITH CONSISTENT SNAPSHOT")
 results=[]
 for i in range(5):
  for kind,sql in [("original",original),("rewrite",rewrite)]:
   r=q(kind+"_"+str(i+1),sql);results.append(r)
   assert out["checks"][-1]["wall_ms"]<2000,"Latency gate >2s; stop"
 assert all(r==results[0] for r in results),"Aggregate mismatch; stop"
 out["same_snapshot_equal"]=True;out["aggregate"]=results[0]
 q("snapshot_end","ROLLBACK")
 for kind in ["original","rewrite"]:
  vals=[x["wall_ms"] for x in out["checks"] if x["name"].startswith(kind+"_")]
  out[kind+"_timing"]={"n":len(vals),"each_ms":vals,"mean_ms":statistics.mean(vals),"median_ms":statistics.median(vals),"min_ms":min(vals),"max_ms":max(vals)}
 q("ddl_final","SELECT JOB_ID,JOB_TYPE,STATE,CREATE_TIME,START_TIME,END_TIME FROM INFORMATION_SCHEMA.DDL_JOBS WHERE DB_NAME='squad_lab' AND TABLE_NAME='orders_big' ORDER BY JOB_ID DESC LIMIT 3")
 q("locks_after","SELECT COUNT(*) n FROM INFORMATION_SCHEMA.DATA_LOCK_WAITS")
 q("memory_after","SELECT MEMORY_CURRENT,MEMORY_LIMIT FROM INFORMATION_SCHEMA.MEMORY_USAGE LIMIT 1")
 out["completed"]=True
finally:
 c.close();out["ended_at"]=datetime.datetime.now().astimezone().isoformat();path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str));print(json.dumps(out,ensure_ascii=False,indent=2,default=str))
