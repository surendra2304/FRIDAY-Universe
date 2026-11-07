#!/usr/bin/env python3
"""Test real FRIDAY HTTP dispatch against the isolated specialist fleet."""
import asyncio, hashlib, json, os, sys, time
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"FRIDAY/apps/core/src"))
from friday_core.universe_dispatch_bus import UniverseDispatchBus
S=[
("Inference","inference",["/health","/healthz"],"/v1/task/validate","", "X-API-Key"),
("Memora","memora",["/health","/healthz"],"/v1/task/execute","friday","X-Agent-Name"),
("IntelX","intelx",["/api/v1/health","/health","/healthz"],"/api/v1/task/execute","friday-test-only","X-API-Key"),
("Futuris","futuris",["/health","/healthz"],"/v1/task/execute","friday-test-only","X-Friday-Api-Key"),
("Stratex","stratex",["/health","/api/health"],"/v1/task/execute","friday-test-only","X-API-KEY"),
("Forge","forge",["/health","/api/health"],"/api/v1/forge/delegate","","X-API-Key"),
("Cortex","cortex",["/health","/health/ready"],"/v1/task/execute","friday-test-only","X-Friday-Api-Key"),
("VyralX","vyralx",["/ready"],"/v1/task/execute","vyralx-test-only","X-API-Key"),
("Sentinel","sentinel",["/health","/healthz"],"/api/v1/tasks","","X-API-Key"),]
def payload(n):
 tid="friday-standalone-"+n.lower()
 if n=="Inference": return {"source_agent":"friday","action":"reason","payload":{"prompt":"Validate this synthetic nonproduction request; do not call a model or external provider."}}
 if n=="Memora": return {"task_id":tid,"source_agent":"friday","target_agent":"memora","action":"query","payload":{"query":"FRIDAY nonproduction smoke marker","limit":1}}
 if n=="IntelX": return {"task_id":tid,"source_agent":"friday","target_agent":"intelx","action":"query","payload":{"query":"synthetic fixture only","limit":1}}
 if n in ("Futuris","Stratex","Forge"): return {"task_id":tid,"source_agent":"friday","target_agent":n.lower(),"action":"status","payload":{}}
 if n=="Cortex": return {"task_id":tid,"source_agent":"friday","target_agent":"cortex","action":"analyze","dry_run":True,"payload":{"dry_run":True,"goal":"Review synthetic nonproduction metrics; recommend only.","telemetry":{"visitors":12,"conversions":2}}}
 if n=="VyralX": return {"task_id":tid,"target_agent":"vyralx","action":"status","requested_mode":"sync","inputs":{}}
 if n=="Sentinel":
  now=datetime.now(UTC); t="http://inference:8000/health"
  return {"objective":"Loopback-only health observation.","targets":[{"type":"url","value":t}],"mode":"assessment","scope":{"owner":"local-test","written_authorization_reference":"FRIDAY-NONPROD-TEST-ONLY","allowed_targets":[t,"inference"],"allowed_methods":["discovery","validation"],"time_window":{"start_time":(now-timedelta(minutes=1)).isoformat(),"end_time":(now+timedelta(minutes=5)).isoformat()},"maximum_impact":"low","rate_limit":1,"authorization":{"allow_third_party_enrichment":False}}}
 raise ValueError(n)
