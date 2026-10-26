"""Real two-shot audiovisual non-destructive cinema edit with incremental DAG.

Actual H264/AAC + FFmpeg decoder + rights verified owner footage:
revision one builds real two-shot film, revision two replaces only one source.
The completed unrelated encoded shot and original final film bytes MUST be
retained unchanged, while the revised scene and new final render are decoded.

No creative template is imposed on the studio: these two small colors and
sine wave are solely reproducible physical CI fixtures, never film defaults.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from studio_next.contracts import ToolSpec
from studio_next.durable_graph import DurableFilmGraph,execute_durable_film_graph
from studio_next.media_vault import MediaVault,sha256_file
from studio_next.delivery_audit import _probe_details
from studio_next.registry import ToolCatalog
from studio_next.body_revision_impact import plan_film_revision_impact


def _cmd(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=90)
    if result.returncode!=0:
        raise RuntimeError("Physical original media engine failed: "+
                           result.stderr[-1800:])
    return result


def _fixture(path,color,frequency):
    _cmd(["ffmpeg","-hide_banner","-loglevel","error","-y",
          "-f","lavfi","-i",f"color=c={color}:s=160x90:r=12:d=0.8",
          "-f","lavfi","-i",f"sine=frequency={frequency}:sample_rate=48000:duration=0.8",
          "-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",
          "-shortest",str(path)])


def _cinema(root,vault,witness_a,witness_b,b_name,b_out,film_out):
    return {
      "project":{"creative_intent":"One original two-shot filmed/audio montage"},
      "assets":[
       {"id":"source_a","rights":"owner_supplied","status":"verified",
        "location":"camera-a.mp4","sha256":witness_a["asset_id"]},
       {"id":"source_b","rights":"owner_supplied","status":"verified",
        "location":b_name,"sha256":witness_b["asset_id"]}],
      "shots":[
       {"id":"opening","purpose":"Intimate original picture with sound",
        "duration_seconds":0.8,"asset_refs":["source_a"]},
       {"id":"continuation","purpose":"Second independently filmed original shot",
        "duration_seconds":0.8,"asset_refs":["source_b"]}],
      "tool_graph":[
       {"id":"picture_a","tool_id":"proof.video",
        "purpose":"Edit original picture A and keep original sound",
        "shot_refs":["opening"],"depends_on":[],
        "inputs":{"source":"camera-a.mp4","out":"prepared-a.mp4",
                  "asset_id":witness_a["asset_id"],
                  "attestation_id":witness_a["attestation_id"]}},
       {"id":"picture_b","tool_id":"proof.video",
        "purpose":"Edit original picture B and keep original sound",
        "shot_refs":["continuation"],"depends_on":[],
        "inputs":{"source":b_name,"out":b_out,
                  "asset_id":witness_b["asset_id"],
                  "attestation_id":witness_b["attestation_id"]}},
       {"id":"finish","tool_id":"proof.concat",
        "purpose":"Encode actual two-shot final picture and audio",
        "depends_on":["picture_a","picture_b"],
        "inputs":{"a":{"$node_output":"picture_a"},
                  "b":{"$node_output":"picture_b"},
                  "out":film_out}}
      ]
    }


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Native verified audiovisual editing requires both actual decoders")
class ActualNonDestructiveCinemaRevision(unittest.TestCase):
    def test_physical_original_films_revise_only_affected_picture(self):
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            vault=MediaVault(root/"vault")
            recordings={}
            for source,color,pitch in (
                    ("camera-a.mp4","red",440),
                    ("camera-b.mp4","blue",480),
                    ("camera-b-new.mp4","green",660)):
                path=root/source
                _fixture(path,color,pitch)
                recordings[source]=vault.ingest(
                    path,mime="video/mp4",rights="owner_supplied",
                    source_type="owner_upload",source_id=source,
                    evidence="Original test recording authored for physical native CI",
                    owner_or_generator="owner")
            first=_cinema(root,vault,recordings["camera-a.mp4"],
               recordings["camera-b.mp4"],"camera-b.mp4",
               "prepared-b.mp4","film-first.mp4")
            revised=_cinema(root,vault,recordings["camera-a.mp4"],
               recordings["camera-b-new.mp4"],"camera-b-new.mp4",
               "prepared-b-new.mp4","film-revised.mp4")
            calls=[]
            tools=ToolCatalog()

            def prepare(args):
                vault.inspect(args["asset_id"],attestation_id=args["attestation_id"])
                original=root/args["source"]
                if sha256_file(original)!=args["asset_id"]:
                    raise ValueError("Original physical footage differed from owner custody")
                destination=root/args["out"]
                if destination.exists():
                    raise FileExistsError("Cannot rewrite accepted original movie")
                calls.append(("prepare",args["source"]))
                _cmd(["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                      "-i",str(original),
                      "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
                      "-c:a","aac","-b:a","128k","-movflags","+faststart",
                      str(destination)])
                return {"path":str(destination),"sha256":sha256_file(destination),
                        "bytes":destination.stat().st_size}

            def join(args):
                a,b=args["a"],args["b"]
                output=root/args["out"]
                if output.exists():
                    raise FileExistsError("Do not overwrite previously approved film")
                calls.append(("join",args["out"]))
                _cmd(["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                      "-i",a["path"],"-i",b["path"],
                      "-filter_complex","[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
                      "-map","[v]","-map","[a]","-c:v","libx264",
                      "-pix_fmt","yuv420p","-preset","ultrafast",
                      "-c:a","aac","-b:a","128k","-movflags","+faststart",
                      str(output)])
                return {"path":str(output),"sha256":sha256_file(output),
                        "bytes":output.stat().st_size}

            def verified(tool_id,output):
                try:
                    p=Path(output["path"])
                    if (not p.is_file() or sha256_file(p)!=output["sha256"]
                         or p.stat().st_size!=output["bytes"]):
                        return False
                    facts=_probe_details(p)
                    return facts["audio_stream_present"] and facts["width"]==160
                except (KeyError,OSError,ValueError,TypeError):
                    return False

            tools.register(ToolSpec("proof.video","Original source picture encode",
                           "Actual licensed H264/AAC source edit","write"),prepare)
            tools.register(ToolSpec("proof.concat","Original sound/picture movie",
                           "Actual multishot H264/AAC timeline assembly","write"),join)

            def fingerprint_material(tool,inputs):
                if tool=="proof.video":
                    p=root/inputs["source"]
                    return [{"bytes":p.stat().st_size,
                             "sha256":sha256_file(p),"relative":p.name}]
                return []

            def go(film):
                return execute_durable_film_graph(
                    film,tools,fact_ids=set(),
                    store=DurableFilmGraph(root/"production.sqlite3"),
                    trusted_idempotent_tools={"proof.video","proof.concat"},
                    output_verifier=verified,
                    tool_revisions={"proof.video":"native-ffmpeg-proven-v1",
                                    "proof.concat":"native-ffmpeg-proven-v1"},
                    input_material_fingerprint=fingerprint_material,
                    lease_seconds=6)

            prior=go(first)
            self.assertEqual(prior["status"],"all_tool_results_verified",prior)
            prior_cinema=sha256_file(root/"film-first.mp4")
            unchanged_picture=sha256_file(root/"prepared-a.mp4")
            self.assertEqual(len(calls),3)
            for file in ("prepared-a.mp4","prepared-b.mp4","film-first.mp4"):
                physical=_probe_details(root/file)
                self.assertTrue(physical["audio_stream_present"])
                _cmd(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
                      "-i",str(root/file),"-map","0:v:0","-map","0:a:0","-f","null","-"])

            preview=plan_film_revision_impact(first,revised)
            self.assertEqual(preview["original_unchanged_candidates"],["picture_a"])
            self.assertEqual(preview["new_or_changed_operations"],["picture_b","finish"])
            self.assertFalse(preview["reusable_cached_bytes_proven"])
            after=go(revised)
            self.assertEqual(after["status"],"all_tool_results_verified",after)
            self.assertEqual(after["reused"],["picture_a"])
            self.assertEqual(len(calls),5)
            self.assertEqual(calls[-2:],[
                ("prepare","camera-b-new.mp4"),("join","film-revised.mp4")])
            self.assertEqual(sha256_file(root/"prepared-a.mp4"),unchanged_picture)
            self.assertEqual(sha256_file(root/"film-first.mp4"),prior_cinema)
            self.assertNotEqual(sha256_file(root/"film-first.mp4"),
                                sha256_file(root/"film-revised.mp4"))
            self.assertTrue(_probe_details(root/"film-revised.mp4")["audio_stream_present"])
            _cmd(["ffmpeg","-hide_banner","-loglevel","error","-xerror",
                  "-i",str(root/"film-revised.mp4"),"-map","0:v:0","-map","0:a:0",
                  "-f","null","-"])
            self.assertTrue((root/"prepared-b.mp4").is_file())
            self.assertTrue((root/"prepared-b-new.mp4").is_file())
            # CI can retain both real originals and mastered files for
            # review by a future physical/visual evaluator. These are tiny
            # technical proof fixtures, not an artistic cinematography score.
            preserve=os.getenv("ZX7_INCREMENTAL_CINEMA_PROOF")
            if preserve:
                destination=Path(preserve).resolve()
                destination.mkdir(parents=True,exist_ok=True)
                records=[]
                for filename in ("prepared-a.mp4","prepared-b.mp4",
                                 "prepared-b-new.mp4","film-first.mp4",
                                 "film-revised.mp4"):
                    from_path=root/filename
                    to_path=destination/filename
                    if to_path.exists():
                        raise FileExistsError("Review evidence must not be overwritten")
                    shutil.copyfile(from_path,to_path)
                    meta=_probe_details(to_path)
                    records.append({"file":filename,
                        "sha256":sha256_file(to_path),
                        "bytes":to_path.stat().st_size,
                        "duration_seconds":meta["duration_seconds"],
                        "original_audio_present":meta["audio_stream_present"]})
                (destination/"verified-two-revision-media.json").write_text(
                    json.dumps({"first_master_retained":True,
                                "unrelated_video_stage_reused":True,
                                "originals_decode_with_actual_audio":True,
                                "independent_artistic_quality_certified":False,
                                "real_media":records},indent=2)+"\n",
                    encoding="utf-8")


if __name__=="__main__":
    unittest.main()
