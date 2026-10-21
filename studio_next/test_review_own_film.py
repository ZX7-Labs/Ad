import unittest
from studio_next.review_own_film import coverage_from_actual_edit


class WholeFilmVisualCoverageTests(unittest.TestCase):
    def test_not_a_fixed_scene_count_or_movie_length(self):
        for n in (1,4,8,19,151):
            shots=[{"id":"s"+str(i),"actual_media_seconds":2.5+i*.1}
                   for i in range(n)]
            total=sum(x["actual_media_seconds"] for x in shots)
            coverage=coverage_from_actual_edit(shots,total)
            self.assertEqual(coverage["scene_count"],n)
            self.assertEqual(coverage["frame_evidence_count"],n*2)
            labels=[point["scene_id"] for batch in coverage["batches"] for point in batch]
            self.assertEqual(set(labels),set(x["id"] for x in shots))
            self.assertEqual(labels[0],"s0")
            self.assertEqual(labels[-1],"s"+str(n-1))
            self.assertEqual(len(coverage["batches"]), (n*2+5)//6)

    def test_verified_movie_duration_not_fabricated(self):
        shots=[{"id":"one","actual_media_seconds":2.0},
               {"id":"two","actual_media_seconds":3.0}]
        with self.assertRaisesRegex(ValueError,"differ from actual encoded"):
            coverage_from_actual_edit(shots,10.0)
        with self.assertRaisesRegex(ValueError,"actual rendered media"):
            coverage_from_actual_edit([{"id":"s","actual_media_seconds":0}],1.0)

    def test_split_long_movies_no_scene_disappears(self):
        shots=[{"id":str(i),"actual_media_seconds":60.0} for i in range(80)]
        samples=coverage_from_actual_edit(shots,4800.0,frames_per_shot=3,
                                          model_batch_limit=6)
        self.assertEqual(len(samples["batches"]),40)
        for batch in samples["batches"]:
            for frame in batch:
                self.assertGreaterEqual(frame["timestamp_seconds"],0)
                self.assertLess(frame["timestamp_seconds"],4800.)

    def test_reject_duplicate_scene_id_and_invalid_model_capacity(self):
        x=[{"id":"a","actual_media_seconds":1.0},
           {"id":"a","actual_media_seconds":1.0}]
        with self.assertRaisesRegex(ValueError,"duplicated"):
            coverage_from_actual_edit(x,2)
        with self.assertRaisesRegex(ValueError,"capacity"):
            coverage_from_actual_edit([x[0]],1,model_batch_limit=1)


if __name__=="__main__":
    unittest.main()
