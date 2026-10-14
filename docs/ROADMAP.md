# From alpha probes to production delegation

The next release should not enable production dispatch until these are implemented and independently verified:

- Enforced file and network boundaries appropriate to repository editing, including symlinks, junctions and child processes.
- Reliable actual-model evidence and rejection of unavailable or substituted models.
- Account-change detection without storing credentials, plus real same-machine CLI account-switch testing.
- Task submission, continuation and outcome retrieval with durable states that distinguish local failure from remote activity.
- Remote cancellation or an explicit operator recovery protocol, tested on Windows and Linux.
- Read-only, write-scoped, failed, permission-denied, timed-out and interrupted real tasks.
- A tested CLI version support policy; protocol fixtures from multiple supported versions, without private session data.
- Results and filesystem changes verified independently from model self-reports.

Frontend and knowledge routing preferences should be evaluated with representative project tasks. Benchmark names or scores do not substitute for project-level quality checks.

No release automation, telemetry, recurring account checks or automatic model fallback is included.
