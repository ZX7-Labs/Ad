import json
import tempfile
import unittest
from pathlib import Path

from studio_next.execute_film import verified_render_fact_ledger


def scene(refs):
    return {"id":"shot-1","purpose":"An original scene",
            "duration_seconds":9.7,"fact_refs":refs}

def tx(refs):
    return {"title":"Independent art","scenes":[scene(refs)]}


class FilmFactContinuityTests(unittest.TestCase):
    def test_fact_citations_survive_exact_model_to_renderer_handoff(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)
            (folder/"director-translation.json").write_text(json.dumps(tx(["identity"])))
            facts={"request":"Original ad","facts":{"identity":"Paper notebook"}}
            (folder/"owner-factual-brief.json").write_text(json.dumps(facts))
            director,ledger=verified_render_fact_ledger(folder/"director-translation.json")
            self.assertEqual(director["scenes"][0]["fact_refs"],["identity"])
            self.assertEqual(ledger,{"identity":"Paper notebook"})

    def test_fabricated_fact_not_laundered_from_model_output(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)
            (f/"film.json").write_text(json.dumps(tx(["magic_superpower"])))
            (f/"owner-factual-brief.json").write_text(json.dumps(
                {"facts":{"identity":"Ordinary notebook"}}))
            with self.assertRaisesRegex(ValueError,"no verifiable owner source"):
                verified_render_fact_ledger(f/"film.json")

    def test_conflicting_embedded_facts_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)
            wrapper={"treatment":tx(["identity"]),
                     "brief":{"facts":{"identity":"Invented"}}}
            (f/"film.json").write_text(json.dumps(wrapper))
            (f/"original.json").write_text(json.dumps(
                {"facts":{"identity":"Real paper notebook"}}))
            with self.assertRaisesRegex(ValueError,"disagree"):
                verified_render_fact_ledger(f/"film.json",f/"original.json")

    def test_legacy_standalone_film_no_claims_remains_usable(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"film.json"
            p.write_text(json.dumps(tx([])))
            _,ledger=verified_render_fact_ledger(p)
            self.assertEqual(ledger,{})

    def test_model_cannot_cite_missing_owner_source(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/"film.json"
            p.write_text(json.dumps(tx(["identity"])))
            with self.assertRaisesRegex(ValueError,"no verifiable owner source"):
                verified_render_fact_ledger(p)

if __name__=="__main__":
    unittest.main()
