# Official CLI integration boundary

Sources inspected on 2026-10-14:

- [Installation and authentication](https://antigravity.google/docs/cli/install/)
- [Headless operation](https://antigravity.google/docs/cli/headless)
- [CLI permissions](https://antigravity.google/docs/permissions?tab=cli)
- [Remote Control and separate CLI/editor sign-in](https://antigravity.google/docs/remote-control?tab=cli)
- [CLI changelog](https://antigravity.google/docs/changelog?tab=cli)

The adapter targets the standalone `agy` binary. An IDE launcher that opens a chat window is not a headless provider. The Google Python SDK uses a different authentication/billing path; this project does not silently replace the user's CLI subscription with an API key or Vertex account.

## Probe protocol

Each attempt uses a fresh empty directory, a fixed model argument, `-p`, JSON output, a local JSON schema, an explicit print timeout, plan mode, sandbox and disabled slash expansion. No shell is used. Prompt content is bounded in size. The model ID is passed as one argument and is restricted to a slug-like string.

The official result envelope includes status, response, structured output, conversation ID and usage. This project validates the structured output it requested and refuses to treat exit code 0 alone as success. Known structured-error and soft-denial diagnostics also fail the probe. Unknown provider warnings and protocol changes still require human review.

No tool-use trace or actual-model field is currently independently verified. `verified_model` therefore stays null. `--mode plan` and `--sandbox` do not prove enforced read-only access. Workspace observations only cover the newly created probe directory, not the entire filesystem.

## Cancellation and recovery

The adapter uses an explicit provider timeout and a slightly longer outer timeout. It attempts to stop the local process tree on timeout/interruption. The CLI process ending does not establish that the remote service has cancelled a task. There is no resume, retry or cancellation API implemented here.

If local termination cannot be confirmed, the execution lock remains. A crash can also leave a lock. The operator must confirm both local and remote state before removing it. Reusing the same attempted package is always rejected; make a new package only after inspecting the previous outcome.

## Credentials and changing accounts

The official CLI owns authentication, cached credentials and model permissions. This tool neither discovers the user's email nor reads a keyring. It does not run login/logout commands. Changing desktop identity is not sufficient evidence that CLI identity changed. Stop active work, switch through the official CLI, confirm the intended account and model availability, then run a new explicitly authorized probe.

Successful `agy models` or a Flash probe does not establish Argon entitlement. Updating the CLI may change output fields, permissions and timeout behavior; rerun compatibility tests before trusting a new version for production work.
