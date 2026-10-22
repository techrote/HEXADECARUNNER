"""Fast functional qualification. Local workers are NOT physical GitHub nodes."""
import copy
from pathlib import Path
import tempfile
import unittest

import hexrunner as h


class RunnerTests(unittest.TestCase):
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

    def test_all_supported_partition_counts(self):
        for count in h.WORKER_COUNTS:
            with self.subTest(workers=count):
                manifest = self.manifest(count)
                partitions = [h.assigned(manifest, i) for i in range(count)]
                ids = [task["id"] for part in partitions for task in part]
                self.assertEqual(len(ids), 32)
                self.assertEqual(len(set(ids)), 32)
                shuffled = copy.deepcopy(manifest)
                shuffled["tasks"].reverse()
                self.assertEqual(partitions, [h.assigned(shuffled, i) for i in range(count)])
                self.assertLessEqual(max(map(len, partitions)) - min(map(len, partitions)), 1)

    def test_execution_all_supported_counts(self):
        digests = []
        for count in h.WORKER_COUNTS:
            manifest = self.manifest(count)
            root = self.complete(manifest, f"workers-{count}")
            report = h.reduce_results(manifest, root)
            self.assertTrue(report["baseline_equal"])
            digests.append(report["result_sha256"])
        self.assertEqual(len(set(digests)), 1)

    def test_known_reference_result(self):
        # Independently checked using a nested 4x4 grid and direct neighbor indexing.
        self.assertEqual(h.simulation({"cells": 4, "steps": 1, "seed": 1})["sum"], 491908)

    def test_invalid_workers_and_processes(self):
        for workers in (0, 2, 3, 33, True):
            with self.assertRaises(ValueError):
                self.manifest(workers)
        for processes in (0, 5, True):
            with self.assertRaises(ValueError):
                h.build_manifest(processes=processes)

    def test_invalid_tasks_and_digest(self):
        manifest = self.manifest()
        manifest["workers"] = 8
        with self.assertRaisesRegex(ValueError, "digest"):
            h.validate_manifest(manifest)
        for tasks in ([{"id": "../escape", "payload": {}}],
                      [{"id": "a", "payload": {}}, {"id": "a", "payload": {}}]):
            with self.assertRaises(ValueError):
                h.validate_tasks(tasks)
        with self.assertRaises(ValueError):
            h.build_manifest(workers=32, count=4)

    def test_strict_json(self):
        for text in ('{"a":1,"a":2}', '{"value":NaN}', '{"value":Infinity}'):
            with self.assertRaises(ValueError):
                h.loads(text)

    def test_missing_worker_rejected(self):
        manifest = self.manifest()
        root = self.root / "input"
        h.run_worker(manifest, index=0, baseline=True, output=root / "baseline")
        with self.assertRaisesRegex(ValueError, "missing workers"):
            h.reduce_results(manifest, root)

    def test_missing_extra_and_corrupt_receipts(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        path = next((root / "0").glob("task-*.json"))
        original = h.read_json(path)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "checkpoint files"):
            h.reduce_results(manifest, root)
        h.atomic_json(path, original)
        extra = root / "0" / "task-unknown.json"
        h.atomic_json(extra, original)
        with self.assertRaisesRegex(ValueError, "checkpoint files"):
            h.reduce_results(manifest, root)
        extra.unlink()
        original["result"]["sum"] += 1
        h.atomic_json(path, original)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            h.reduce_results(manifest, root)

    def test_baseline_disagreement_rejected(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        path = next((root / "0").glob("task-*.json"))
        receipt = h.read_json(path)
        receipt["result"]["sum"] += 1
        receipt["result_sha256"] = h.digest(receipt["result"])
        h.atomic_json(path, receipt)
        with self.assertRaisesRegex(ValueError, "differ from"):
            h.reduce_results(manifest, root)

    def test_failure_checkpoints_and_resume(self):
        manifest = self.manifest()
        root = self.root / "input"
        h.run_worker(manifest, index=0, baseline=True, output=root / "baseline")
        failed = h.run_worker(manifest, index=0, output=root / "old", fail_task="t000000")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["computed_tasks"], 7)
        for index in range(1, 4):
            h.run_worker(manifest, index=index, output=root / str(index))
        with self.assertRaisesRegex(ValueError, "failed"):
            h.reduce_results(manifest, root)
        restored = h.run_worker(manifest, index=0, output=root / "new", resume=root / "old", run_attempt=2)
        self.assertEqual(restored["restored_tasks"], 7)
        self.assertEqual(restored["computed_tasks"], 1)
        report = h.reduce_results(manifest, root)
        self.assertTrue(report["baseline_equal"])
        self.assertFalse(report["performance_eligible"])
        self.assertIsNone(report["execution_span_speedup"])

    def test_transient_retry(self):
        manifest = self.manifest()
        root = self.root / "worker"
        result = h.run_worker(manifest, index=0, output=root, fail_task="t000000", fail_once=True)
        self.assertEqual(result["status"], "complete")
        receipt = h.read_json(root / "task-t000000.json")
        self.assertEqual(receipt["attempts"], 2)
        self.assertEqual(len(receipt["retry_errors"]), 1)

    def test_stale_checkpoint_rejected(self):
        manifest = self.manifest()
        old = self.root / "old"
        h.run_worker(manifest, index=0, output=old)
        different = self.manifest(source="different-revision")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            h.run_worker(different, index=0, output=self.root / "new", resume=old)

    def test_conflicting_checkpoints_rejected(self):
        manifest = self.manifest()
        cache = self.root / "cache"
        h.run_worker(manifest, index=0, output=cache / "first")
        receipt = h.read_json(cache / "first/task-t000000.json")
        receipt["result"]["sum"] += 1
        receipt["result_sha256"] = h.digest(receipt["result"])
        h.atomic_json(cache / "second/task-t000000.json", receipt)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            h.run_worker(manifest, index=0, output=self.root / "new", resume=cache)

    def test_duplicate_summary_and_foreign_run_rejected(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        summary = h.read_json(root / "0/worker.json")
        h.atomic_json(root / "duplicate/worker.json", summary)
        with self.assertRaisesRegex(ValueError, "duplicate worker"):
            h.reduce_results(manifest, root)
        (root / "duplicate/worker.json").unlink()
        summary["run_id"] = "some-other-run"
        h.atomic_json(root / "0/worker.json", summary)
        with self.assertRaisesRegex(ValueError, "foreign"):
            h.reduce_results(manifest, root)

    def test_resume_does_not_hide_latest_failure(self):
        manifest = self.manifest()
        root = self.complete(manifest)
        h.run_worker(manifest, index=0, output=root / "new", fail_task="t000000", run_attempt=2)
        with self.assertRaisesRegex(ValueError, "failed"):
            h.reduce_results(manifest, root)

    def test_no_baseline_and_overlap(self):
        manifest = self.manifest(1)
        root = self.root / "input"
        h.run_worker(manifest, index=0, output=root / "0")
        report = h.reduce_results(manifest, root, require_baseline=False)
        self.assertIsNone(report["baseline_equal"])
        self.assertFalse(report["performance_eligible"])
        self.assertEqual(h.overlap([{"started_epoch": 1, "finished_epoch": 3},
                                    {"started_epoch": 2, "finished_epoch": 4}]), 2)
        self.assertEqual(h.overlap([{"started_epoch": 1, "finished_epoch": 2},
                                    {"started_epoch": 2, "finished_epoch": 3}]), 1)

    def test_custom_adapter_and_source_guard(self):
        adapter = self.root / "adapter.py"
        adapter.write_text('import json,sys\nt=json.load(sys.stdin)\njson.dump({"square":t["payload"]["n"]**2},sys.stdout)\n')
        tasks = [{"id": "x", "payload": {"n": 7}}]
        manifest = h.build_manifest(workers=1, processes=1, tasks=tasks, adapter="adapter.py", workdir=self.root)
        out = self.root / "out"
        h.run_worker(manifest, index=0, output=out, workdir=self.root)
        self.assertEqual(h.read_json(out / "task-x.json")["result"], {"square": 49})
        adapter.write_text("raise RuntimeError('changed')\n")
        with self.assertRaisesRegex(ValueError, "source digest"):
            h.run_worker(manifest, index=0, output=self.root / "different", workdir=self.root)
        with self.assertRaises(ValueError):
            h.within(self.root, "../escape.py")

    def test_adapter_timeout_and_invalid_output(self):
        adapter = self.root / "adapter.py"
        adapter.write_text("import time\ntime.sleep(5)\n")
        with self.assertRaisesRegex(RuntimeError, "exceeded"):
            h.invoke_adapter(str(adapter), {"id": "x", "payload": {}}, str(self.root), 1)
        adapter.write_text("print('not-json')\n")
        with self.assertRaises(ValueError):
            h.invoke_adapter(str(adapter), {}, str(self.root), 1)

    def test_output_reuse_refused(self):
        manifest = self.manifest()
        output = self.root / "out"
        h.run_worker(manifest, index=0, output=output)
        with self.assertRaisesRegex(ValueError, "fresh"):
            h.run_worker(manifest, index=0, output=output)

    def test_atomic_writer(self):
        path = self.root / "nested/value.json"
        h.atomic_json(path, {"value": 1})
        self.assertEqual(h.read_json(path), {"value": 1})
        self.assertFalse(list(path.parent.glob(".pending-*")))


if __name__ == "__main__":
    unittest.main()
