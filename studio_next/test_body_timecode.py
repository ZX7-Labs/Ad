"""Independent algorithmic boundaries for source-exact editorial SMPTE labels.

These tests prove clock labeling, not claimed artistic quality or video
decoding. Physical video/audio evidence is verified by separate BODY tools.
"""
import random
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from studio_next.body_timecode import (
    _rate,format_timecode,parse_timecode,
    frame_timecode_receipt,parse_timecode_receipt,verify_timecode_receipt)


class ExactSourceTimecodeTests(unittest.TestCase):
    def test_ntsc_2997_skip_labels_not_frames_or_picture_source_time(self):
        rate=(30000,1001)
        known={
            0:"00:00:00;00",1:"00:00:00;01",
            1798:"00:00:59;28",1799:"00:00:59;29",
            1800:"00:01:00;02",1801:"00:01:00;03",
            17982:"00:10:00;00",107892:"01:00:00;00",
            2589407:"23:59:59;29"}
        for index,label in known.items():
            with self.subTest(source_frame=index):
                self.assertEqual(format_timecode(index,*rate,drop_frame=True),label)
                self.assertEqual(parse_timecode(label,*rate),(index,True))
        for label in ("00:01:00;00","00:01:00;01",
                      "01:19:00;00","23:59:00;01"):
            with self.subTest(omitted=label),self.assertRaisesRegex(
                    ValueError,"no physically existing source frame"):
                parse_timecode(label,*rate)
        for label in ("00:00:00;00","00:10:00;00","01:00:00;01"):
            self.assertGreaterEqual(parse_timecode(label,*rate)[0],0)
        receipt=frame_timecode_receipt(1800,*rate,True)
        self.assertEqual(receipt["timecode_label"],"00:01:00;02")
        self.assertEqual(Fraction(receipt["physical_elapsed_seconds_numerator"],
                                  receipt["physical_elapsed_seconds_denominator"]),
                         Fraction(1800*1001,30000))
        self.assertEqual(receipt["actual_picture_frames_removed"],0)
        self.assertFalse(receipt["artistic_or_delivery_quality_certified"])

    def test_ntsc_5994_skip_four_labels_per_non_tenth_minute(self):
        rate=(60000,1001)
        known={
            0:"00:00:00;00",3599:"00:00:59;59",
            3600:"00:01:00;04",35964:"00:10:00;00",
            215784:"01:00:00;00",5178815:"23:59:59;59"}
        for frame,label in known.items():
            with self.subTest(frame=frame):
                self.assertEqual(format_timecode(frame,*rate,drop_frame=True),label)
                self.assertEqual(parse_timecode(label,*rate),(frame,True))
        for missing in ("00:01:00;00","00:01:00;01",
                        "00:01:00;02","00:01:00;03"):
            with self.assertRaises(ValueError):
                parse_timecode(missing,*rate)
        self.assertEqual(parse_timecode("00:10:00;00",*rate),
                         (35964,True))

    def test_fractional_nondrop_remains_a_frame_label_not_false_wall_time(self):
        cases=((24,1),(24000,1001),(25,1),(30,1),(30000,1001),
               (50,1),(60000,1001),(60,1))
        for numerator,denominator in cases:
            _,nominal,_,limit=_rate(numerator,denominator,False)
            for frame in (0,1,nominal-1,nominal,nominal*60-1,limit-1):
                with self.subTest(rate=(numerator,denominator),frame=frame):
                    label=format_timecode(frame,numerator,denominator)
                    self.assertEqual(parse_timecode(
                        label,numerator,denominator),(frame,False))
                    self.assertEqual(label[8],":")
        real=frame_timecode_receipt(24,24000,1001,False)
        self.assertEqual(real["timecode_label"],"00:00:01:00")
        self.assertEqual(Fraction(real["physical_elapsed_seconds_numerator"],
                                  real["physical_elapsed_seconds_denominator"]),
                         Fraction(1001,1000))

    def test_every_one_of_1440_minutes_omits_exactly_standard_labels(self):
        for numerator,nominal,skipped in ((30000,30,2),(60000,60,4)):
            for hour in range(24):
                for minute in range(60):
                    at=f"{hour:02d}:{minute:02d}:00;"
                    if minute%10==0:
                        self.assertEqual(parse_timecode(at+"00",
                            numerator,1001)[1],True)
                    else:
                        for impossible in range(skipped):
                            with self.assertRaises(ValueError):
                                parse_timecode(at+f"{impossible:02d}",
                                               numerator,1001)
                        label=at+f"{skipped:02d}"
                        physical,drop=parse_timecode(label,numerator,1001)
                        self.assertTrue(drop)
                        self.assertEqual(format_timecode(
                            physical,numerator,1001,drop_frame=True),label)

    def test_randomized_bijection_full_24h_epoch_multiple_rational_rates(self):
        rng=random.Random(0x7A7C0DE)
        accepted=((24000,1001,False),(24,1,False),
                  (25,1,False),(30000,1001,False),
                  (30000,1001,True),(60000,1001,False),
                  (60000,1001,True),(60,1,False))
        for numerator,denominator,drop in accepted:
            _,_,_,limit=_rate(numerator,denominator,drop)
            for _ in range(12000):
                index=rng.randrange(limit)
                label=format_timecode(index,numerator,denominator,
                                      drop_frame=drop)
                restored,policy=parse_timecode(label,numerator,denominator)
                self.assertEqual((restored,policy),(index,drop))
            with self.assertRaisesRegex(ValueError,"one actual frame"):
                format_timecode(limit,numerator,denominator,drop_frame=drop)

    def test_invalid_ambiguity_unsafe_grammar_and_float_rate_never_become_frames(self):
        invalid=("00:01:00;00","00:01:00;01","24:00:00;02",
                 "00:60:00;02","00:00:60;02","00:00:00;30",
                 "00:00:00;XX","0:00:00;00","00:00:00;000",
                 "00:00:00;00\n","-00:00:00;02","00:00:00;02;exec",
                 "٠٠:٠٠:٠٠;٠٢",None,False,13,"")
        for label in invalid:
            with self.subTest(invalid=label),self.assertRaises(ValueError):
                parse_timecode(label,30000,1001)
        for numerator,denominator,drop in (
            (29.97,1,True),(30000,1000,True),
            (24000,1001,True),(60,1,True),
            (0,1,False),(-24,1,False),(24,0,False),
            (1000,1,False),(1,False,False),
            (30000,1001,"true"),(True,1,False)):
            with self.subTest(rate=(numerator,denominator,drop)):
                with self.assertRaises(ValueError):
                    format_timecode(0,numerator,denominator,drop_frame=drop)
        for value in (True,False,0.0,-1,2592000,None):
            with self.subTest(frame=value),self.assertRaises(ValueError):
                format_timecode(value,30000,1001,drop_frame=True)

    def test_immutable_receipt_recomputed_from_source_clock_blocks_fake_proof(self):
        a=frame_timecode_receipt(107892,30000,1001,True)
        b=parse_timecode_receipt(a["timecode_label"],30000,1001)
        self.assertTrue(verify_timecode_receipt(a,"body.timecode_format"))
        self.assertTrue(verify_timecode_receipt(b,"body.timecode_parse"))
        self.assertEqual(b["frame_index"],a["frame_index"])
        for mutator in (
            lambda x:x.update(frame_index=x["frame_index"]+1),
            lambda x:x.update(timecode_label="01:00:00;01"),
            lambda x:x.update(actual_picture_frames_removed=2),
            lambda x:x.update(physical_elapsed_seconds_denominator=1000),
            lambda x:x.update(artistic_or_delivery_quality_certified=True),
            lambda x:x.update(untrusted_shell="pwd"),
        ):
            changed=dict(a)
            mutator(changed)
            self.assertFalse(verify_timecode_receipt(
                changed,"body.timecode_format"))
        self.assertFalse(verify_timecode_receipt(
            dict(b,input_timecode_label="xx"),"body.timecode_parse"))
        self.assertFalse(verify_timecode_receipt(a,"body.fake_timecode"))

    def test_durable_director_graph_revalidates_exact_original_clock_instead_of_fake_cached_proof(self):
        from studio_next.body_integration import body_catalog,run_body_project
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            catalog=body_catalog(root)
            self.assertEqual(catalog.trusted_material_fingerprint(
                "body.timecode_format",{
                    "numerator":30000,"denominator":1001,
                    "frame_index":1800,"drop_frame":True}),[])
            self.assertIn("body.timecode_format",
                          catalog.committed_tool_revisions())
            graph={
                "project":{"creative_intent":
                    "Show exact source-frame clock without modifying owner footage"},
                "assets":[],
                "shots":[{"id":"clock","purpose":
                    "Address owner video frames exactly","duration_seconds":1}],
                "tool_graph":[{"id":"source-clock","tool_id":"body.timecode_format",
                    "purpose":"Author reversible frame-exact timecode label",
                    "inputs":{"numerator":30000,"denominator":1001,
                              "frame_index":1800,"drop_frame":True},
                    "depends_on":[]}]}
            first=run_body_project(graph,root,db_name="smpte-proof.sqlite3")
            self.assertEqual(first["status"],"all_tool_results_verified")
            self.assertEqual(first["reused"],[])
            again=run_body_project(graph,root,db_name="smpte-proof.sqlite3")
            self.assertEqual(again["status"],"all_tool_results_verified")
            self.assertEqual(again["reused"],["source-clock"])
            self.assertEqual(again["completed"],["source-clock"])
            # Changing an *actual* rational frame index changes the trusted
            # durable input key and must invalidate the previous observation.
            changed=__import__("copy").deepcopy(graph)
            changed["tool_graph"][0]["inputs"]["frame_index"]=1801
            third=run_body_project(changed,root,db_name="smpte-proof.sqlite3")
            self.assertEqual(third["status"],"all_tool_results_verified")
            self.assertEqual(third["reused"],[])
            self.assertEqual(third["completed"],["source-clock"])

    def test_actual_registered_read_tools_offer_stable_safe_rational_clocks(self):
        from studio_next.body_integration import body_catalog,validate_witness
        with tempfile.TemporaryDirectory() as tmp:
            owner=body_catalog(Path(tmp))
            tools={entry["id"]:entry for entry in owner.discover()}
            for id in ("body.timecode_format","body.timecode_parse"):
                self.assertIn(id,tools)
                self.assertEqual(tools[id]["status"],"installed")
            formatted=owner.invoke("body.timecode_format",{
                "numerator":30000,"denominator":1001,
                "frame_index":1800,"drop_frame":True},
                allowed_access={"read"})
            self.assertEqual(formatted["timecode_label"],"00:01:00;02")
            self.assertTrue(validate_witness("body.timecode_format",formatted))
            parsed=owner.invoke("body.timecode_parse",{
                "numerator":30000,"denominator":1001,
                "timecode":"00:01:00;02"},allowed_access={"read"})
            self.assertEqual(parsed["frame_index"],1800)
            self.assertTrue(validate_witness("body.timecode_parse",parsed))
            self.assertFalse(validate_witness("body.timecode_parse",
                                             {**parsed,"frame_index":1801}))
            for forged in (
                {"numerator":30000,"denominator":1001,
                 "frame_index":0,"drop_frame":"yes"},
                {"numerator":30000,"denominator":1001,
                 "frame_index":0,"drop_frame":True,"shell":"rm -rf /"},
                {"numerator":30000,"denominator":1001,
                 "frame_index":-1,"drop_frame":True},
            ):
                with self.subTest(forged=forged),self.assertRaises((ValueError,TypeError)):
                    owner.invoke("body.timecode_format",forged,
                                 allowed_access={"read"})


if __name__=="__main__":
    unittest.main()
