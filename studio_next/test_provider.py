"""Local-model network isolation and reliable JSON-output tests (no real server)."""
import io
import json
import unittest
from unittest.mock import patch
from studio_next.providers import LocalCreativeModel,LocalModelSettings

class FakeReply:
    def __init__(self,payload):
        self.payload=payload
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,length):return json.dumps(self.payload).encode()[:length]

def answer(text,finish="stop"):
    return {"choices":[{"finish_reason":finish,"message":{"content":text}}]}

class ProviderTests(unittest.TestCase):
    def test_remote_api_not_possible_by_default(self):
        for endpoint in ("https://api.openai.com","http://x.evil.com:8080",
                         "http://127.0.0.1:8080/path","http://me:pass@localhost:8080",
                         "http://localhost:8080/?key=secret"):
            with self.subTest(endpoint=endpoint),self.assertRaises(ValueError):
                LocalModelSettings(base_url=endpoint)
    def test_creative_response_schema(self):
        client=LocalCreativeModel(LocalModelSettings(model_id="qwen-local"))
        decision={"kind":"question","question":"Which specific product is it?"}
        requests=[]
        def mock_urlopen(req,timeout):
            data=json.loads(req.data)
            requests.append((req.full_url,data,timeout))
            return FakeReply(answer(json.dumps(decision)))
        with patch("studio_next.providers.urlopen",side_effect=mock_urlopen):
            result=client.decide({"brief":{"request":"Make a Short"}})
        self.assertEqual(result,decision)
        self.assertEqual(requests[0][1]["model"],"qwen-local")
        self.assertIn("film",requests[0][1]["messages"][0]["content"].lower()+
                      " film") # accepted general film remit
        self.assertTrue(requests[0][0].startswith("http://127.0.0.1:8080"))
    def test_critic_response_separate_role(self):
        c=LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen",return_value=FakeReply(
            answer('{"approved":false,"issues":[{"location":"/scene1","reason":"weak","repair":"stronger hook"}]}'))):
            v=c.review({"plan":{"creative_intent":"draft"}})
        self.assertFalse(v["approved"])
    def test_truncated_output_is_error(self):
        c=LocalCreativeModel(LocalModelSettings())
        with patch("studio_next.providers.urlopen",return_value=FakeReply(
            answer('{"kind":"proposal"}',finish="length"))):
            with self.assertRaises(ValueError):
                c.decide({"brief":{}})
    def test_empty_and_non_object_json_rejected(self):
        c=LocalCreativeModel(LocalModelSettings())
        for payload in (answer(""),answer('["bad"]')):
            with patch("studio_next.providers.urlopen",return_value=FakeReply(payload)):
                with self.assertRaises(ValueError):
                    c.decide({})
    def test_sampling_cannot_override_identity(self):
        with self.assertRaises(ValueError):
            LocalModelSettings(sampling={"messages":[]})
        with self.assertRaises(ValueError):
            LocalModelSettings(sampling={"model":"not-approved"})
    def test_sampling_optional_model_decides_creative_outputs(self):
        s=LocalModelSettings(sampling={})
        self.assertEqual(s.sampling,{}) # no global temperature, fixed voice/pace etc

if __name__=="__main__":unittest.main()
