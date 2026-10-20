import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from director_research.contracts import audit_bundle, evidence, review_passes, schedule, schema_errors, BUNDLE
from director_research.grounded import run, LocalClient
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
                   problems=[], recommended_repairs=[])


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

    def test_ui_in_concept_is_blocked_even_with_clean_narration(self):
        bundle = proposal()
        bundle['creative']['concept'] = 'Click the Organize button and notes align'
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
                        {'problems': ['Unresolved issue']}):
            self.assertFalse(review_passes(dict(GOOD_REVIEW, **changes)))

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

    def test_remote_paid_endpoint_cannot_be_selected(self):
        with TemporaryDirectory() as temp, self.assertRaises(ValueError):
            LocalClient('https://example.com/api', temp)


if __name__ == '__main__':
    unittest.main()