async def main():
 async with httpx.AsyncClient() as client:
  health={}; deadline=time.monotonic()+180; pending=list(S)
  while pending and time.monotonic()<deadline:
   for s in pending[:]:
    n,p,paths,*_=s; base=f"http://{p}:8000"
    for path in paths:
     try:
      r=await client.get(base+path,timeout=3)
      if r.status_code==200: health[n]={"url":base+path,"status":r.status_code,"body":r.json() if r.content else {"status":"ok"}}; pending.remove(s); break
     except (httpx.HTTPError,ValueError): pass
   if pending: await asyncio.sleep(1)
  if pending: raise RuntimeError("Unhealthy services: "+", ".join(s[0] for s in pending))
 bus=UniverseDispatchBus()
 for n,p,paths,path,key,header in S:
  base=f"http://127.0.0.1:{p}"; bus.register_agent(n,base,base+paths[0],timeout_sec=30,max_retries=0,api_key=key,auth_header=header,action_path=path)
 captured=[]; original=httpx.AsyncClient.post
 async def capture(client,url,*args,**kwargs):
  r=await original(client,url,*args,**kwargs)
  try: body=r.json() if r.content else {}
  except ValueError: body={"text":r.text[:500]}
  captured.append({"url":str(url),"status":r.status_code,"body":body}); return r
 httpx.AsyncClient.post=capture
 receipts=[]
 try:
  for n,p,paths,path,key,header in S:
   friday=await bus.dispatch_async(n,"safe-smoke",payload(n),timeout_sec=30)
   r=captured[-1]; body=r["body"]
   if r["status"] not in (200,201,202,204): raise RuntimeError(f"{n} HTTP {r['status']}: {body}")
   row={"agent":n,"friday_task_id":friday.task_id,"friday_status":friday.status,"service_url":r["url"],"http_status":r["status"],"health":health[n],"service_response":body}
   if n=="Inference":
    if body.get("valid") is not True or body.get("prompt_safe") is not True: raise RuntimeError("Inference validation failed: "+str(body))
    row["service_receipt"]={"requested_action":"reason-validation","authorization_decision":"AUTHORIZED","verification_evidence":{"source":"inference.v1.task.validate","task_id":friday.task_id,"valid":True,"prompt_safe":True}}
   elif n=="Sentinel":
    task_id=str(body.get("task_id") or ""); base=f"http://127.0.0.1:{p}"; end=time.monotonic()+30; task={}
    async with httpx.AsyncClient() as c:
     while task_id and time.monotonic()<end:
      q=await c.get(f"{base}/api/v1/tasks/{task_id}",timeout=5)
      if q.status_code==200:
       task=q.json()
       if str(task.get("status","")).lower() in {"completed","complete","failed","blocked","cancelled"}: break
      await asyncio.sleep(.25)
     if str(task.get("status","")).lower() not in {"completed","complete"}: raise RuntimeError("Sentinel loopback task did not complete: "+str(task))
     ev=await c.get(f"{base}/api/v1/tasks/{task_id}/evidence",timeout=5)
     if ev.status_code!=200 or not ev.json(): raise RuntimeError("Sentinel did not persist evidence")
     row["service_response"]=task; row["service_receipt"]={"requested_action":"loopback-health-observation","authorization_decision":"AUTHORIZED","verification_evidence":{"source":"sentinel.local-task-evidence","task_id":task_id,"status":task.get("status"),"evidence":ev.json()}}
   else:
    receipt=body.get("receipt") if isinstance(body,dict) else None
    evidence=receipt.get("verification_evidence") if isinstance(receipt,dict) else None
    if not isinstance(evidence,dict) or not evidence: raise RuntimeError(f"{n} receipt has no verification evidence: {body}")
    row["service_receipt"]=receipt
   digest=json.dumps(row["service_response"],sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
   row["response_sha256"]=hashlib.sha256(digest).hexdigest(); receipts.append(row)
 finally: httpx.AsyncClient.post=original
 if len(receipts)!=9: raise RuntimeError("Expected nine specialist receipts")
 out=Path(os.environ.get("FRIDAY_TEST_RECEIPTS_PATH", str(ROOT/"generated-artifacts/friday-standalone-test/receipts.json"))); out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({"runner":"FRIDAY UniverseDispatchBus","mode":"nonproduction-test","agents_total":10,"specialists":len(receipts),"external_network":"isolated internal test mesh","health":health,"receipts":receipts},indent=2)+"\n",encoding="utf-8")
 print(f"Verified {len(receipts)} evidence-backed service receipts; 10 total agents.")
if __name__=="__main__": asyncio.run(main())
