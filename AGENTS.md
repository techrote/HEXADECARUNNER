# Agent contract

- GitHub-hosted Ubuntu CPU runners only. No self-hosted runner, physical GPU, VPN, external compute service or live public listener.
- Four workers by default. 8/16/32 are opt-in; never launch all sizes automatically.
- Preserve fail-closed manifest, coverage, result and baseline validation. A missing worker is a failure, not reduced coverage.
- All benchmark claims must name source SHA, task parameters, process counts, retry/cache state and measured overhead. Local emulation is not physical multi-node qualification.
- Keep runtime standard-library-only. Run `python -m unittest discover -s tests -v` and validate workflow YAML before publication.
- Action dependencies must be immutable SHA pins. Do not inherit secrets or add write permissions to compute jobs.
- Checkpoint recovery covers published artifacts, not work lost before upload. Never claim otherwise.
- Update documentation and test failure paths when changing workflow orchestration or schemas.
