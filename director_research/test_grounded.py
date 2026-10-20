import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from director_research.contracts import audit_bundle, evidence, schedule, schema_errors, BUNDLE
from director_research.grounded import run, re_review, LocalClient
from director_research.reviewing import review_passes, audit_review
from director_research.test_benchmark import BRIEF, CONCEPT, scenes


def proposal(count=5):
    items = scenes()['clips']
    items = [copy.deepcopy(items[i % len(items)]) for i in range(count)]
    for item in items:
        item.update(seconds=24/count, narration='Keep an idea close.', representation='metaphor',
                    fact_ids=['fact_2'], capabilities=['vector_shapes', 'layered_transform'])
    items[0]['role'] = 'hook'
    items[-1].update(role='cta', on_screen=BRIEF['cta'])
    return {'creative': {k: CONCEPT[k] for k in
                        ('concept', 'audience_insight', 'hook', 'visual_motif')} |
                       {'why_this_concept': 'A clear space relates to organising ideas.'},
            'design': {k: CONCEPT[k] for k in
                       ('palette', 'typography', 'camera_language', 'lighting', 'use_3d',
                        'music', 'sound_design', 'voice', 'voice_direction')},
            'scenes': {'clips': items}}


GOOD_REVIEW = dict(approved=True, score_out_of_10=8, factual_support=True,
                   execution_realistic=True, strongest_moment='The final note stays in focus.',
                   findings=[])


