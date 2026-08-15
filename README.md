# Esh

An offline English/Thai vocabulary trainer for iPhone. Words are scheduled with
FSRS spaced repetition and practised through seven game types (flashcards,
cloze, dictation, matching, odd-one-out, word association, scramble) rather than
a single review screen.

Everything runs on-device. There is no account, no server, and no network call
at runtime — the vocabulary ships as a SQLite seed inside the app bundle and the
UI font is bundled rather than fetched.

The current build ships **130 words** (386 senses, 650 example sentences, 526
related words) as a first real-device test set.

## Layout

| Path | What it is |
|---|---|
| `vocab_app/` | The Flutter app |
| `tools/` | Python pipeline that generates the vocabulary and exports the app seed |
| `data/` | Local pipeline input — **not** in git, 383 MB, rebuildable via `tools/` |
| `SPEC.md` | Product and technical spec (Thai) |
| `ALGORITHM.md` | Every scheduling/selection number the app uses, and where it lives in code |
| `NOTES.md` | Chronological build log |

## Running it during development

Requires Flutter 3.44.4 stable.

```bash
cd vocab_app && flutter run -d windows
```

On web and desktop the app draws itself inside a fixed 390x844 iPhone-sized
frame so the layout matches the phone. On iOS that wrapper is not applied.

Tests and analysis:

```bash
cd vocab_app && flutter analyze && flutter test
```

## How a build reaches the phone

There is no Mac and no paid Apple Developer account in this pipeline.
`.github/workflows/ios-build.yml` runs on every push to `master`:

1. **flutter-tests** (Linux) — `flutter analyze` and `flutter test`.
2. **build-ios** (macOS runner) — `flutter build ios --release --no-codesign`,
   then packages `Runner.app` into `Payload/` and zips it as `Esh.ipa` by hand,
   because without a signing identity `xcodebuild -exportArchive` cannot run.
3. **publish** (Linux) — attaches the IPA to a `build-<run number>` GitHub
   Release and regenerates `apps.json`, the SideStore source manifest.

The app version is the CI run number (`1.0.<run>`), so every push is strictly
newer than the last and the phone sees an update without any manual version bump.

The IPA is unsigned; **SideStore re-signs it on the phone** with a free Apple ID.
That is what removes the $99 Apple Developer requirement, at the cost of a
re-sign every 7 days.

## Installing on an iPhone from Windows

One-time setup:

1. Install **Apple Devices** from the Microsoft Store (it provides the USB
   device service) and **iloader**.
2. Use iloader to install **SideStore**, signing in with a free Apple ID.
3. On the phone: trust the developer app under Settings → General → VPN &
   Device Management, enable Developer Mode, and connect **LocalDevVPN**.
4. In SideStore → Sources → add:
   ```
   https://raw.githubusercontent.com/pimdejvani/Esh_Learner/master/apps.json
   ```
5. Install Esh from the **Browse tab** — not from a downloaded file, or it will
   not auto-update.
6. Turn on Background App Refresh so SideStore can re-sign before the 7-day
   signature expires.

After that, pushing to `master` is enough: CI builds, releases, and updates the
source, and the phone offers the new version.

## Regenerating the vocabulary

The seed at `vocab_app/assets/seed/vocab.db` is produced by the `tools/` chain:

```bash
python tools/build_vocab_library.py
python tools/select_pilot_100.py
python tools/build_content_db.py
python tools/translate_vocab_content.py
python tools/validate_content_db.py
python tools/export_app_seed.py
```

The current seed is the 100-word pilot set plus a 30-word hard fixture used for
testing. Before any release beyond personal use, re-export without the fixture
(`export_app_seed.py` without `--include-test-words`); see `test.md`.

## Licence note

The bundled UI font, Plus Jakarta Sans, is under the SIL Open Font License —
see `vocab_app/assets/fonts/OFL.txt`.
