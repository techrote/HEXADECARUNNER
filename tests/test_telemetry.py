import unittest
from scripts.telemetry import summarize, elapsed


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


    def test_partial_rerun_deduplicates_untouched_execution(self):
        run = {'id': 12, 'status': 'in_progress', 'head_sha': 'abc'}
        original = {'id': 1, 'run_attempt': 1, 'runner_id': 100,
                    'name': 'distributed / hex / worker-0', 'status': 'completed',
                    'created_at': '2026-01-01T00:00:00Z',
                    'started_at': '2026-01-01T00:00:02Z',
                    'completed_at': '2026-01-01T00:01:02Z', 'steps': []}
        carried = {**original, 'id': 2, 'run_attempt': 2,
                   'created_at': '2026-01-01T00:02:00Z'}
        rerun = {**carried, 'id': 3, 'runner_id': 101,
                 'started_at': '2026-01-01T00:02:02Z',
                 'completed_at': '2026-01-01T00:02:32Z'}
        report = summarize(run, [carried, rerun, original], 'hex')
        self.assertEqual(report['carried_forward_records_ignored'], 1)
        self.assertEqual(len(report['jobs']), 2)
        self.assertEqual(report['completed_job_runner_minutes'], 1.5)
        self.assertEqual(report['jobs'][0]['id'], 1)
        self.assertEqual(report['jobs'][0]['queue_seconds'], 2)
        self.assertIsNone(elapsed('2026-01-01T00:02:00Z', '2026-01-01T00:00:02Z'))

if __name__ == '__main__':
    unittest.main()
