"""Security, static mobile delivery and unchanged authorization regression checks."""
from __future__ import annotations
import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer

from studio_next.body_mobile import ASSETS,CSP,PAGE,SCRIPT
from studio_next.body_service import make_body_http_handler


class FakeCoordinator:
    projects = "/tmp"
    def list_jobs(self):
        return {"jobs":[]}


class BodyMobileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token="unit-test-only-token-that-is-longer-than-32-bytes"
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),
            make_body_http_handler(FakeCoordinator(),cls.token))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)

    def ask(self,path,token=None):
        c=http.client.HTTPConnection("127.0.0.1",self.server.server_address[1],timeout=8)
        headers={"Authorization":"Bearer "+token} if token else {}
        c.request("GET",path,headers=headers)
        r=c.getresponse()
        status,head,body=r.status,dict(r.getheaders()),r.read()
        c.close()
        return status,head,body

    def test_static_client_is_unprivileged_no_host_token_embedded(self):
        for path,(mime,body) in ASSETS.items():
            status,head,response=self.ask(path)
            self.assertEqual(status,200,path)
            self.assertEqual(head["Content-Type"],mime)
            self.assertEqual(response,body)
            self.assertEqual(head["Content-Security-Policy"],CSP)
            self.assertEqual(head["X-Content-Type-Options"],"nosniff")
            self.assertEqual(head["Referrer-Policy"],"no-referrer")
            self.assertNotIn(self.token.encode(),response)
        self.assertIn("Film IR",PAGE)
        self.assertIn("no-store",SCRIPT)
        self.assertNotIn("localStorage",SCRIPT)
        self.assertNotIn("sessionStorage",SCRIPT)
        self.assertNotIn("innerHTML",SCRIPT)
        self.assertNotIn("eval(",SCRIPT)

    def test_original_api_never_public_from_browser_shell(self):
        status,head,_=self.ask("/v1/jobs")
        self.assertEqual(status,401)
        self.assertNotIn("Access-Control-Allow-Origin",head)
        status,_,_=self.ask("/v1/health",token="wrong")
        self.assertEqual(status,401)
        status,_,response=self.ask("/v1/health",token=self.token)
        self.assertEqual(status,200)
        self.assertIn(b"zx7-local-body",response)

    def test_only_registered_shell_routes_are_unprotected(self):
        for uri in ["/", "/studio/unknown","/studio.js/../v1/jobs","/v1/tools"]:
            code,_,_=self.ask(uri)
            self.assertEqual(code,401,uri)

if __name__=="__main__":
    unittest.main()
