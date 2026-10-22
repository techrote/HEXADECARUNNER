"""Example task adapter. Replace the body with a deterministic CI operation.

stdin: one JSON object {"id": "...", "payload": {...}}
stdout: exactly one JSON result; diagnostic logs belong on stderr.
Nonzero exit or timeout is a retryable failure. Never encode failure as success.
"""
import json
import sys


def main():
    task = json.load(sys.stdin)
    samples = task["payload"]["samples"]
    if not samples or not all(type(value) is int for value in samples):
        raise ValueError("samples must be a nonempty integer list")
    # A small deterministic reference operation; real adapters can invoke tests.
    result = {"sum": sum(samples), "sum_squares": sum(value * value for value in samples)}
    json.dump(result, sys.stdout, allow_nan=False, sort_keys=True)


if __name__ == "__main__":
    main()
