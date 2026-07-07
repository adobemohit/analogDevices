"""Shared activity folder discovery logic (no third-party dependencies)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "deploy.config.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def discover_activity_folders(config: dict) -> list[Path]:
    discovery = config.get("discovery", {})
    info_file = discovery.get("info_file", "activity-info.json")
    exclude_dirs = set(discovery.get("exclude_dirs", []))

    folders: list[Path] = []
    for info_path in ROOT.rglob(info_file):
        if any(part in exclude_dirs for part in info_path.parts):
            continue
        folders.append(info_path.parent)

    return sorted(folders)


def get_git_changed_files(before_sha: str, after_sha: str) -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--name-status", before_sha, after_sha],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )

    changes: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        changes.append((status, path.replace("\\", "/")))
    return changes


def get_newly_added_activity_folders(config: dict) -> list[Path]:
    discovery = config.get("discovery", {})
    info_file = discovery.get("info_file", "activity-info.json")
    deploy_only_new = discovery.get("deploy_only_new_folders", True)

    all_folders = discover_activity_folders(config)
    if not deploy_only_new:
        return all_folders

    before_sha = os.environ.get("GITHUB_BEFORE_SHA", "").strip()
    after_sha = os.environ.get("GITHUB_SHA", "").strip()

    if not after_sha:
        print("GITHUB_SHA not set. Deploying all discovered activity folders.")
        return all_folders

    if not before_sha or before_sha == "0" * 40:
        print("First push detected. Treating all activity folders as new.")
        return all_folders

    changed_files = get_git_changed_files(before_sha, after_sha)
    new_folders: set[Path] = set()

    for status, path in changed_files:
        if not status.startswith("A"):
            continue
        if not path.endswith(info_file):
            continue
        folder = (ROOT / path).parent
        if folder.exists():
            new_folders.add(folder.resolve())

    return sorted(new_folders)
