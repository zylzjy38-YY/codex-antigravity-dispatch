"""Explicit text-only integration probes for the standalone agy CLI.

This is not a production file-editing adapter or an enforced file sandbox.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from . import core
from .storage import Invalid, read_json, reject_links, state_path, text, write_json

OUTPUT_SCHEMA = {"type": "object", "properties": {
    "summary": {"type": "string"},
    "blockers": {"type": "array", "items": {"type": "string"}},
    "evidence": {"type": "array", "items": {"type": "string"}}},
    "required": ["summary", "blockers", "evidence"], "additionalProperties": False}


def stop_process(process):
    """Best-effort local process-tree termination; does not prove remote cancellation."""
    tree_stopped = False
    try:
        if os.name == "nt":
            # A recycled PID must never be targeted after the parent has exited.
            if process.poll() is None:
                outcome = subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                                         creationflags=subprocess.CREATE_NO_WINDOW, check=False)
                tree_stopped = outcome.returncode == 0
        else:
            os.killpg(process.pid, signal.SIGKILL)
            tree_stopped = True
    except ProcessLookupError:
        tree_stopped = os.name != "nt"
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass
    parent_stopped = process.poll() is not None
    return {"local_process_stopped": parent_stopped,
            "local_process_tree_stopped": tree_stopped and parent_stopped}


def invoke(argv, cwd, stdout_path, stderr_path, timeout):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    process = None
    try:
        with stdout_path.open("xb") as output, stderr_path.open("xb") as errors:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=errors, shell=False, **options)
            return {"exit_code": process.wait(timeout=timeout), "timed_out": False,
                    "interrupted": False, "cli_started": True, "local_process_stopped": True,
                    "local_process_tree_stopped": None, "cleanup_required": False}
    except (OSError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        stopped = stop_process(process) if process is not None else {
            "local_process_stopped": True, "local_process_tree_stopped": True}
        return {"exit_code": process.returncode if process is not None else None,
                "timed_out": isinstance(exc, subprocess.TimeoutExpired),
                "interrupted": isinstance(exc, KeyboardInterrupt), "cli_started": process is not None,
                "cleanup_required": process is not None, "error_type": type(exc).__name__, **stopped}


def parse_response(payload, stderr, exit_code):
    if exit_code != 0:
        return "cli_failed", None
    if re.search(r"AGY_ERROR|soft[- ]deny|permission.{0,40}denied", stderr, re.IGNORECASE):
        return "cli_reported_error", None
    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        return "unsuccessful_response", None
    result = payload.get("structured_output")
    if (not isinstance(result, dict) or set(result) != {"summary", "blockers", "evidence"}
            or not isinstance(result["summary"], str)
            or any(not isinstance(result[key], list) or any(not isinstance(v, str) for v in result[key])
                   for key in ("blockers", "evidence"))):
        return "invalid_response", None
    return ("response_with_blockers" if result["blockers"] else "response_received"), result


def executable(value):
    candidate = value or shutil.which("agy")
    if not candidate:
        raise Invalid("Standalone agy CLI not found; install it separately or provide --agy")
    path = Path(candidate).expanduser()
    if not path.is_absolute() or not path.is_file():
        raise Invalid("--agy must identify an existing absolute executable path")
    if os.name == "nt" and path.suffix.lower() != ".exe":
        raise Invalid("Use the standalone agy.exe, not an IDE .cmd launcher")
    return str(path.resolve())


def run_test(run_id, root, model, agy, timeout, allow_execution):
    if not allow_execution:
        return {"status": "blocked", "execution_performed": False,
                "reason": "This command needs explicit --allow-execution authorization."}, 3
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", text(model, "test model")):
        raise Invalid("Invalid test model ID")
    if not 10 <= timeout <= 900:
        raise Invalid("Integration-test timeout must be between 10 and 900 seconds")
    root = state_path(root)
    cfg = core.config(root)
    core.inspect(run_id, root)
    directory = core.run_directory(run_id, root)
    task = core.validate_task(read_json(directory / "task.json"), root)
    if task["inputs"] or task["access"] != "read-only" or task["allowed_write_paths"] or task["network"] != "none":
        raise Invalid("Integration probes require no input files, read-only access, no writable paths and network=none")
    binary = executable(agy)
    message = ("This is an authorized TEXT-ONLY integration probe. Do not use tools, read files, access URLs, "
               "or modify files. Answer from the prompt only. Return the requested structured result.\n\n"
               + core.prompt({**task, "work_dir": "<isolated probe workspace>"}, model))
    if len(message.encode("utf-8")) > 8000:
        raise Invalid("Text-only integration probe exceeds 8000 UTF-8 bytes")
    lock_path = root / "execution.lock"
    reject_links(lock_path)
    release_lock = True
    try:
        lock = lock_path.open("x", encoding="utf-8")
    except FileExistsError:
        return {"status": "busy", "execution_performed": False,
                "reason": "An execution lock exists; do not retry until the old process is confirmed stopped."}, 10
    try:
        with lock:
            lock.write(run_id)
        attempt = directory / "execution"
        reject_links(attempt)
        if attempt.exists():
            raise Invalid("This package already has an execution attempt; prepare a new package after reviewing its result")
        attempt.mkdir(mode=0o700)
        workspace = attempt / "workspace"
        workspace.mkdir(mode=0o700)
        schema = attempt / "output.schema.json"
        write_json(schema, OUTPUT_SCHEMA)
        argv = [binary, "-p", message, "--model", model, "--output-format", "json",
                "--json-schema", str(schema), "--print-timeout", f"{timeout}s",
                "--mode", "plan", "--sandbox", "--disable-slash-commands"]
        write_json(attempt / "request.json", {"run_id": run_id, "test_model": model,
                   "configured_model_unchanged": cfg["requested_model"], "timeout_seconds": timeout,
                   "test_only": True, "permission_boundary": "CLI plan mode and sandbox; not enforced file read-only"})
        output, errors = attempt / "stdout.json", attempt / "stderr.log"
        started = time.monotonic()
        report = {"run_id": run_id, "test_only": True, "requested_model": model,
                  "verified_model": None, "model_verification": "not_verified",
                  "execution_performed": False, "remote_cancellation_verified": False}
        try:
            release_lock = False  # Unknown startup/cleanup state must not permit a second call.
            report["execution_performed"] = None
            outcome = invoke(argv, workspace, output, errors, timeout + 5)
            release_lock = outcome["local_process_stopped"] and (
                not outcome["cleanup_required"] or outcome["local_process_tree_stopped"] is True)
            report.update(execution_performed=outcome["cli_started"], **outcome)
            if outcome["timed_out"] or outcome["interrupted"]:
                report["status"], code = ("timed_out" if outcome["timed_out"] else "interrupted"), 6
            elif outcome["exit_code"] != 0:
                report["status"], code = "cli_failed", 5
            else:
                payload = read_json(output)
                with errors.open(encoding="utf-8", errors="replace") as diagnostic_file:
                    diagnostics = diagnostic_file.read(131072)
                report["status"], report["result"] = parse_response(payload, diagnostics, outcome["exit_code"])
                report["conversation_id"] = payload.get("conversation_id") if isinstance(payload, dict) else None
                report["usage"] = payload.get("usage") if isinstance(payload, dict) else None
                code = 0 if report["status"] == "response_received" else 5
            # Observe only the isolated workspace, never claim whole-machine isolation.
            report["workspace_entries_observed"] = sorted(str(p.relative_to(workspace)) for p in workspace.rglob("*"))
            if report["workspace_entries_observed"]:
                report["status"], code = "workspace_changed", 5
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            report.update(status="adapter_error", error_type=type(exc).__name__)
            code = 5
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["exit_code"] = code
        report["execution_lock_retained"] = not release_lock
        report["artifact_dir"] = str(attempt)
        try:
            write_json(attempt / "result.json", report)
        except (OSError, ValueError) as exc:
            report.update(outcome_status=report["status"], status="result_persistence_failed",
                          result_persisted=False, persistence_error_type=type(exc).__name__, exit_code=5)
            code = 5
        return report, code
    finally:
        if release_lock:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                # Never replace an executed outcome with a misleading pre-execution CLI error.
                if "report" in locals():
                    report["execution_lock_retained"] = True
                    report["lock_release_failed"] = True
