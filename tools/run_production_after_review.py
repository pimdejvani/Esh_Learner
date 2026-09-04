#!/usr/bin/env python3
"""Run the production content pipeline once the full Sol review gate passes.

It is safe to call this after every review batch.  Before the manifest is fully
reviewed with zero report/overlay errors it prints ``gate=not_ready`` and exits
without translating or touching production files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STAGING_ROOT = ROOT / "staging" / "production_pipeline"
PROGRESS = re.compile(r"reviewed=(\d+)/(\d+).*errors=(\d+)")


def run(command: list[str], *, env: dict[str, str], log: Path) -> None:
    display = subprocess.list2cmdline(command)
    print(f"> {display}", flush=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"> {display}\n")
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            handle.write(line)
        code = process.wait()
    if code:
        raise SystemExit(f"pipeline command failed ({code}): {display}")


def review_gate(env: dict[str, str]) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "sol_review_progress.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    match = PROGRESS.search(result.stdout)
    if match is None:
        raise SystemExit(f"could not read review gate:\n{output}")
    reviewed, total, errors = map(int, match.groups())
    return reviewed == total and errors == 0 and result.returncode == 0, output


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def promote(staged_content: Path, staged_seed: Path, content: Path, seed: Path) -> None:
    """Replace both production files, restoring backups if the second replace fails."""
    content.parent.mkdir(parents=True, exist_ok=True)
    seed.parent.mkdir(parents=True, exist_ok=True)
    content_next = content.with_name(f".{content.name}.next")
    seed_next = seed.with_name(f".{seed.name}.next")
    content_backup = content.with_name(f".{content.name}.previous")
    seed_backup = seed.with_name(f".{seed.name}.previous")
    shutil.copy2(staged_content, content_next)
    shutil.copy2(staged_seed, seed_next)
    if content.exists():
        shutil.copy2(content, content_backup)
    if seed.exists():
        shutil.copy2(seed, seed_backup)
    try:
        os.replace(content_next, content)
        os.replace(seed_next, seed)
    except BaseException:
        if content_backup.exists():
            os.replace(content_backup, content)
        if seed_backup.exists():
            os.replace(seed_backup, seed)
        raise
    content_backup.unlink(missing_ok=True)
    seed_backup.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", default="azure,deepl")
    parser.add_argument("--content-db", type=Path, default=ROOT / "data" / "content_v2.db")
    parser.add_argument(
        "--seed-db", type=Path, default=ROOT / "vocab_app" / "assets" / "seed" / "vocab.db"
    )
    parser.add_argument("--staging-root", type=Path, default=STAGING_ROOT)
    args = parser.parse_args()

    env = os.environ.copy()
    env.setdefault("ESH_SOURCE_DB", str(ROOT / "data" / "vocabulary_evidence.db"))
    ready, detail = review_gate(env)
    print(detail)
    if not ready:
        print("gate=not_ready action=noop production_unchanged=true")
        return 0

    args.staging_root.mkdir(parents=True, exist_ok=True)
    lock = args.staging_root / "production.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"gate=ready action=noop reason=locked lock={lock}")
        return 0
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()}\n")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
    run_dir = args.staging_root / run_id
    run_dir.mkdir()
    log = run_dir / "pipeline.log"
    try:
        # Recheck under the lock so two reviewers finishing together cannot race.
        ready, detail = review_gate(env)
        if not ready:
            print("gate=changed action=noop production_unchanged=true")
            return 0

        english = run_dir / "english_reviewed"
        translated = run_dir / "translated"
        content = run_dir / "content_v2.db"
        seed = run_dir / "vocab.db"
        python = sys.executable
        run([python, "tools/build_vocab_library.py", "validate"], env=env, log=log)
        run([python, "tools/build_reviewed_english_drafts.py", "--output-dir", str(english)], env=env, log=log)
        run([python, "tools/translate_vocab_content.py", "--input-dir", str(english), "--dry-run"], env=env, log=log)
        run(
            [python, "tools/translate_vocab_content.py", "--input-dir", str(english),
             "--output-dir", str(translated), "--providers", args.providers],
            env=env,
            log=log,
        )
        run([python, "tools/build_content_db.py", "--draft-dir", str(translated), "--out", str(content)], env=env, log=log)
        run([python, "tools/validate_content_db.py", "--db", str(content)], env=env, log=log)
        run([python, "tools/export_app_seed.py", "--content-db", str(content), "--out", str(seed)], env=env, log=log)

        manifest = {
            "run_id": run_id,
            "review_gate": detail,
            "providers": args.providers,
            "content_sha256": digest(content),
            "seed_sha256": digest(seed),
            "production_content": str(args.content_db.resolve()),
            "production_seed": str(args.seed_db.resolve()),
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        promote(content, seed, args.content_db, args.seed_db)
        print(f"gate=passed action=promoted run={run_dir}")
        return 0
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
