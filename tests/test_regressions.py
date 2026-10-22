"""Regression gates found during real hosted qualification and readback."""
import copy
from pathlib import Path
import tempfile
import unittest

import hexrunner as h


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, workers=4, **kwargs):
        return h.build_manifest(workers=workers, count=32, cells=4, steps=3, processes=1, **kwargs)

    def complete(self, manifest, name="input"):
        root = self.root / name
        h.run_worker(manifest, index=0, baseline=True, output=root / "baseline")
        for index in range(manifest["workers"]):
            h.run_worker(manifest, index=index, output=root / str(index))
        return root

    def test_upstream_failure_cannot_reuse_old_success(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        for status in ("failure", "cancelled", "skipped"):
            with self.assertRaisesRegex(ValueError, "upstream worker"):
                h.reduce_results(manifest, root, upstream_workers=status)
            with self.assertRaisesRegex(ValueError, "upstream baseline"):
                h.reduce_results(manifest, root, upstream_baseline=status)

    def test_empty_restore_is_not_silently_fresh(self):
        cache = self.root / "cache"
        cache.mkdir()
        with self.assertRaisesRegex(ValueError, "no published checkpoints"):
            h.run_worker(self.manifest(), index=0, output=self.root / "out", resume=cache)

    def test_foreign_summary_without_receipts_rejected(self):
        manifest = self.manifest()
        cache = self.root / "cache"
        h.atomic_json(cache / "worker.json", {"schema": 1, "experiment_id": "foreign",
                                              "role": "worker", "index": 0})
        with self.assertRaisesRegex(ValueError, "summary identity"):
            h.run_worker(manifest, index=0, output=self.root / "out", resume=cache)

    def test_old_duplicate_attempt_after_new_attempt_rejected(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        old = h.read_json(root / "0/worker.json")
        h.run_worker(manifest, index=0, output=root / "new", run_attempt=2)
        h.atomic_json(root / "zz-duplicate/worker.json", old)
        with self.assertRaisesRegex(ValueError, "duplicate worker"):
            h.reduce_results(manifest, root)

    def test_rerun_without_restore_excluded_from_performance(self):
        manifest = self.manifest(1)
        root = self.complete(manifest)
        h.run_worker(manifest, index=0, output=root / "new", run_attempt=2)
        report = h.reduce_results(manifest, root)
        self.assertTrue(report["baseline_equal"])
        self.assertFalse(report["performance_eligible"])
        self.assertIn("workflow rerun: not a fresh single-attempt trial", report["performance_exclusions"])


if __name__ == "__main__":
    unittest.main()
