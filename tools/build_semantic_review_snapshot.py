"""Build an auditable staging database from Qwen candidates and ChatGPT audits.

This deliberately writes a new staging database. It never opens or modifies the
canonical vocabulary/evidence databases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SEQ_START = 2151
SEQ_END = 2325


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_rows(candidate: dict) -> list[dict]:
    return sorted(candidate.get("rows", []), key=lambda row: int(row["rank"]))


def candidate_parts(path: Path) -> tuple[dict, dict | None]:
    payload = read_json(path)
    if "candidate" in payload:
        return payload["candidate"], payload.get("report")
    return payload, None


def candidate_state(path: Path) -> str:
    if path.parent.name not in {"accepted", "quarantine"}:
        raise ValueError(f"candidate has unexpected parent: {path}")
    return path.parent.name


def seq_from_name(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def source_priority(seq: int) -> list[str]:
    if 2151 <= seq <= 2200:
        return ["semantic/20260825-chatgpt-25", "output"]
    if 2201 <= seq <= 2225:
        return ["semantic/20260825-blind-01", "output"]
    if 2226 <= seq <= 2250:
        return [
            "semantic/20260825-blind-02-repair-r5-simply",
            "semantic/20260825-blind-02-repair-r5-shift",
            "semantic/20260825-blind-02-repair-r4",
            "semantic/20260825-blind-02-repair-r3",
            "semantic/20260825-blind-02-repair-r2",
            "semantic/20260825-blind-02-repair",
            "semantic/20260825-blind-02",
            "output",
        ]
    if 2251 <= seq <= 2275:
        return [
            "semantic/20260825-blind-03-repair",
            "semantic/20260825-blind-03",
            "output",
        ]
    if 2276 <= seq <= 2300:
        return [
            "semantic/20260825-blind-04-repair-r4",
            "semantic/20260825-blind-04-repair-r3",
            "semantic/20260825-blind-04-repair-r2",
            "semantic/20260825-blind-04-repair",
            "semantic/20260825-blind-04",
            "output",
        ]
    return ["semantic/20260825-blind-05", "output"]


def load_versions(run_dir: Path) -> dict[int, list[dict]]:
    versions: dict[int, list[dict]] = defaultdict(list)
    roots = [run_dir / "output"]
    roots.extend(
        path
        for path in (run_dir / "semantic").iterdir()
        if path.is_dir() and not path.name.endswith("-source")
    )
    for root in roots:
        for state in ("accepted", "quarantine"):
            state_dir = root / state
            if not state_dir.is_dir():
                continue
            for path in state_dir.glob("*_*.json"):
                seq = seq_from_name(path)
                if not SEQ_START <= seq <= SEQ_END:
                    continue
                candidate, report = candidate_parts(path)
                versions[seq].append(
                    {
                        "seq": seq,
                        "source": root.relative_to(run_dir).as_posix(),
                        "state": candidate_state(path),
                        "path": path,
                        "candidate": candidate,
                        "report": report,
                    }
                )
    return versions


def choose_current(seq: int, versions: list[dict]) -> dict:
    by_source = defaultdict(list)
    for version in versions:
        by_source[version["source"]].append(version)
    for source in source_priority(seq):
        matches = by_source.get(source, [])
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(f"multiple current candidates for seq {seq} in {source}")
    raise ValueError(f"no candidate found for seq {seq}")


def issue_map(review_dir: Path) -> dict[str, dict[tuple[int, int], dict]]:
    maps: dict[str, dict[tuple[int, int], dict]] = {}

    calibration = read_json(review_dir / "20260825-chatgpt-calibration-seq2151-2200.json")
    maps["calibration"] = {
        (int(word["seq"]), int(issue["rank"])): issue
        for word in calibration["words"]
        for issue in word.get("issues", [])
    }

    blind01 = read_json(review_dir / "20260825-chatgpt-blind-01-audit.json")
    maps["blind01"] = {
        (int(word["seq"]), int(rank)): {
            "codes": word.get("codes", []),
            "reason": word["reason"],
        }
        for word in blind01["word_failures"]
        for rank in word["ranks"]
    }

    blind02 = read_json(review_dir / "20260825-chatgpt-blind-02-audit.json")
    maps["blind02_initial"] = {
        (int(issue["seq"]), int(issue["rank"])): issue
        for issue in blind02["failures"]
    }
    blind02_r3 = read_json(review_dir / "20260825-chatgpt-blind-02-repair-r3-audit.json")
    maps["blind02_r3"] = {
        (int(issue["seq"]), int(issue["rank"])): issue
        for issue in blind02_r3["failures"]
    }

    blind03 = read_json(review_dir / "20260825-chatgpt-blind-03-post-repair-audit.json")
    maps["blind03_final"] = {
        (int(issue["seq"]), int(issue["rank"])): issue
        for issue in blind03["remaining_failed_rows"]
    }

    blind04 = read_json(review_dir / "20260825-chatgpt-blind-04-post-repair-audit.json")
    maps["blind04_final"] = {
        (int(issue["seq"]), int(issue["rank"])): issue
        for issue in blind04["remaining_failed_rows"]
    }

    blind05 = read_json(review_dir / "20260825-chatgpt-blind-05-partial-audit.json")
    maps["blind05_partial"] = {
        (int(issue["seq"]), int(issue["rank"])): issue
        for issue in blind05["failures"]
    }
    return maps


def original_candidate(versions: list[dict]) -> dict | None:
    for version in versions:
        if version["source"] == "output":
            return version["candidate"]
    return None


def review_assignment(
    seq: int,
    current: dict,
    versions: list[dict],
    issues: dict[str, dict[tuple[int, int], dict]],
) -> tuple[str, dict[tuple[int, int], dict], str]:
    state = current["state"]
    source = current["source"]

    if seq >= 2310:
        return "pending_chatgpt_review", {}, "ChatGPT stopped before reviewing this word."
    if state == "quarantine":
        return "reviewed_quarantine", {}, "ChatGPT-reviewed, justified quarantine."
    if 2301 <= seq <= 2309:
        return "reviewed", issues["blind05_partial"], "Reviewed against the final blind-05 candidate."
    if 2276 <= seq <= 2300:
        return "reviewed", issues["blind04_final"], "Final candidate covered by the post-repair ChatGPT audit."
    if 2251 <= seq <= 2275:
        return "reviewed", issues["blind03_final"], "Final candidate covered by the post-repair ChatGPT audit."
    if 2226 <= seq <= 2250:
        if source == "semantic/20260825-blind-02-repair-r3":
            return "reviewed", issues["blind02_r3"], "Candidate covered by the ChatGPT r3 audit."
        if source in {"semantic/20260825-blind-02", "output"}:
            return "reviewed", issues["blind02_initial"], "Candidate covered by the initial ChatGPT audit."
        return (
            "pending_post_repair_review",
            {},
            "Word was reviewed earlier, but this later repaired candidate has not been re-audited by ChatGPT.",
        )
    if 2201 <= seq <= 2225:
        original = original_candidate(versions)
        if original is not None and canonical_rows(original) == canonical_rows(current["candidate"]):
            return "reviewed", issues["blind01"], "Candidate is unchanged from the ChatGPT-audited input."
        return (
            "pending_post_repair_review",
            {},
            "Word was reviewed earlier, but this repaired candidate has not been re-audited by ChatGPT.",
        )
    if source == "output":
        return "reviewed", issues["calibration"], "Original candidate covered by ChatGPT calibration review."
    return (
        "pending_post_repair_review",
        {},
        "Word was reviewed earlier, but this repaired candidate has not been re-audited by ChatGPT.",
    )


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE snapshot_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE words (
    seq INTEGER PRIMARY KEY,
    headword TEXT NOT NULL,
    qwen_state TEXT NOT NULL CHECK (qwen_state IN ('accepted', 'quarantine')),
    candidate_source TEXT NOT NULL,
    seen_by_chatgpt INTEGER NOT NULL CHECK (seen_by_chatgpt IN (0, 1)),
    final_candidate_reviewed INTEGER NOT NULL CHECK (final_candidate_reviewed IN (0, 1)),
    review_state TEXT NOT NULL,
    release_ready INTEGER NOT NULL CHECK (release_ready IN (0, 1)),
    review_notes TEXT NOT NULL,
    candidate_json TEXT NOT NULL
);
CREATE TABLE sentences (
    seq INTEGER NOT NULL REFERENCES words(seq),
    rank INTEGER NOT NULL,
    sense_id INTEGER,
    pos TEXT,
    target TEXT,
    memorable INTEGER NOT NULL,
    sentence TEXT NOT NULL,
    review_state TEXT NOT NULL,
    failure_codes_json TEXT,
    review_reason TEXT,
    PRIMARY KEY (seq, rank)
);
CREATE TABLE candidate_versions (
    id INTEGER PRIMARY KEY,
    seq INTEGER NOT NULL REFERENCES words(seq),
    qwen_state TEXT NOT NULL,
    source TEXT NOT NULL,
    source_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    selected_as_current INTEGER NOT NULL CHECK (selected_as_current IN (0, 1)),
    candidate_json TEXT NOT NULL,
    report_json TEXT
);
CREATE TABLE review_artifacts (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE review_batches (
    batch TEXT PRIMARY KEY,
    seq_start INTEGER NOT NULL,
    seq_end INTEGER NOT NULL,
    word_count INTEGER NOT NULL,
    seen_by_chatgpt_words INTEGER NOT NULL,
    pending_chatgpt_words INTEGER NOT NULL,
    final_candidate_reviewed_words INTEGER NOT NULL,
    pending_post_repair_words INTEGER NOT NULL,
    release_ready_words INTEGER NOT NULL
);
CREATE INDEX idx_words_review_state ON words(review_state);
CREATE INDEX idx_sentences_review_state ON sentences(review_state);
CREATE INDEX idx_candidate_versions_seq ON candidate_versions(seq);
CREATE VIEW reviewed_words AS
    SELECT * FROM words WHERE seen_by_chatgpt = 1;
CREATE VIEW pending_chatgpt_words AS
    SELECT * FROM words WHERE seen_by_chatgpt = 0;
CREATE VIEW pending_final_candidate_review AS
    SELECT * FROM words WHERE final_candidate_reviewed = 0;
CREATE VIEW release_ready_words AS
    SELECT * FROM words WHERE release_ready = 1;
"""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compact_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build(run_dir: Path, review_dir: Path, output: Path) -> dict:
    if output.resolve() in {
        (run_dir.parent.parent.parent / "data" / "vocabulary_evidence.db").resolve(),
        (run_dir.parent.parent.parent / "data" / "vocabulary.db").resolve(),
    }:
        raise ValueError("refusing to overwrite a canonical database")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing snapshot: {output}")

    versions_by_seq = load_versions(run_dir)
    missing = [seq for seq in range(SEQ_START, SEQ_END + 1) if seq not in versions_by_seq]
    if missing:
        raise ValueError(f"missing candidate versions for sequences: {missing}")
    current = {
        seq: choose_current(seq, versions_by_seq[seq])
        for seq in range(SEQ_START, SEQ_END + 1)
    }
    issues = issue_map(review_dir)

    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.executescript(SCHEMA)
        generated_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "schema_version": "1",
            "kind": "staging_semantic_review_snapshot",
            "generated_at_utc": generated_at,
            "source_run_id": "20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c",
            "source_bundle_id": run_dir.name,
            "seq_start": str(SEQ_START),
            "seq_end": str(SEQ_END),
            "canonical_db_modified": "false",
            "qwen_continuation": "stopped_by_user",
        }
        connection.executemany("INSERT INTO snapshot_meta VALUES (?, ?)", meta.items())

        word_rows = []
        sentence_rows = []
        assignments: dict[int, str] = {}
        for seq in range(SEQ_START, SEQ_END + 1):
            selected = current[seq]
            candidate = selected["candidate"]
            assignment, failure_map, notes = review_assignment(
                seq, selected, versions_by_seq[seq], issues
            )
            assignments[seq] = assignment
            sentence_states = []
            for row in canonical_rows(candidate):
                rank = int(row["rank"])
                failure = failure_map.get((seq, rank))
                if assignment == "pending_chatgpt_review":
                    row_state = "pending_chatgpt_review"
                elif assignment == "pending_post_repair_review":
                    row_state = "pending_post_repair_review"
                elif assignment == "reviewed_quarantine":
                    row_state = "excluded_quarantine"
                elif failure:
                    row_state = "fail"
                else:
                    row_state = "pass"
                sentence_states.append(row_state)
                codes = None
                reason = None
                if failure:
                    raw_codes = failure.get("codes", failure.get("code", []))
                    if isinstance(raw_codes, str):
                        raw_codes = [raw_codes]
                    codes = compact_json(raw_codes)
                    reason = failure.get("reason")
                sentence_rows.append(
                    (
                        seq,
                        rank,
                        row.get("sense_id"),
                        row.get("pos"),
                        row.get("target"),
                        int(bool(row.get("memorable"))),
                        row["sentence"],
                        row_state,
                        codes,
                        reason,
                    )
                )
            seen = int(seq <= 2309)
            final_reviewed = int(assignment in {"reviewed", "reviewed_quarantine"})
            if assignment == "reviewed_quarantine":
                word_state = "reviewed_quarantine"
            elif assignment == "reviewed" and "fail" in sentence_states:
                word_state = "reviewed_with_failures"
            elif assignment == "reviewed":
                word_state = "reviewed_pass"
            else:
                word_state = assignment
            release_ready = int(
                selected["state"] == "accepted"
                and word_state == "reviewed_pass"
            )
            word_rows.append(
                (
                    seq,
                    candidate["headword"],
                    selected["state"],
                    selected["source"],
                    seen,
                    final_reviewed,
                    word_state,
                    release_ready,
                    notes,
                    compact_json(candidate),
                )
            )

        connection.executemany(
            "INSERT INTO words VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", word_rows
        )
        connection.executemany(
            "INSERT INTO sentences VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", sentence_rows
        )

        version_rows = []
        for seq, versions in sorted(versions_by_seq.items()):
            for version in sorted(versions, key=lambda item: (item["source"], item["state"])):
                raw = version["path"].read_bytes()
                version_rows.append(
                    (
                        seq,
                        version["state"],
                        version["source"],
                        version["path"].relative_to(run_dir).as_posix(),
                        sha256_bytes(raw),
                        int(version["path"] == current[seq]["path"]),
                        compact_json(version["candidate"]),
                        compact_json(version["report"]) if version["report"] is not None else None,
                    )
                )
        connection.executemany(
            """INSERT INTO candidate_versions
               (seq, qwen_state, source, source_path, sha256, selected_as_current,
                candidate_json, report_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            version_rows,
        )

        artifact_rows = []
        for path in sorted(review_dir.glob("*.json")):
            # Do not ingest this builder's own generated summary on a rebuild.
            if path.resolve() == output.with_suffix(".summary.json").resolve():
                continue
            raw = path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("canonical_database_modified") is False
                and "database" in payload
                and "integrity_check" in payload
            ):
                continue
            artifact_rows.append((path.name, sha256_bytes(raw), raw.decode("utf-8")))
        connection.executemany(
            "INSERT INTO review_artifacts VALUES (?, ?, ?)", artifact_rows
        )

        batches = [
            ("calibration", 2151, 2200),
            ("blind_01", 2201, 2225),
            ("blind_02", 2226, 2250),
            ("blind_03", 2251, 2275),
            ("blind_04", 2276, 2300),
            ("blind_05", 2301, 2325),
        ]
        for name, start, end in batches:
            seen = sum(assignments[seq] != "pending_chatgpt_review" for seq in range(start, end + 1))
            pending = (end - start + 1) - seen
            final_reviewed = sum(
                assignments[seq] in {"reviewed", "reviewed_quarantine"}
                for seq in range(start, end + 1)
            )
            pending_post_repair = sum(
                assignments[seq] == "pending_post_repair_review"
                for seq in range(start, end + 1)
            )
            ready = sum(row[7] for row in word_rows if start <= row[0] <= end)
            connection.execute(
                "INSERT INTO review_batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    name,
                    start,
                    end,
                    end - start + 1,
                    seen,
                    pending,
                    final_reviewed,
                    pending_post_repair,
                    ready,
                ),
            )

        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_keys:
            raise RuntimeError(f"database verification failed: {integrity=}, {foreign_keys=}")

        counts = {
            "words": connection.execute("SELECT count(*) FROM words").fetchone()[0],
            "sentences": connection.execute("SELECT count(*) FROM sentences").fetchone()[0],
            "candidate_versions": connection.execute("SELECT count(*) FROM candidate_versions").fetchone()[0],
            "review_artifacts": connection.execute("SELECT count(*) FROM review_artifacts").fetchone()[0],
            "word_review_states": dict(
                connection.execute(
                    "SELECT review_state, count(*) FROM words GROUP BY review_state ORDER BY review_state"
                ).fetchall()
            ),
            "sentence_review_states": dict(
                connection.execute(
                    "SELECT review_state, count(*) FROM sentences GROUP BY review_state ORDER BY review_state"
                ).fetchall()
            ),
        }
    finally:
        connection.close()

    database_sha = sha256_bytes(output.read_bytes())
    sha_path = output.with_suffix(output.suffix + ".sha256")
    sha_path.write_text(f"{database_sha}  {output.name}\n", encoding="ascii")
    summary = {
        "ok": True,
        "database": str(output),
        "sha256": database_sha,
        "integrity_check": "ok",
        "foreign_key_check": "ok",
        "counts": counts,
        "pending_chatgpt_range": {"seq_start": 2310, "seq_end": 2325, "words": 16},
        "canonical_database_modified": False,
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = build(args.run_dir.resolve(), args.review_dir.resolve(), args.output.resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
