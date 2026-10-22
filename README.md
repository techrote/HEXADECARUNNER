# HEXADECARUNNER

A reusable GitHub Actions distributed-compute proof of concept: **four compute workers by default**, selectable **8, 16 or 32**. Each worker uses up to four local Python processes. A single-runner baseline processes the identical task set before the worker phase, followed by strict artifact-based reduction.

This is **scatter/gather**, not a live MPI/Ray cluster, a shared-memory machine, or a way to bypass GitHub concurrency limits. Tasks must be independent. Workers communicate through a manifest and published result artifacts at stage boundaries.

Implementation and hosted qualification are tracked in issue #1. See the feature branch and forthcoming workflow documentation for the complete interface.

## Local test

```sh
python -m unittest discover -s tests -v
```

Python 3.11 or newer; no runtime dependencies.
