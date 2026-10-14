# Alpha verification

Local verification date: 2026-10-14. Local host: Windows, Python 3.14. Standalone official `agy` version: 1.3.5.

## Observed live result

With explicit user authorization, the runner requested `gemini-3.8-flash-medium` for a nonsensitive text-only probe. The official CLI returned a SUCCESS envelope and a structured result whose summary was exactly `DISPATCH_SMOKE_OK`, with empty blockers and evidence. No new entries were observed in the isolated probe workspace.

This establishes one successful round trip through the CLI. It does not establish actual-model metadata verification, Argon availability, enforced read-only access, account switching, remote cancellation or repository-editing reliability. The configured target was not changed to Flash. Private conversation IDs, raw logs, paths and account data are intentionally excluded from this repository.

## Automated verification

The local suite passed **35 tests** before the initial publication. The built wheel was also checked for packaged defaults and exclusion of private state.

- Unit/integration tests cover strict task/configuration validation, domain routing, original preparation invariants, task digests, path checks, symlink rejection where supported, and partial preparation failures.
- Probe tests use simulated provider responses for missing consent, invalid model IDs, duplicate attempts, concurrent locks, response errors, malformed JSON, blockers, unexpected writes and unconfirmed termination.
- Local subprocess tests use Python, not a model, to verify output capture and timeout termination.
- Installed-CLI tests verify JSON output, exit codes, offline round trips and refusal to execute without explicit authorization.
- The workflow is configured for Windows/Linux and Python 3.10/3.14. An added CI file is not itself evidence of a successful hosted run; consult the repository Actions results.

Independent review identified and then verified fixes for cleanup after process-start errors, truthful reporting when result persistence fails, and preserving the lock when process-tree termination is uncertain. Publishing content was checked to exclude local usernames/paths, private task state and logs. This is a limited content check, not a guarantee against every possible secret format.

Test results apply to the checked revision; see commit history and Actions for subsequent changes.
