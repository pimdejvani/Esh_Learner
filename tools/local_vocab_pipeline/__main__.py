from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import build_run, doctor, run_worker, status_report, summary_report, verify_result
from .semantic import build_blind_calibration, semantic_revalidate


def main() -> int:
    parser = argparse.ArgumentParser(prog="vocab-run", description="Build and run source-grounded local vocabulary jobs")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor")
    check.add_argument("--api-url")
    build = commands.add_parser("build")
    build.add_argument("run_dir", type=Path)
    build.add_argument("--evidence-db", type=Path, required=True)
    build.add_argument("--manifest", type=Path, required=True)
    build.add_argument("--draft-dir", type=Path, required=True)
    build.add_argument("--seq-start", type=int, required=True)
    build.add_argument("--seq-end", type=int, required=True)
    build.add_argument("--mode", choices=("audit_repair", "generate"), default="audit_repair")
    build.add_argument("--review-report-dir", type=Path)
    build.add_argument("--api-url", default="http://127.0.0.1:8082/v1/chat/completions")
    build.add_argument("--critic-pass", choices=("always", "never"), default="always")
    run = commands.add_parser("run")
    run.add_argument("run_dir", type=Path)
    run.add_argument("--ignore-resources", action="store_true", help="testing only")
    semantic = commands.add_parser("semantic-revalidate")
    semantic.add_argument("run_dir", type=Path)
    semantic.add_argument("calibration", type=Path)
    semantic.add_argument("output_dir", type=Path)
    semantic.add_argument("--api-url", default="http://127.0.0.1:8082/v1/chat/completions")
    blind = commands.add_parser("semantic-select-blind")
    blind.add_argument("run_dir", type=Path)
    blind.add_argument("output", type=Path)
    blind.add_argument("--exclude", action="append", type=Path, default=[])
    blind.add_argument("--count", type=int, default=25)
    for name in ("status", "summary", "verify"):
        sub = commands.add_parser(name)
        sub.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    if args.command == "doctor":
        result = doctor(args.api_url)
    elif args.command == "build":
        result = build_run(args.run_dir, args.evidence_db, args.manifest, args.draft_dir, args.seq_start, args.seq_end, mode=args.mode, review_report_dir=args.review_report_dir, config={"api_url": args.api_url, "critic_pass": args.critic_pass == "always"})
    elif args.command == "run":
        result = run_worker(args.run_dir, ignore_resources=args.ignore_resources)
    elif args.command == "semantic-revalidate":
        result = semantic_revalidate(args.run_dir, args.calibration, args.output_dir, config={"api_url": args.api_url})
    elif args.command == "semantic-select-blind":
        result = build_blind_calibration(args.run_dir, args.exclude, args.output, args.count)
    elif args.command == "status":
        result = status_report(args.run_dir)
    elif args.command == "summary":
        result = summary_report(args.run_dir)
    else:
        result = verify_result(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
