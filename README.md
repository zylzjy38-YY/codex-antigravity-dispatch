# Codex Antigravity Dispatch

Capability-based task preparation for a Codex coordinator and an Antigravity specialist. [中文说明](README.zh-CN.md)

**Alpha software. Production dispatch remains disabled.** The project separates offline task routing and preparation from explicitly authorized integration tests. A prepared package is never automatically sent or replayed. Installing this package does not install Antigravity, log in, or change either client's account.

The sample policy assigns frontend design/implementation, complex deliverables and difficult academic reasoning to Antigravity, and backend/debugging/integration to Codex. These are editable preferences, not universal model rankings. Codex remains responsible for final verification.

## Install

Requires Python 3.10+; there are no third-party runtime dependencies.

```shell
python -m pip install .
cadispatch --version
cadispatch init
cadispatch status
cadispatch route --domain frontend_visual --mode auto
```

State defaults to `~/.codex-antigravity-dispatch`, outside the installed package. Override it with the absolute `--state-dir` argument **before the subcommand**, or `CODEX_ANTIGRAVITY_STATE`. `init` creates a new state directory and never overwrites existing data. It does not install global Codex instructions.

## What works

| Capability | Current scope |
|---|---|
| Domain-based routing | Editable local policy; explicit `independent`, `auto`, or `antigravity` mode |
| Offline task packages | Strict validation, task digest, preparation record, human-readable prompt |
| Standalone `agy` integration | Explicit **text-only probes** using JSON structured output |
| Duplicate/concurrent calls | One attempt per package and one active local execution lock |
| Error handling | Exit code, response status, schema, reported errors, outer timeout |
| Cancellation | Best-effort local termination; remote cancellation is **not verified** |
| Model identity | Records requested model; actual model metadata is **not independently verified** |
| Production repository editing | **Not implemented; `dispatch` stays blocked** |
| Account switching | No credentials stored; CLI login and entitlement must be rechecked separately |

This is a tested alpha foundation, not a mature unattended coding agent. See [verification](docs/VERIFICATION.md), [integration details](docs/INTEGRATION.md), and [the remaining work](docs/ROADMAP.md).

## Prepare a task

Copy [examples/task.json](examples/task.json), replace `work_dir` with an existing absolute path, and fill in the task. All paths refer to the machine running the command. Keep state and real task files out of Git.

```shell
cadispatch prepare --task /absolute/path/task.json --mode auto
cadispatch inspect --run-id RUN_ID_FROM_PREPARE
cadispatch dispatch --run-id RUN_ID_FROM_PREPARE
```

The last command deliberately returns `blocked` / exit code 3. `auto` is an explicitly selected routing mode, not an automatic background worker. Tasks routed to Codex or `ask_user` return `not_prepared` / exit code 4. No code in this package invokes Codex or creates another agent recursively.

The task contract requires `goal`, `background`, `domain`, `work_dir`, `inputs`, `access`, `allowed_write_paths`, `acceptance`, `constraints`, and `network`. `access` is `read-only` or `write`; `network` is `none` or `research`. These declare intent, not enforced OS permissions. The offline format supports write tasks for future adapters; the current live probe refuses them.

## Run an authorized text-only integration probe

Install the **standalone** [official Antigravity CLI](https://antigravity.google/docs/cli/install/) separately. The IDE launcher is not the same CLI. Verify its version and available model IDs with `agy --version` and `agy models`. Authenticate directly in the official client; never put tokens in this repository.

For a prepared task with no input files, read-only access, no writable paths and `network=none`:

```shell
cadispatch run --run-id RUN_ID_FROM_PREPARE --test-model gemini-3.8-flash-medium --allow-execution --timeout 120
```

If `agy` is not on PATH, pass `--agy /absolute/path/to/agy` (Windows: the standalone `agy.exe`). `--test-model` affects **this attempt only** and does not rewrite the configured Argon target. `run` is a separate explicit probe path; changing `enabled` in config cannot activate production `dispatch`.

The probe sends prompt text only, uses a fresh empty workspace, and invokes `--mode plan --sandbox --disable-slash-commands`. It does **not** pass `--dangerously-skip-permissions`. Plan mode and the CLI sandbox are not a proven whole-machine read-only boundary. No input files are copied and the task's original work directory is not used for execution. Use only nonsensitive text in probes.

The external model service necessarily requires a network connection. `network=none` means the task must not browse URLs; it does not disable provider transport. Global client instructions or tools may still be visible to `agy`; there is no guarantee of complete client-profile isolation.

The result schema contains `summary`, `blockers` and `evidence`. `response_received` means a structured response arrived, not that every user acceptance criterion or actual model identity was independently verified. The coordinator must check the result. CLI startup was authorized even when the server later rejects authentication or the model.

Prepared records stay immutable; probe evidence lives in a separate `execution/` directory. `inspect` checks the original preparation record; read `execution/result.json` for the probe outcome. Task hashes detect accidental changes, not malicious tampering. State directory permissions and Windows ACLs remain the user's responsibility.

## Accounts, timeouts and retries

- Desktop/IDE and standalone CLI logins are separate. A desktop account change is not proof of a CLI account change. See [official Remote Control documentation](https://antigravity.google/docs/remote-control?tab=cli).
- Sign out/in using the official CLI when needed. Recheck model access under the intended account before any new probe. This tool never reads keyring entries, copies credentials, switches accounts, or falls back to an API key/provider.
- The explicit inner timeout and outer process timeout prevent depending on version-specific defaults. Local termination cannot prove remote execution has stopped.
- There are no automatic retries or silent model fallbacks. A package has at most one probe attempt. Review its result and any remote activity before preparing a new one.
- A leftover `execution.lock` is not automatically removed. Confirm the original CLI and remote task are stopped before removing that single lock file. A lock is a cooperative concurrency mechanism, not a security boundary.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Query/preparation succeeded, or a structured probe response was received |
| 2 | Invalid input/configuration/record or a local filesystem error |
| 3 | Execution blocked |
| 4 | Routing does not select Antigravity |
| 5 | CLI, response, adapter or observed workspace failure |
| 6 | Timeout or interruption |
| 10 | Another execution lock exists |

Business results are JSON; argparse help and argument errors use normal console text.

## Use with Codex

Review [examples/AGENTS.fragment.md](examples/AGENTS.fragment.md) and adapt it to your local instructions. Installation does not edit any `AGENTS.md`. Ordinary use remains offline until the user explicitly authorizes a probe. The model preferences are examples, and account availability is never inferred from them.

## Development

```shell
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use temporary directories and simulated processes. They do not require an account or invoke a paid model.

GitHub Actions tests Python 3.10 and 3.14 on Windows and Linux and builds a wheel. CI never installs `agy` or uses a model credential.

MIT licensed. This is an independent project, not an official OpenAI or Google integration.
