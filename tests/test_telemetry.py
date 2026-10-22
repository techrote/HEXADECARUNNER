import unittest
from scripts.telemetry import summarize


class TelemetryTests(unittest.TestCase):
    def test_scope_missing_queue_and_incomplete_snapshot(self):
        run = {'id': 12, 'status': 'in_progress', 'head_sha': 'abc'}
        job = {'id': 1, 'name': 'distributed / hex / worker-0', 'status': 'completed',
               'conclusion': 'success', 'started_at': '2026-01-01T00:00:00Z',
               'completed_at': '2026-01-01T00:01:01Z', 'steps': [
                   {'name': 'Compute', 'started_at': '2026-01-01T00:00:10Z', 'completed_at': '2026-01-01T00:00:40Z'},
                   {'name': 'Upload checkpoints', 'started_at': '2026-01-01T00:00:40Z', 'completed_at': '2026-01-01T00:00:45Z'}]}
        pending = {**job, 'id': 2, 'name': 'distributed / hex / aggregate', 'status': 'in_progress', 'completed_at': None, 'steps': []}
        foreign = {**job, 'id': 3, 'name': 'distributed / other / worker-0'}
        report = summarize(run, [job, pending, foreign], 'hex')
        self.assertEqual(len(report['jobs']), 2)
        self.assertAlmostEqual(report['completed_job_runner_minutes'], 61 / 60)
        self.assertEqual(report['completed_job_rounded_minute_estimate'], 2)
        self.assertFalse(report['all_selected_jobs_completed'])
        self.assertIsNone(report['jobs'][0]['queue_seconds'])
        self.assertEqual(report['jobs'][0]['setup_to_compute_seconds'], 10)
        self.assertEqual(report['jobs'][0]['artifact_upload_step_seconds'], 5)


if __name__ == '__main__':
    unittest.main()
