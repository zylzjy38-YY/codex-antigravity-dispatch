## Optional Codex / Antigravity collaboration

- Remain independent unless the user explicitly selects automatic collaboration or Antigravity.
- Read the installed project's README and local routing policy. Assign bounded specialist deliverables, not generic read/write/review roles. Codex owns integration and final verification.
- Use `cadispatch status`, `route`, `prepare` and `inspect` for offline work. Preparation is not task execution. Do not infer account availability from a configured model label.
- Production `dispatch` is disabled. Only use `run --allow-execution --test-model <exact ID>` when the user explicitly authorizes a text-only integration test and its model. This may consume the account's model quota.
- Do not substitute models, accounts or billing methods. CLI and desktop logins are separate. Ask the user to resolve authentication through the official client; do not read or copy credential stores.
- Do not use the probe runner for repository editing, sensitive data or a task that requires enforced read-only access. The current adapter does not provide that enforcement.
- Do not recurse into other agents or run concurrent external tasks. Never replay an attempted package automatically. On interruption or timeout, report that remote cancellation is unverified.
- Verify the response against task acceptance criteria. Requested model identity is not independently verified actual model identity.
