import os,json,time,datetime,pathlib,importlib.util
s=importlib.util.spec_from_file_location("db",os.path.join(os.getcwd(),"skills/dba_inspect.py"));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
path=pathlib.Path("evidence/repair_apply_20261002.json");out={"started_at":datetime.datetime.now().astimezone().isoformat(),"checks":[]};c=m.connect()
def q(name,sql):
 item={"name":name,"sql":sql,"at":datetime.datetime.now().astimezone().isoformat()};t=time.perf_counter()
 try:
  with c.cursor() as cur:
   cur.execute(sql);item["rows"]=[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()] if cur.description else [];item["ok"]=True
 except Exception as e:item.update(ok=False,error=str(e));raise
 finally:
  item["wall_ms"]=(time.perf_counter()-t)*1000;out["checks"].append(item);path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str));print(name,item["ok"],round(item["wall_ms"],3),flush=True)
 return item["rows"]
try:
 before=q("structure_before","SHOW CREATE TABLE squad_lab.orders_big")[0]["Create Table"]
 assert "note_suffix4" not in before,"Column exists; stop, inspect instead of repeat"
 inds=q("indexes_before","SHOW INDEX FROM squad_lab.orders_big");assert len(inds)==1 and inds[0]["Key_name"]=="PRIMARY"
 mem=q("memory_before","SELECT MEMORY_CURRENT,MEMORY_LIMIT FROM INFORMATION_SCHEMA.MEMORY_USAGE LIMIT 1")[0]
 assert int(mem["MEMORY_CURRENT"])/int(mem["MEMORY_LIMIT"])<.7
 assert q("locks_before","SELECT COUNT(*) n FROM INFORMATION_SCHEMA.DATA_LOCK_WAITS")[0]["n"]==0
 q("add_column","ALTER TABLE squad_lab.orders_big ADD COLUMN note_suffix4 VARCHAR(4) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin GENERATED ALWAYS AS (RIGHT(note,4)) VIRTUAL")
 q("add_column_warnings","SHOW WARNINGS")
 q("create_index","CREATE INDEX idx_orders_status_suffix4_amount ON squad_lab.orders_big(status,note_suffix4,amount)")
 q("create_index_warnings","SHOW WARNINGS")
 q("structure_after","SHOW CREATE TABLE squad_lab.orders_big")
 idx=q("indexes_after","SHOW INDEX FROM squad_lab.orders_big")
 assert [r["Column_name"] for r in idx if r["Key_name"]=="idx_orders_status_suffix4_amount"]==["status","note_suffix4","amount"]
 q("ddl_state","SELECT JOB_ID,JOB_TYPE,STATE,CREATE_TIME,START_TIME,END_TIME FROM INFORMATION_SCHEMA.DDL_JOBS WHERE DB_NAME='squad_lab' AND TABLE_NAME='orders_big' ORDER BY JOB_ID DESC LIMIT 5")
 q("analyze","ANALYZE TABLE squad_lab.orders_big COLUMNS status,note,note_suffix4,amount")
 q("analyze_warnings","SHOW WARNINGS")
 q("stats_meta_after","SHOW STATS_META WHERE Db_name='squad_lab' AND Table_name='orders_big'")
 q("stats_histograms_after","SHOW STATS_HISTOGRAMS WHERE Db_name='squad_lab' AND Table_name='orders_big'")
 q("memory_after","SELECT MEMORY_CURRENT,MEMORY_LIMIT FROM INFORMATION_SCHEMA.MEMORY_USAGE LIMIT 1")
 out["completed"]=True
finally:
 c.close();out["ended_at"]=datetime.datetime.now().astimezone().isoformat();path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str))
