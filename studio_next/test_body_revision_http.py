"""Physically running authenticated HTTP contract for original film revision preview."""
from __future__ import annotations

import copy
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from studio_next.body_service import make_body_http_handler
from studio_next.test_body_revision_impact import original_film


class ActualReadOnlyFilmDiffHTTP(unittest.TestCase):
    def setUp(self):
        self.home=tempfile.TemporaryDirectory()
        self.root=Path(self.home.name)
        self.before=original_film(self.root)
        self.after=copy.deepcopy(self.before)
        self.after["shots"][1]["duration_seconds"]=5.8
        self.token="owner-local-token-for-film-revision-with-32-chars"
        class Dummy:
            pass
        self.server=ThreadingHTTPServer(("127.0.0.1",0),
               make_body_http_handler(Dummy(),self.token))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=4)
        self.home.cleanup()
    def request(self,payload,token=None):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=8)
        headers={"Content-Type":"application/json"}
        if token:
            headers["Authorization"]="Bearer "+token
        data=json.dumps(payload).encode("utf-8")
        conn.request("POST","/v1/revisions/impact",body=data,headers=headers)
        response=conn.getresponse()
        output=response.status,json.loads(response.read())
        conn.close()
        return output
    def test_real_http_only_auth_owner_and_no_original_revision_mutation(self):
        old=json.dumps(self.before,sort_keys=True)
        new=json.dumps(self.after,sort_keys=True)
        code,_=self.request({"before":self.before,"after":self.after})
        self.assertEqual(code,401)
        code,_=self.request({"before":self.before,"after":self.after},token="wrong")
        self.assertEqual(code,401)
        code,report=self.request({"before":self.before,"after":self.after},token=self.token)
        self.assertEqual(code,200,report)
        self.assertEqual(report["original_unchanged_candidates"],["render1","audio_master"])
        self.assertEqual(report["new_or_changed_operations"],["render2","final"])
        self.assertFalse(report["reusable_cached_bytes_proven"])
        self.assertFalse(report["source_media_bytes_physically_rechecked"])
        self.assertTrue(report["requires_runtime_custody_validation"])
        self.assertEqual(json.dumps(self.before,sort_keys=True),old)
        self.assertEqual(json.dumps(self.after,sort_keys=True),new)
        self.assertFalse((self.root/"production.sqlite3").exists())
    def test_attack_malformed_or_unlicensed_original_film_never_executes(self):
        for payload in ({},{"before":self.before},[],
                        {"before":self.before,"after":self.after,"admin":True}):
            code,_=self.request(payload,token=self.token)
            self.assertEqual(code,400)
        invalid=copy.deepcopy(self.after)
        invalid["assets"][0]["rights"]="unknown-rights"
        code,result=self.request({"before":self.before,"after":invalid},token=self.token)
        self.assertEqual(code,400)
        self.assertIn("unsafe/unrenderable",result["error"])


if __name__=="__main__":
    unittest.main()
