"""Independent local authenticated production-body service.

Run real locally installed creative tools WITHOUT ChatGPT supervision.
POST a model/artist-authored original Film IR, obtain an ID, poll status,
and restart interrupted jobs from the same SQLite + MediaVault stages.

This is a loopback-only trusted host API, never a public internet deployment.
No paid calls, software installs, shell commands, image/style templates or
infinite hidden background jobs. Real media is created only by registered tools.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hmac
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .body_capabilities import operational_tool_summary,explain_operational_tool
from .body_integration import run_body_project
from .media_vault import MediaVault

_ID=re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_MAX_JOB_BODY=4*1024*1024
_MAX_OWNER_FILE=1024*1024*1024
_MEDIA_NAME=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,179}$")
_MEDIA_MIME={".mp4":"video/mp4",".mov":"video/quicktime",
             ".webm":"video/webm",".png":"image/png",".jpeg":"image/jpeg",
             ".jpg":"image/jpeg",".webp":"image/webp",".svg":"image/svg+xml",
             ".wav":"audio/wav",".mp3":"audio/mpeg",".flac":"audio/flac",
             ".glb":"model/gltf-binary",".bin":"application/octet-stream"}


class LocalBodyCoordinator:
    def __init__(self,root,*,execute=None,workers=1):
        if type(workers) is not int or not (1<=workers<=16):
            raise ValueError("Operator must choose finite host workload capacity")
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.projects=self.root/"projects"
        self.projects.mkdir(exist_ok=True)
        self.database=self.root/"body-jobs.sqlite3"
        self.executor=concurrent.futures.ThreadPoolExecutor(
            max_workers=workers,thread_name_prefix="zx7-original-body")
        self._queued=set()
        self._lock=threading.RLock()
        self.execute=execute or run_body_project
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,
                original_ir TEXT NOT NULL,status TEXT NOT NULL,
                attempts INTEGER NOT NULL, result TEXT,
                modified REAL NOT NULL)""")

    def _connect(self):
        db=sqlite3.connect(self.database,timeout=30,isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def _workspace(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Unsafe original project/workspace identity")
        place=(self.projects/identity).resolve()
        if not place.is_relative_to(self.projects):
            raise ValueError("Original project cannot escape studio folder")
        return place

    def upload_owner_media(self,workspace_id,filename,stream,bytes_expected,*,
                           mime,source_id,rights_evidence):
        """Owner-authenticated real bytes, never a model-created rights label.

        The file becomes visible only after full byte transfer and real
        decoder/provenance verification. No overwrite and no URL fetching.
        """
        if not isinstance(filename,str) or not _MEDIA_NAME.fullmatch(filename):
            raise ValueError("Invalid media asset file identity")
        if _MEDIA_MIME.get(Path(filename).suffix.lower())!=mime:
            raise ValueError("Media extension does not match declared source type")
        if type(bytes_expected) is not int or not (0<bytes_expected<=_MAX_OWNER_FILE):
            raise ValueError("Upload size exceeds operator-approved local resource budget")
        if not isinstance(source_id,str) or not source_id.strip() or (
                not isinstance(rights_evidence,str) or not rights_evidence.strip()):
            raise ValueError("Owner must explicitly attest the original media source")
        folder=self._workspace(workspace_id)
        folder.mkdir(parents=True,exist_ok=True)
        final=folder/filename
        if final.exists():
            raise FileExistsError("Original imported media is immutable; never overwrite")
        stage=folder/(".zx7-import-"+uuid.uuid4().hex+".tmp")
        published=False
        try:
            with stage.open("xb") as dest:
                remaining=bytes_expected
                while remaining:
                    chunk=stream.read(min(1024*1024,remaining))
                    if not isinstance(chunk,(bytes,bytearray)) or not chunk:
                        raise ValueError("Owner upload ended before declared physical bytes")
                    dest.write(chunk)
                    remaining-=len(chunk)
                dest.flush()
                os.fsync(dest.fileno())
            vault=MediaVault(folder/"vault")
            attested=vault.ingest(stage,mime=mime,rights="owner_supplied",
                source_type="owner_upload",source_id=source_id,
                evidence=rights_evidence,owner_or_generator="authenticated_local_owner")
            os.link(stage,final)
            published=True
            return {"source":filename,"asset_id":attested["asset_id"],
                    "attestation_id":attested["attestation_id"],
                    "mime":mime,"bytes":bytes_expected,
                    "verified_real_media_bytes":True,
                    "rights_claim":"Owner-attested; no independent legal ownership certification"}
        except BaseException:
            if published:final.unlink(missing_ok=True)
            raise
        finally:
            stage.unlink(missing_ok=True)

    def submit(self,film_ir,*,workspace_id,job_id=None):
        if not isinstance(film_ir,dict) or not isinstance(film_ir.get("tool_graph"),list):
            raise ValueError("Original creative Film IR and actual tool graph required")
        root=self._workspace(workspace_id)
        root.mkdir(parents=True,exist_ok=True)
        identifier=job_id or uuid.uuid4().hex
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid production job identity")
        encoded=json.dumps(film_ir,allow_nan=False,ensure_ascii=False)
        with self._connect() as db:
            try:
                db.execute("""INSERT INTO jobs VALUES(?,?,?,?,?,?,?)""",
                    (identifier,workspace_id,encoded,"queued",0,None,time.time()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Original creative job ID already exists; never overwrite") from exc
        self.queue(identifier)
        return {"job_id":identifier,"workspace_id":workspace_id,"status":"queued",
                "original_artistic_plan_preserved":True}

    def queue(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Invalid job identity")
        with self._lock:
            if identity in self._queued:
                return False
            with self._connect() as db:
                found=db.execute("SELECT status FROM jobs WHERE id=?",(identity,)).fetchone()
            if found is None:raise ValueError("Unknown submitted project")
            if found[0]=="completed":
                return False
            self._queued.add(identity)
            self.executor.submit(self._work,identity)
            return True

    def _work(self,identity):
        try:
            with self._connect() as db:
                # Jobs already have a bounded single executor owner locally.
                db.execute("""UPDATE jobs SET status='running',attempts=attempts+1,
                           modified=? WHERE id=?""",(time.time(),identity))
                row=db.execute("SELECT workspace_id,original_ir FROM jobs WHERE id=?",
                               (identity,)).fetchone()
            if row is None:raise ValueError("Submitted original film vanished")
            location=self._workspace(row[0])
            original=json.loads(row[1])
            # Execution itself uses the crash-safe graph/physical witness vault.
            result=self.execute(original,location)
            if not isinstance(result,dict):
                raise RuntimeError("Original film tool graph produced no audit result")
            ok=result.get("status")=="all_tool_results_verified"
            status="completed" if ok else "blocked"
            report=result
        except BaseException as exc:
            status="failed"
            report={"status":"failed","message":type(exc).__name__+": "+str(exc),
                    "movie_delivered":False}
        finally:
            with self._connect() as db:
                db.execute("""UPDATE jobs SET status=?,result=?,modified=? WHERE id=?""",
                    (status,json.dumps(report,allow_nan=False,ensure_ascii=False),
                     time.time(),identity))
            with self._lock:
                self._queued.discard(identity)

    def inspect(self,identity):
        if not isinstance(identity,str) or not _ID.fullmatch(identity):
            raise ValueError("Invalid original job identity")
        with self._connect() as db:
            row=db.execute("""SELECT workspace_id,status,attempts,result,modified
                FROM jobs WHERE id=?""",(identity,)).fetchone()
        if row is None:raise ValueError("Unknown job")
        return {"job_id":identity,"workspace_id":row[0],"status":row[1],
                "attempts":row[2],"result":json.loads(row[3]) if row[3] else None,
                "updated_at":row[4]}

    def pending_restart(self):
        with self._connect() as db:
            ids=[x[0] for x in db.execute(
                "SELECT id FROM jobs WHERE status IN ('queued','running')")]
        for identity in ids:
            self.queue(identity)
        return len(ids)

    def close(self):
        self.executor.shutdown(wait=True)


def make_body_http_handler(coordinator,token):
    if not isinstance(token,str) or len(token)<32:
        raise ValueError("Local creative body API needs secret >=32 characters")
    class Handler(BaseHTTPRequestHandler):
        server_version="ZX7Body/1"
        def log_message(self,format,*args):
            pass
        def _reply(self,code,payload):
            binary=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(binary)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(binary)
        def _authorized(self):
            actual=self.headers.get("Authorization","")
            if not hmac.compare_digest(actual,"Bearer "+token):
                self._reply(401,{"error":"Local production service requires host authorization"})
                return False
            return True
        def do_GET(self):
            if not self._authorized():return
            path=urlsplit(self.path).path
            try:
                if path=="/v1/health":
                    return self._reply(200,{"service":"zx7-local-body",
                        "host_only":"127.0.0.1","online":True})
                if path=="/v1/tools":
                    return self._reply(200,{"tools":operational_tool_summary(
                        coordinator.projects)})
                if path.startswith("/v1/tools/"):
                    name=path.removeprefix("/v1/tools/")
                    return self._reply(200,explain_operational_tool(
                        coordinator.projects,name))
                if path.startswith("/v1/jobs/"):
                    identity=path.removeprefix("/v1/jobs/")
                    return self._reply(200,coordinator.inspect(identity))
                return self._reply(404,{"error":"Unknown local body endpoint"})
            except (ValueError,TypeError) as exc:
                return self._reply(400,{"error":str(exc)})
        def do_POST(self):
            if not self._authorized():return
            path=urlsplit(self.path).path
            if path.startswith("/v1/workspaces/") and "/assets/" in path:
                pieces=path.split("/")
                if len(pieces)!=6 or pieces[1:3]!=["v1","workspaces"] or (
                        pieces[4]!="assets"):
                    return self._reply(404,{"error":"Invalid original media route"})
                try:
                    length=int(self.headers.get("Content-Length","0"))
                    receipt=coordinator.upload_owner_media(
                        pieces[3],pieces[5],self.rfile,length,
                        mime=self.headers.get("Content-Type",""),
                        source_id=self.headers.get("X-Source-Id",""),
                        rights_evidence=self.headers.get("X-Rights-Evidence",""))
                    return self._reply(201,receipt)
                except (ValueError,TypeError,FileExistsError,OSError) as exc:
                    return self._reply(400,{"error":str(exc)})
            if path!="/v1/jobs":
                return self._reply(404,{"error":"Only original film jobs and owned media can be submitted"})
            try:
                length=int(self.headers.get("Content-Length","0"))
                if not (0<length<=_MAX_JOB_BODY):
                    raise ValueError("Bounded Film IR upload required; upload assets separately")
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={"workspace_id","film_ir"}:
                    raise ValueError("Job request requires original Film IR and workspace")
                return self._reply(202,coordinator.submit(
                    body["film_ir"],workspace_id=body["workspace_id"]))
            except (ValueError,TypeError,json.JSONDecodeError) as exc:
                return self._reply(400,{"error":str(exc)})
    return Handler


def start_local_body_service(root,*,secret,port=8765,workers=1):
    if type(port) is not int or not (0<port<65536):
        raise ValueError("Local port must be explicit and valid")
    coordinator=LocalBodyCoordinator(root,workers=workers)
    coordinator.pending_restart()
    server=ThreadingHTTPServer(("127.0.0.1",port),
        make_body_http_handler(coordinator,secret))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        coordinator.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace-root",type=Path,required=True)
    p.add_argument("--port",type=int,default=8765)
    p.add_argument("--workers",type=int,default=1)
    a=p.parse_args()
    secret=os.getenv("ZX7_BODY_API_TOKEN")
    if not secret or len(secret)<32:
        raise SystemExit("Set a unique 32+ character ZX7_BODY_API_TOKEN in host environment")
    start_local_body_service(a.workspace_root,secret=secret,
                             port=a.port,workers=a.workers)


if __name__=="__main__":main()
