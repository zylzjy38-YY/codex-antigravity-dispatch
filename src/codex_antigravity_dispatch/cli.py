"""JSON-oriented command line interface."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import __version__, core
from .storage import Invalid, initialize, read_json, state_path


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Capability-based Codex / Antigravity task preparation and explicit integration tests.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--state-dir", default=os.environ.get("CODEX_ANTIGRAVITY_STATE", str(Path.home() / ".codex-antigravity-dispatch")))
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "status", "doctor"):
        commands.add_parser(command)
    routing = commands.add_parser("route")
    routing.add_argument("--domain", required=True)
    routing.add_argument("--mode", choices=core.MODES, required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--task", required=True)
    prep.add_argument("--mode", choices=core.MODES, required=True)
    for command in ("inspect", "dispatch"):
        commands.add_parser(command).add_argument("--run-id", required=True)
    run = commands.add_parser("run", help="Explicit integration test; never automatic production dispatch")
    run.add_argument("--run-id", required=True)
    run.add_argument("--allow-execution", action="store_true", help="Authorize this one external CLI invocation")
    run.add_argument("--test-model", required=True, help="Exact model ID authorized for this test only")
    run.add_argument("--agy", help="Absolute path to the official standalone agy executable")
    run.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    code = 0
    try:
        root = state_path(args.state_dir)
        if args.command == "init":
            result = initialize(root)
        elif args.command == "status":
            result = core.status(root)
        elif args.command == "doctor":
            result = core.doctor(root)
        elif args.command == "route":
            result = core.route(args.domain, args.mode, root)
        elif args.command == "prepare":
            result, code = core.prepare(read_json(args.task), args.mode, root)
        elif args.command == "inspect":
            result = core.inspect(args.run_id, root)
        elif args.command == "dispatch":
            result, code = core.dispatch(args.run_id, root)
        else:
            from .runner import run_test
            result, code = run_test(args.run_id, root, args.test_model, args.agy,
                                    args.timeout, args.allow_execution)
    except (Invalid, OSError, ValueError, KeyError, TypeError) as exc:
        result, code = {"status": "invalid", "execution_performed": False, "error": str(exc)}, 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return code