class GroundedTests(unittest.TestCase):
    def check(self, bundle):
        return audit_bundle(bundle, BRIEF, evidence(BRIEF))

    def test_variable_shot_count_and_no_render_claim(self):
        for count in (3, 5, 7, 10):
            with self.subTest(count=count):
                qa = self.check(proposal(count))
                self.assertTrue(qa['passed'], qa)
                self.assertFalse(qa['render_ready'])
                self.assertFalse(qa['verified_claims'])

    def test_shape_not_silently_coerced(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['technique'] = '2.5d liquid simulation'
        self.assertFalse(self.check(bundle)['passed'])

    def test_caption_contract_rejects_staging_paragraph(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['on_screen'] = (
            'Close-up of a textured paper surface with a thin shaky line representing an idea.')
        self.assertTrue(schema_errors(bundle, BUNDLE))
        bundle['scenes']['clips'][0]['on_screen'] = 'KEEP THE NEXT IDEA'
        self.assertFalse(schema_errors(bundle, BUNDLE))

    def test_unavailable_effect_inside_motion_is_blocked(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['motion'] = 'Use fluid simulation to animate water'
        self.assertIn('unavailable production technique', str(self.check(bundle)))

    def test_excluding_an_effect_is_not_requesting_it(self):
        bundle = proposal()
        bundle['design']['use_3d'] = 'No photorealistic 3D; use simple layered shapes instead.'
        self.assertTrue(self.check(bundle)['passed'])
        bundle['scenes']['clips'][0]['light'] = 'Use volumetric light after the cut.'
        self.assertIn('unavailable production technique', str(self.check(bundle)))

    def test_ui_in_concept_is_blocked_even_with_clean_narration(self):
        bundle = proposal()
        bundle['creative']['concept'] = 'Click the Organize button and notes align'
        self.assertIn('unprovided product UI', str(self.check(bundle)))

    def test_audience_pause_button_metaphor_is_not_product_ui(self):
        bundle = proposal()
        bundle['creative']['audience_insight'] = 'Teams crave a pause button rather than a rigid cage.'
        self.assertTrue(self.check(bundle)['passed'])
        bundle['scenes']['clips'][0]['composition'] = 'Show the Organize button in the product dashboard.'
        self.assertIn('unprovided product UI', str(self.check(bundle)))

    def test_symbolic_label_does_not_waive_visual_promises(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['composition'] = 'A symbolic badge reading 100% guaranteed'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_audio_click_is_not_a_product_automation_claim(self):
        bundle = proposal()
        bundle['design']['sound_design'] = 'One click on alignment'
        self.assertTrue(self.check(bundle)['passed'])
        bundle['scenes']['clips'][0]['narration'] = 'Organize ideas in one click.'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_animation_scale_is_not_a_performance_promise(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['composition'] = 'A note at 80% scale; opacity: 100%'
        self.assertTrue(self.check(bundle)['passed'])
        bundle['scenes']['clips'][0]['on_screen'] = '100% BETTER'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_visible_badge_promise_is_still_blocked(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['composition'] = 'A scaled note with a badge reading 100% better'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_instantaneous_edits_are_not_product_promises(self):
        bundle = proposal()
        bundle['creative']['visual_motif'] = 'A waveform that instantly cuts to a flat white void.'
        bundle['scenes']['clips'][0]['composition'] = 'The line freezes instantly beside a paper outline.'
        self.assertTrue(self.check(bundle)['passed'])
        bundle['scenes']['clips'][0]['narration'] = 'NOVA instantly organizes ideas.'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_instant_feature_claim_in_concept_still_blocked(self):
        bundle = proposal()
        bundle['creative']['concept'] = 'The product instantly solves every problem.'
        self.assertIn('unsupported promise', str(self.check(bundle)))

    def test_invented_evidence_is_blocked(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['fact_ids'] = ['fact_999']
        self.assertIn('invented evidence', str(self.check(bundle)))

    def test_missing_source_is_not_automatically_added(self):
        bundle = proposal()
        bundle['scenes']['clips'][0]['fact_ids'] = []
        self.assertFalse(self.check(bundle)['passed'])

    def test_missing_cta_is_blocked(self):
        bundle = proposal()
        bundle['scenes']['clips'][-1]['on_screen'] = 'SOMETHING ELSE'
        self.assertIn('CTA', str(self.check(bundle)))

    def test_schema_rejects_fake_capability_and_boolean_timing(self):
        bundle = proposal()
        bundle['scenes']['clips'][0].update(capabilities=['fluid_solver'], seconds=True)
        self.assertGreaterEqual(len(schema_errors(bundle, BUNDLE)), 2)

    def test_invalid_duration_cannot_enter_evidence(self):
        for target in (True, float('nan'), 0, 91, '24'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                evidence(dict(BRIEF, duration_seconds=target))

    def test_timing_preserves_directors_relative_rhythm_and_words(self):
        shots = proposal(3)['scenes']
        for shot, seconds in zip(shots['clips'], (3, 4, 5)):
            shot['seconds'] = seconds
        before = copy.deepcopy(shots)
        fixed = schedule(shots, 24)
        self.assertEqual([s['seconds'] for s in fixed['clips']], [6, 8, 10])
        self.assertEqual(shots, before)
        self.assertEqual([s['narration'] for s in fixed['clips']],
                         [s['narration'] for s in before['clips']])

    def test_rubber_stamp_reviewer_is_not_sufficient(self):
        for changes in ({'score_out_of_10': 7}, {'approved': 'true'},
                        {'factual_support': False}, {'execution_realistic': False},
                        {'findings': [{'category': 'story', 'path': '/missing',
                                       'excerpt': 'fake', 'reason': 'weak', 'repair': 'fix'}]}):
            self.assertFalse(review_passes(dict(GOOD_REVIEW, **changes), proposal()))

    def test_reviewer_cannot_invent_excerpt_or_evidence_location(self):
        bundle = proposal()
        review = dict(GOOD_REVIEW, approved=False, score_out_of_10=6,
                      findings=[dict(category='story', path='/creative/concept',
                                     excerpt='A quote the director never wrote',
                                     reason='Generic metaphor', repair='Use a specific notebook action')])
        self.assertIn('excerpt', str(audit_review(review, bundle)['errors']))
        review['findings'][0]['path'] = '/scenes/clips/999/motion'
        self.assertFalse(audit_review(review, bundle)['passed'])

    def test_review_flags_require_a_corresponding_finding(self):
        self.assertFalse(audit_review(dict(GOOD_REVIEW, approved=False,
                                          factual_support=False), proposal())['passed'])
        self.assertFalse(audit_review(dict(GOOD_REVIEW, approved=False,
                                          execution_realistic=False), proposal())['passed'])

    def test_re_review_preserves_proposal_and_rejects_mismatched_evidence(self):
        class Fake:
            trace = []
            def ask(self, name, prompt, data, schema, tokens):
                self.data = data
                return copy.deepcopy(GOOD_REVIEW)
        bundle = proposal()
        with TemporaryDirectory() as temp:
            source = Path(temp) / 'original.json'
            source.write_text(json.dumps({'state': 'blocked_for_review', 'bundle': bundle,
                                          'evidence': evidence(BRIEF)}))
            before = source.read_bytes()
            out = Path(temp)/'recheck'
            out.mkdir()
            fake = Fake()
            result = re_review(fake, BRIEF, source, out)
            self.assertEqual(result['bundle'], bundle)
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(result['provenance']['proposal_changed'])
            self.assertNotIn('hard_checks', fake.data)
            self.assertFalse(result['render_ready'])
            with self.assertRaises(ValueError):
                re_review(fake, dict(BRIEF, benefit='A different assertion'), source, out)

    def test_hard_gate_cannot_be_overridden_and_repair_is_bounded(self):
        class Fake:
            trace = []
            calls = []
            def ask(self, name, *args):
                self.calls.append(name)
                bundle = proposal()
                bundle['scenes']['clips'][0]['motion'] = 'fluid simulation'
                return (bundle['creative'] if name == 'concept' else
                        bundle['design'] if name == 'art_direction' else
                        bundle['scenes'] if name == 'shots' else
                        copy.deepcopy(GOOD_REVIEW) if name.startswith('critic') else bundle)
        fake = Fake()
        with TemporaryDirectory() as temp:
            result = run(fake, BRIEF, temp)
            self.assertEqual(result['state'], 'blocked_for_review')
            self.assertEqual(len(result['attempts']), 2)
            self.assertEqual(sum(n.startswith('repair') for n in fake.calls), 1)
            self.assertTrue((Path(temp)/'draft_0.json').is_file())
            self.assertFalse(result['human_quality_approved'])

    def test_complete_draft_survives_reviewer_crash(self):
        class Fake:
            trace = []
            def ask(self, name, *args):
                bundle = proposal()
                if name.startswith('critic'):
                    raise TimeoutError('reviewer timed out')
                return bundle[{'concept': 'creative', 'art_direction': 'design', 'shots': 'scenes'}[name]]
        with TemporaryDirectory() as temp:
            with self.assertRaises(TimeoutError):
                run(Fake(), BRIEF, temp)
            draft = json.loads((Path(temp)/'draft_0.json').read_text())
            self.assertEqual(draft['state'], 'unreviewed_draft')
            self.assertEqual(len(draft['bundle']['scenes']['clips']), 5)

    def test_invalid_review_cannot_trigger_a_plan_rewrite(self):
        class Fake:
            trace = []
            calls = []
            def ask(self, name, *args):
                self.calls.append(name)
                bundle = proposal()
                if name.startswith('critic'):
                    return dict(GOOD_REVIEW, approved=False, factual_support=False)
                return bundle[{'concept': 'creative', 'art_direction': 'design', 'shots': 'scenes'}[name]]
        with TemporaryDirectory() as temp:
            fake = Fake()
            result = run(fake, BRIEF, temp)
            self.assertEqual(result['block_reason'], 'invalid_review')
            self.assertFalse(any(name.startswith('repair') for name in fake.calls))

    def test_remote_paid_endpoint_cannot_be_selected(self):
        with TemporaryDirectory() as temp, self.assertRaises(ValueError):
            LocalClient('https://example.com/api', temp)


if __name__ == '__main__':
    unittest.main()
