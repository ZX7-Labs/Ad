"""Physical single-use browser artifact authorization and tamper tests."""
from __future__ import annotations
import hashlib
import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

from studio_next.body_download_tickets import DownloadTickets
from studio_next.body_service import make_body_http_handler


class TicketAuthorityTests(unittest.TestCase):
    def test_single_use_rights_and_expiry(self):
        now=[30.0]
        tickets=DownloadTickets(ttl=2,max_outstanding=2,clock=lambda:now[0])
        original="a"*64
        ticket=tickets.issue("film_01","finished/original.mp4",sha256=original,length=721)
        self.assertNotIn("Bearer",str(ticket))
        self.assertNotIn("a"*64,ticket["url"])
        token=ticket["url"].rsplit("/",1)[1]
        result=tickets.consume(token)
        self.assertEqual(result["job_id"],"film_01")
        self.assertEqual(result["relative"],"finished/original.mp4")
        self.assertEqual(result["sha256"],original)
        self.assertIsNone(tickets.consume(token))
        expired=tickets.issue("film_02","original.wav",sha256="b"*64,length=12)
        now[0]+=2
        self.assertIsNone(tickets.consume(expired["url"].rsplit("/",1)[1]))

    def test_bounded_and_concurrent_consume(self):
        gate=DownloadTickets(max_outstanding=1)
        u=gate.issue("film","clip.mp4",sha256="c"*64,length=222)["url"].split("/")[-1]
        with self.assertRaises(RuntimeError):
            gate.issue("film","clip.mp4",sha256="c"*64,length=222)
        with ThreadPoolExecutor(max_workers=10) as pool:
            replies=list(pool.map(gate.consume,[u]*10))
        self.assertEqual(sum(x is not None for x in replies),1)

    def test_invalid_ticket_claims_never_issued(self):
        t=DownloadTickets()
        for digest in ("", "x"*64, "a"*63, 4):
            with self.assertRaises(ValueError):
                t.issue("film","media.mp4",sha256=digest,length=300)
        for n in (-1,0,True,"999"):
            with self.assertRaises(ValueError):
                t.issue("film","media.mp4",sha256="a"*64,length=n)


class ActualAuthorizedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"original.wav"
        # This stub verifies only the authenticated HTTP/ticket boundary.
        self.path.write_bytes(b"provenance-bound original output bytes")
        self.token="only-in-test-actual-body-token-with-32-plus-characters"
        file=self.path
        owner=self
        self.mutate_after_inspect=False
        class OwnerMedia:
            def inspect_media(self,job,relative):
                if job!="owner-job" or relative!="original.wav":
                    raise ValueError("Unregistered original owner media")
                data=file.read_bytes()
                evidence={"path":file,"mime":"audio/wav","bytes":len(data),
                          "sha256":hashlib.sha256(data).hexdigest()}
                if owner.mutate_after_inspect:
                    owner.mutate_after_inspect=False
                    file.write_bytes(b"Z"*len(data))
                return evidence
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
            make_body_http_handler(OwnerMedia(),self.token))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)
        self.temp.cleanup()

    def request(self,method,path,token=None):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=8)
        headers={"Authorization":"Bearer "+token} if token else {}
        c.request(method,path,body=b"" if method=="POST" else None,headers=headers)
        r=c.getresponse()
        code,head,body=r.status,dict(r.getheaders()),r.read()
        c.close()
        return code,head,body

    def issue(self):
        path="/v1/jobs/owner-job/artifacts/original.wav/download-ticket"
        return self.request("POST",path,self.token)

    def test_no_ticket_without_full_owner_bearer(self):
        code,_,_=self.request("POST",
            "/v1/jobs/owner-job/artifacts/original.wav/download-ticket")
        self.assertEqual(code,401)
        code,_,_=self.request("POST",
            "/v1/jobs/owner-job/artifacts/unknown.mp4/download-ticket",self.token)
        self.assertEqual(code,400)

    def test_real_download_exact_bytes_once(self):
        code,_,data=self.issue()
        self.assertEqual(code,201)
        ticket=json.loads(data)
        self.assertTrue(ticket["single_use"])
        code,head,data=self.request("GET",ticket["url"])
        self.assertEqual(code,200)
        self.assertEqual(data,self.path.read_bytes())
        self.assertEqual(head["X-ZX7-SHA256"],hashlib.sha256(data).hexdigest())
        self.assertIn("no-referrer",head["Referrer-Policy"])
        code,_,_=self.request("GET",ticket["url"])
        self.assertEqual(code,404)

    def test_same_length_content_swap_between_inspection_and_send_is_409(self):
        code,_,data=self.issue()
        self.assertEqual(code,201)
        ticket=json.loads(data)
        self.mutate_after_inspect=True
        code,head,actual=self.request("GET",ticket["url"])
        self.assertEqual(code,409)
        self.assertIn(b"SHA256",actual)
        self.assertNotEqual(actual,self.path.read_bytes())
        self.assertNotIn("X-ZX7-SHA256",head)
        replay,_,_=self.request("GET",ticket["url"])
        self.assertEqual(replay,404)

    def test_changed_media_fails_closed_after_ticket_issue(self):
        code,_,data=self.issue()
        self.assertEqual(code,201)
        ticket=json.loads(data)
        self.path.write_bytes(self.path.read_bytes()+b"-mutated")
        code,_,data=self.request("GET",ticket["url"])
        self.assertEqual(code,409)
        self.assertIn(b"changed",data)


if __name__=="__main__":
    unittest.main()
