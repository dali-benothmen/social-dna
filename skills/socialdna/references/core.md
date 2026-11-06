# Core workflows

The examples below use symbolic `RUN_ID`, `ACCOUNT_ID`, `POST_ID`, `EVIDENCE_ID` and
`REVISION_ID`. Replace them with returned values, not guessed identifiers. Use the
same explicit `--data-dir` throughout. Root `--format json` requests envelopes;
`report generate --format markdown` deliberately emits a document instead.

## Local media

```text
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze video /absolute/clip.mp4 --max-frames 60
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze image /absolute/photo.jpg --max-side 1024
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze carousel POST_ID --max-items 20
```

Video accepts `--subtitles /absolute/captions.srt`; this is a supplied transcript, not
ASR. Static carousels require an imported post and ordered local image references.
Mixed video/static or animated media are refused/partial, not silently flattened.
By default originals are referenced, not copied. `--copy-media` explicitly retains
original bytes (possibly private EXIF); generated image displays remove that metadata.
Video/image accept `--resume RUN_ID` only for a compatible interrupted configuration;
rerunning a carousel reuses eligible completed image tasks.

For requested enrichment, check the exact model capability without `--no-ai`; ask
before preparation/downloads and do not invoke an unavailable provider. `--ocr` on
images/carousels requires a prepared OCR runtime and model. Video supports explicit
`--transcribe`, `--ocr`, `--align`, `--pose`, `--classify-audio`, `--reason`. Use `--no-ai`
to suppress these, not to promise that a separate host model cannot see supplied data.
Resource ceilings appear in capabilities. Deep video emits an estimate on stderr;
frame counts, duration, OCR area and model runtime matter. There is no reliable
automatic wall-clock/RAM/cost prediction. Agree on a small bounded sample first.

## Authorized account exports and comparisons

```text
socialdna --data-dir /absolute/library --offline --format json import json /absolute/export.json --dry-run
socialdna --data-dir /absolute/library --offline --format json import json /absolute/export.json
socialdna --data-dir /absolute/library --offline --no-ai --format json analyze account ACCOUNT_ID --spec /absolute/comparison.json
socialdna --data-dir /absolute/library --offline --format json compare posts --left POST_ID_A --right POST_ID_B --spec /absolute/comparison.json
socialdna --data-dir /absolute/library --offline --format json compare accounts --left ACCOUNT_ID_A --right ACCOUNT_ID_B --spec /absolute/comparison.json
socialdna --data-dir /absolute/library --offline --format json compare reproduce RUN_ID
```

Dry-run validates without initializing storage. CSV uses `import csv` and the same
dry-run contract. Exports must carry a permission basis, source identity, record types,
definitions and actual observations; public competitor access does not supply private
retention, conversions or demographic insights. Failed validation includes row errors;
do not fabricate missing fields. Ask for an engine-compatible authorized export.
The bundled [synthetic JSON example](../assets/account.json) shows normalized syntax;
replace its source/records/paths with authorized supplied data. Never treat its
invented observations as creator evidence or infer the permission basis from the example.

Get the corrected spec using `skill schema comparison`. Explicitly use schema 2.0,
the actual metric key, age/window, publication/knowledge cutoffs, selection frame,
estimand/design, feature timing and complete test family. Within-creator and
cross-creator designs are distinct. Unversioned specs use legacy semantics: do not
present them as corrected historical controls. Too few matched creators/windows is
an evidence limitation, not permission to drop matching or switch metrics until significant.

Optional `analyze account --analyze-media --max-posts 10 --max-items 20` processes a
bounded local batch; omit `--with-local-models` for deterministic work. An ordinary
export or photo analysis does not need a research question or embeddings.

## Caption and hashtag evidence

```text
socialdna --data-dir /absolute/library --offline --format json creative cite-text POST_ID --field caption --start 0 --end 12
socialdna --data-dir /absolute/library --offline --format json creative cite-text POST_ID --field hashtag --tag-index 0
socialdna --data-dir /absolute/library --offline --format json evidence resolve EVIDENCE_ID --revision REVISION_ID --purpose new_claim
```

Use actual captured text offsets/tag indices. Tags, supplied alternative text, OCR
and captions are separate sources. A tag citation proves its captured wording, not
that it caused reach or is trending. Publishing/search, recommendation distribution
and profile conversion require their own evidence, not a generic engagement score.
Use `context`, `platform`, and `profile` domain reports when the requested inputs
exist; consult [research workflows](research.md) for those boundaries.

For the report handoff, read [the interface contract](interface.md).
