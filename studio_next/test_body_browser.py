"""Real Chromium mobile-viewport acceptance for BODY operator and host-only API.

This is an actual browser+HTTP integration test, NOT a simulated Android
hardware test, NOT evidence of HTTPS remote availability and NOT creative
render quality validation. The local BODY graph is real; an intentionally
incomplete creative plan is properly BLOCKED rather than fabricated as a film.
"""
from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

from studio_next.body_service import LocalBodyCoordinator, make_body_http_handler


class RealMobileBrowserAcceptance(unittest.TestCase):
    def test_browser_owner_media_job_tools_and_one_use_exact_download(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest("Browser acceptance runs separately with actual Chromium")
        token="only-for-headless-local-console-proof-48bytes-long"
        with tempfile.TemporaryDirectory() as home:
            base=Path(home)
            sound=base/"real-original-sound.wav"
            with wave.open(str(sound),"wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00"*16000)
            original=sound.read_bytes()
            coordinator=LocalBodyCoordinator(base/"runtime")
            server=ThreadingHTTPServer(
                ("127.0.0.1",0),make_body_http_handler(coordinator,token))
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            endpoint="http://127.0.0.1:"+str(server.server_port)
            try:
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True)
                    context=browser.new_context(
                        viewport={"width":375,"height":812},
                        device_scale_factor=2,is_mobile=True,has_touch=True)
                    page=context.new_page()
                    page.goto(endpoint+"/studio",wait_until="networkidle")
                    self.assertIn("ZX7",page.title())
                    self.assertTrue(page.locator("#submit").is_disabled())
                    self.assertEqual(page.locator("#token").input_value(),"")
                    self.assertNotIn("localStorage",page.locator("body").inner_text())

                    # Invalid auth cannot enable owner operations.
                    page.locator("#token").fill("wrong-but-long-enough-token-"+"x"*32)
                    page.locator("#connect").click()
                    page.locator("#status").get_by_text(
                        "Local production service requires host authorization").wait_for()
                    self.assertTrue(page.locator("#upload").is_disabled())
                    self.assertEqual(page.locator("#token").input_value(),"")
                    page.locator("#token").fill(token)
                    page.locator("#connect").click()
                    page.locator("#status").get_by_text("Connected",exact=False).wait_for()
                    self.assertFalse(page.locator("#upload").is_disabled())
                    self.assertFalse(page.locator("#jobs-button").is_disabled())
                    page.locator("#tools .entry").first.wait_for(timeout=15000)
                    self.assertGreater(len(page.locator("#tools").inner_text()),15)
                    page.locator("#resources").get_by_text("Free host disk",exact=False).wait_for()
                    self.assertIn("GPU hardware is NOT evidence",page.locator("#resources").inner_text())

                    page.locator("#asset-space").fill("original_recovery")
                    page.locator("#source").fill("operator-camera-sound-01")
                    page.locator("#rights").fill("Original sound authored by owner for local audit")
                    page.locator("#asset").set_input_files(str(sound))
                    page.locator("#upload").click()
                    page.locator("#upload-status").get_by_text(
                        "verified_real_media_bytes",exact=False).wait_for(timeout=20000)
                    media_receipt=json.loads(page.locator("#upload-status").inner_text())
                    self.assertEqual(media_receipt["bytes"],len(original))
                    self.assertTrue((base/"runtime/projects/original_recovery"/sound.name).is_file())

                    # Submit original Film IR; no model invents missing footage.
                    plan={"project":{"creative_intent":"Owner's non-synthetic browser proof"},
                          "shots":[{"id":"take_a",
                                    "purpose":"Authentic owner media provenance",
                                    "duration_seconds":1}],
                          "tool_graph":[]}
                    authored=base/"original_film_ir.json"
                    authored.write_text(json.dumps(plan),encoding="utf-8")
                    page.locator("#workspace").fill("original_recovery")
                    page.locator("#film").set_input_files(str(authored))
                    page.locator("#submit").click()
                    page.locator("#submit-status").get_by_text("job_id",exact=False).wait_for()
                    job=json.loads(page.locator("#submit-status").inner_text())["job_id"]
                    self.assertTrue(job)
                    page.locator("#jobs-button").click()
                    page.locator("#jobs").get_by_text(job,exact=False).first.wait_for()
                    row=page.locator("#jobs .entry").filter(has_text=job).first
                    row.get_by_role("button",name="artifacts").click()
                    page.locator("#jobs").get_by_text(sound.name,exact=False).wait_for()
                    page.get_by_role("button",name="Authorize download").first.click()
                    anchor=page.get_by_role("link",name="Download now",exact=False).first
                    anchor.wait_for()
                    ticket=anchor.get_attribute("href")
                    self.assertTrue(ticket.startswith("/v1/download/"))
                    client=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=15)
                    client.request("GET",ticket)
                    response=client.getresponse()
                    self.assertEqual(response.status,200)
                    received=response.read()
                    self.assertEqual(received,original)
                    self.assertEqual(len(received),media_receipt["bytes"])
                    client.close()
                    client=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
                    client.request("GET",ticket)
                    denied=client.getresponse()
                    self.assertEqual(denied.status,404)
                    denied.read()
                    client.close()

                    # Real operator revision preview: changing shot B cannot
                    # recompute the independently authored and proved shot A.
                    original_ir={"project":{"creative_intent":"Original art"},
                       "shots":[
                        {"id":"a","purpose":"Owned visual scene one","duration_seconds":2.0},
                        {"id":"b","purpose":"Owned visual scene two","duration_seconds":3.0}],
                       "tool_graph":[
                        {"id":"first","tool_id":"body.vector_png","purpose":"Draw A",
                          "shot_refs":["a"],"inputs":{"source_svg":"a.svg"},
                          "depends_on":[]},
                        {"id":"second","tool_id":"body.vector_png","purpose":"Draw B",
                          "shot_refs":["b"],"inputs":{"source_svg":"b.svg"},
                          "depends_on":[]},
                        {"id":"finish","tool_id":"body.render_edit","purpose":"Join cinema",
                          "depends_on":["first","second"],"inputs":{"edit":"film.json"}}]}
                    revised=json.loads(json.dumps(original_ir))
                    revised["shots"][1]["duration_seconds"]=6.0
                    before=base/"before-artist.json"
                    after=base/"after-artist.json"
                    before.write_text(json.dumps(original_ir),encoding="utf-8")
                    after.write_text(json.dumps(revised),encoding="utf-8")
                    page.locator("#before-film").set_input_files(str(before))
                    page.locator("#after-film").set_input_files(str(after))
                    page.locator("#impact-button").click()
                    page.locator("#impact").get_by_text("Candidate unaffected stages:",exact=False).wait_for()
                    self.assertIn("first",page.locator("#impact").inner_text())
                    self.assertIn("second, finish",page.locator("#impact").inner_text())
                    self.assertIn("reverified at runtime",page.locator("#impact").inner_text())

                    # Mobile UI must remain one-column without horizontal scroll.
                    is_fitted=page.evaluate("""() =>
                        document.documentElement.scrollWidth <= window.innerWidth + 1
                    """)
                    self.assertTrue(is_fitted,"Mobile UI overflows 375px viewport")
                    self.assertEqual(page.locator("#token").input_value(),"")
                    out=Path(os.getenv("ZX7_BROWSER_QA_PNG",
                                     str(base/"mobile-browser-proof.png")))
                    out.parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(out),full_page=True)
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=4)
                coordinator.close()


if __name__=="__main__":
    unittest.main()
