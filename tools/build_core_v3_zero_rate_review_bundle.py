#!/usr/bin/env python
"""Build the external-review bundle for the Core V3 zero-rate initializer."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "core_v3_zero_rate_initializer_external_review_20260727"
OUTPUT = Path.home() / "Downloads" / f"{PACKAGE_NAME}.zip"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _selected_paths() -> tuple[Path, ...]:
    paths: set[Path] = set()
    explicit = (
        "README.md",
        "pyproject.toml",
        "docs/core_v3_zero_rate_initializer_problem_statement_20260727.md",
        "docs/core_v3_zero_rate_initializer_external_review_prompt_20260727.md",
        "docs/requirements.md",
        "docs/model_architecture.md",
        "docs/issue_log.md",
        "docs/gates_explained.md",
        "docs/dynamic_column_initialization_strategy.md",
        "docs/initializer_requirements_and_acceptance.md",
        "src/dynamic_distillation/thermo_provider_v1.py",
        "src/dynamic_distillation/pr_flash_backend_v1.py",
        "src/dynamic_distillation/excel_case_loader_v1.py",
        "src/dynamic_distillation/column_spec_builder_v1.py",
        "src/dynamic_distillation/dwsim_compounds_v2.py",
        "sandbox/mini8/input/distillation_column_template_8stage.xlsx",
        "tools/build_core_v3_zero_rate_review_bundle.py",
    )
    for relative in explicit:
        path = ROOT / relative
        if path.is_file():
            paths.add(path)
    for number in range(108, 121):
        paths.update(path for path in (ROOT / "docs").glob(f"dd_{number}_*.md") if path.is_file())
        paths.update(path for path in (ROOT / "logs").glob(f"dd{number}*.json") if path.is_file())
    paths.update(path for path in (ROOT / "src/dynamic_distillation/core_v3").glob("*.py") if path.is_file())
    paths.update(path for path in (ROOT / "tests").glob("test_core_v3_*.py") if path.is_file())
    paths.update(path for path in (ROOT / "tools").glob("*core_v3*.py") if path.is_file())
    return tuple(sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix()))


def main() -> dict[str, object]:
    paths = _selected_paths()
    if not paths:
        raise RuntimeError("review bundle selection is empty")
    required = ROOT / "docs/core_v3_zero_rate_initializer_problem_statement_20260727.md"
    if required not in paths:
        raise RuntimeError("review bundle is missing its problem statement")

    payloads: dict[str, bytes] = {}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        payloads[relative] = path.read_bytes()
    payloads["README_REVIEW_FIRST.md"] = required.read_bytes()
    package_info = {
        "package_name": PACKAGE_NAME,
        "source_repository": str(ROOT),
        "git_branch": _git("branch", "--show-current"),
        "git_commit": _git("rev-parse", "HEAD"),
        "intended_first_file": "README_REVIEW_FIRST.md",
        "dd119_contract_commit": "a56d2ce",
        "dd119_result_commit": "5499c08",
        "dd120_contract_commit": "67b9c51",
        "dd120_result_commit": "4c1597f",
        "focused_test_status": "163 passed before DD-120 execution",
        "selected_repository_files": len(paths),
    }
    payloads["PACKAGE_INFO.json"] = json.dumps(package_info, indent=2).encode("utf-8")
    payloads["GIT_HISTORY.txt"] = (
        _git("log", "--oneline", "--decorate", "-25") + "\n"
    ).encode("utf-8")
    payloads["GIT_STATUS_AT_PACKAGING.txt"] = (
        _git("status", "--short", "--untracked-files=no") + "\n"
    ).encode("utf-8")

    manifest_buffer = io.StringIO(newline="")
    writer = csv.writer(manifest_buffer)
    writer.writerow(("path", "bytes", "sha256"))
    for relative, data in sorted(payloads.items()):
        writer.writerow((relative, len(data), _sha256(data)))
    payloads["MANIFEST.csv"] = manifest_buffer.getvalue().encode("utf-8")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(payloads.items()):
            archive.writestr(f"{PACKAGE_NAME}/{relative}", data)
    with ZipFile(OUTPUT, "r") as archive:
        corrupt = archive.testzip()
        entries = len(archive.infolist())
    if corrupt is not None:
        raise RuntimeError(f"review bundle has a corrupt entry: {corrupt}")
    result = {
        "zip": str(OUTPUT),
        "bytes": OUTPUT.stat().st_size,
        "sha256": _sha256(OUTPUT.read_bytes()),
        "entries": entries,
        "selected_repository_files": len(paths),
        "verified": True,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
