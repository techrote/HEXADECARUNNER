#!/usr/bin/env python3
"""Read-only Actions telemetry. Never equate observed runtime with billed minutes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import urllib.error
import urllib.request


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() if value else None


def elapsed(start, end):
    return max(0.0, timestamp(end) - timestamp(start)) if start and end else None


def summarize(run, jobs, namespace):
    rows = []
    for job in jobs:
        name = job['name']
        # Exact namespace suffix: do not accidentally include another workflow call.
        if not re.search(r'(?:^| / )' + re.escape(namespace) + r' / (?:plan|baseline|worker-\d+|aggregate)$', name):
            continue
        compute = next((s for s in job.get('steps', []) if s['name'] == 'Compute'), None)
        download = upload = 0.0
        for step in job.get('steps', []):
            duration = elapsed(step.get('started_at'), step.get('completed_at')) or 0.0
            if step['name'].startswith(('Download', 'Restore published')):
                download += duration
            if step['name'].startswith('Upload'):
                upload += duration
        rows.append({'name': name, 'id': job['id'], 'status': job['status'],
                     'conclusion': job.get('conclusion'), 'run_attempt': job.get('run_attempt'),
                     'job_seconds': elapsed(job.get('started_at'), job.get('completed_at')),
                     'queue_seconds': elapsed(job.get('created_at'), job.get('started_at')),
                     'setup_to_compute_seconds': elapsed(job.get('started_at'), compute.get('started_at')) if compute else None,
                     'compute_step_seconds': elapsed(compute.get('started_at'), compute.get('completed_at')) if compute else None,
                     'artifact_download_step_seconds': download, 'artifact_upload_step_seconds': upload})
    completed_seconds = sum(row['job_seconds'] or 0 for row in rows)
    return {'schema': 1, 'status': 'available', 'run_id': run['id'], 'run_status': run['status'],
            'run_conclusion': run.get('conclusion'), 'head_sha': run['head_sha'],
            'snapshot_at': datetime.now(timezone.utc).isoformat(), 'namespace': namespace,
            'completed_job_runner_minutes': completed_seconds / 60,
            'completed_job_rounded_minute_estimate': sum(math.ceil((row['job_seconds'] or 0) / 60) for row in rows),
            'all_selected_jobs_completed': bool(rows) and all(row['status'] == 'completed' for row in rows),
            'jobs': rows,
            'notes': ['Snapshot includes all available attempts, not just successful jobs.',
                      'During aggregation, its own duration and final upload are not yet complete.',
                      'Runner minutes are observed job durations; rounded estimate is NOT an invoice.',
                      'Artifact timings include action startup, compression and transfer, not just network.',
                      'Queue time is null when the API does not supply job created_at.',
                      'Collect again after completion for final full-pipeline runner minutes.']}


def render(report):
    if report['status'] != 'available':
        return '\n## GitHub telemetry\n\nUnavailable: ' + report['reason'] + '\n'
    lines = ['\n## GitHub scheduling and artifact overhead\n',
             f"Completed-job runner minutes at snapshot: **{report['completed_job_runner_minutes']:.3f}**.",
             f"All selected jobs completed: **{report['all_selected_jobs_completed']}**. This is not billing data.\n",
             '| Job | Queue s | Setup to compute s | Compute step s | Download steps s | Upload steps s | Job s |',
             '|---|---:|---:|---:|---:|---:|---:|']
    def fmt(value):
        return 'n/a' if value is None else f'{value:.1f}'
    for row in report['jobs']:
        fields = ['queue_seconds', 'setup_to_compute_seconds', 'compute_step_seconds',
                  'artifact_download_step_seconds', 'artifact_upload_step_seconds', 'job_seconds']
        lines.append('| ' + row['name'] + ' | ' + ' | '.join(fmt(row[field]) for field in fields) + ' |')
    return '\n'.join(lines + ['', *report['notes'], ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--run-id', default=os.environ.get('GITHUB_RUN_ID'))
    parser.add_argument('--namespace', default=os.environ.get('HEX_NAMESPACE', 'hex'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        if not args.repo or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
            raise ValueError('valid owner/repository is required')
        if not args.run_id or not str(args.run_id).isdigit():
            raise ValueError('numeric run id is required')
        token = os.environ.get('GH_TOKEN', '')
        def fetch(suffix):
            url = f'https://api.github.com/repos/{args.repo}/actions/runs/{args.run_id}' + suffix
            headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                       'User-Agent': 'HEXADECARUNNER'}
            if token:
                headers['Authorization'] = 'Bearer ' + token
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                return json.load(response)
        run, jobs = fetch(''), []
        for page in range(1, 101):
            batch = fetch(f'/jobs?filter=all&per_page=100&page={page}')['jobs']
            jobs.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError('job pagination limit reached; refusing truncated telemetry')
        report = summarize(run, jobs, args.namespace)
        (args.output / 'github-raw.json').write_text(json.dumps({'run': run, 'jobs': jobs}, indent=2))
    except (OSError, ValueError, KeyError, urllib.error.HTTPError) as error:
        report = {'schema': 1, 'status': 'unavailable', 'reason': f'{type(error).__name__}: {error}'}
    (args.output / 'telemetry.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (args.output / 'telemetry.md').write_text(render(report))
    print(render(report))


if __name__ == '__main__':
    main()
