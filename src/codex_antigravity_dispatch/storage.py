"""Local state and strict JSON validation. Never accesses client credentials."""
from __future__ import annotations

from importlib import resources
import json
import os
from pathlib import Path
import stat
import tempfile

MAX_JSON_BYTES = 2 * 1024 * 1024


class Invalid(ValueError):
    """An invalid task, configuration, path, or record."""


def object_fields(value, required, label):
    if not isinstance(value, dict) or set(value) != set(required):
        raise Invalid(f"{label} must have exactly these fields: {', '.join(sorted(required))}")
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"{label} must be a nonempty string")
    return value.strip()


def text_list(value, label, required=False):
    if not isinstance(value, list) or (required and not value):
        raise Invalid(f"{label} must be {'a nonempty' if required else 'a'} list")
    return [text(item, label) for item in value]


def reject_links(path):
    """Reject existing symlinks/junctions in state paths; not a hostile-process sandbox."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Invalid(f"State paths must not contain symlinks or reparse points: {part}")


def state_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise Invalid("State directory must be absolute")
    reject_links(path)
    return path.resolve()


def read_json(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise Invalid("JSON input exceeds 2 MiB")
    return json.loads(raw.decode("utf-8-sig"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    if os.name != "nt":
        Path(path).chmod(0o600)


def config(root):
    root = state_path(root)
    reject_links(root / "config.json")
    value = object_fields(read_json(root / "config.json"),
                          {"schema_version", "enabled", "adapter", "requested_model", "model_id", "reasoning_effort"}, "Config")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise Invalid("Unsupported config schema_version")
    if type(value["enabled"]) is not bool or value["adapter"] != "disabled":
        raise Invalid("enabled must be boolean; this release only supports adapter=disabled")
    text(value["requested_model"], "requested_model")
    for name in ("model_id", "reasoning_effort"):
        if value[name] is not None:
            text(value[name], name)
    return value


def initialize(root):
    root = state_path(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    if root.exists():
        raise Invalid("State directory already exists; init never overwrites existing data")
    staging = Path(tempfile.mkdtemp(prefix=".cadispatch-init-", dir=root.parent))
    try:
        for name in ("config.json", "routing.json"):
            source = resources.files("codex_antigravity_dispatch").joinpath("defaults", name)
            write_json(staging / name, json.loads(source.read_text(encoding="utf-8")))
        staging.rename(root)
    finally:
        # Only remove the two files we created; never recursively delete user paths.
        if staging.exists():
            for name in ("config.json", "routing.json"):
                (staging / name).unlink(missing_ok=True)
            staging.rmdir()
    return {"status": "initialized", "state_dir": str(root), "execution_performed": False}
