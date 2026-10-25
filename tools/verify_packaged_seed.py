"""Prove a Flutter release package contains the exact reviewed content seed."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from editorial_corrections import verify_corrections
from cloze_utils import valid_cloze_span

ROOT = Path(__file__).resolve().parent.parent


def verify(package: Path) -> dict:
    expected = ROOT / 'vocab_app/assets/seed/vocab.db'
    matches = list(package.rglob('flutter_assets/assets/seed/vocab.db'))
    if len(matches) != 1:
        raise SystemExit(f'expected one packaged seed, found {len(matches)}')
    actual = matches[0]
    if hashlib.sha256(expected.read_bytes()).digest() != hashlib.sha256(actual.read_bytes()).digest():
        raise SystemExit('release seed differs from reviewed seed')
    with sqlite3.connect(f'file:{actual.as_posix()}?mode=ro', uri=True) as db:
        counts = [db.execute(f'SELECT count(*) FROM {table}').fetchone()[0] for table in ('words', 'example_sentences')]
        version = db.execute('SELECT value FROM content_meta WHERE key=?', ('content_version',)).fetchone()[0]
        if counts != [2967, 14835] or version != '4':
            raise SystemExit(f'unexpected packaged content: {counts} version={version}')
        verify_corrections(db)
        for row in db.execute('SELECT en_text,cloze_target,cloze_start,cloze_end FROM example_sentences'):
            if not valid_cloze_span(*row):
                raise SystemExit(f'invalid packaged cloze: {row[0]}')
    print(f'packaged_seed=verified words=2967 sentences=14835 version=4 path={actual}')
    return {
        'content_version': 4, 'words': 2967, 'sentences': 14835,
        'seed_sha256': hashlib.sha256(actual.read_bytes()).hexdigest(),
        'editorial_corrections_sha256': hashlib.sha256((ROOT / 'content/editorial_corrections.json').read_bytes()).hexdigest(),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    result = verify(args.package)
    if args.manifest:
        args.manifest.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
