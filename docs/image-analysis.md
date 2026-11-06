# Individual photos and ordered carousels

Available in `0.0.19`, database head `0017_images`. These are offline descriptive
workflows using the existing media registry, artifacts, task cache and universal
evidence resolver. They need neither FFmpeg, research registration, embeddings nor
a model. Optional OCR uses an explicitly prepared local provider; it never downloads
weights or sends images to a remote service.

## Individual images

```sh
socialdna analyze image ./meal.jpg --no-ai --format json
socialdna analyze image ./meal.jpg --copy-media --format json
socialdna analyze image MEDIA_ID --ocr --format json
socialdna report generate --run RUN_ID --format markdown
socialdna evidence resolve EVIDENCE_ID --format json
```

`MEDIA_ID`, `RUN_ID` and `EVIDENCE_ID` stand for actual returned identities. The same
global `--data-dir` must be used across processes. `import local` now registers a
static image or video by checksum; `analyze image` accepts a local file or registered
image ID. It rejects videos rather than making an artificial one-frame timeline.
`timeline show` explicitly refuses static images.

The report includes source/display dimensions, applied orientation, transparency,
downscaled brightness, contrast, saturation, entropy, edges, Laplacian variance,
palette, histograms and Lab appearance proxies. These reuse the video analyzer's
numeric implementation, not its temporal evidence schema. They are **not** validated
aesthetic ratings, calibrated color grading, camera settings, semantic scene labels,
filmmaking expertise or predictions of engagement.

Images are fully decoded under a source-pixel bound, orientation-corrected and
resized to a bounded display. Transparent pixels are composited on fixed white.
PNG display derivatives carry no EXIF, GPS, comments or ICC metadata. Input color
profiles are not colorimetrically interpreted; these are approximate decoded-RGB
measurements. Pillow's [image loading safeguards](https://pillow.readthedocs.io/en/stable/reference/Image.html)
and [EXIF transpose operation](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose)
inform the explicit validation/normalization path.

Default limits:

- `SOCIALDNA_MAX_IMAGE_PIXELS=40000000` (at most 80000000 configured).
- `SOCIALDNA_MAX_IMAGE_BYTES=50000000` (at most 200000000 configured), additionally
  limited by the existing `max_media_bytes` setting.
- `--max-side 1024`, configurable from 64 to 2048; aspect ratio is preserved.
- `--palette-bins 8`, configurable from 2 to 32.

JPEG, PNG, WebP, BMP, single-page TIFF and single-frame GIF are supported by the
installed Pillow build. Animated/multipage images are refused, not silently reduced
to the first frame/page. HEIC, SVG, PDF, RAW and other codecs are not part of this
delivery. Malformed files and decompression-bomb warnings/errors fail closed before
unbounded pixel decoding. Header sniffing is bounded; a filename extension is not
proof that decoding succeeds.

`--copy-media` is explicit retention of **unmodified original bytes**, which may
contain private metadata. Without it, the engine retains only its managed display
derivative and observations, while the original remains an external file reference.
An image ID requires checksum-matching originals/managed originals for new analysis;
an old report can use its retained derivative. External originals and backups need
their own authorized cleanup.

## Source text and ordered carousels

The existing v1 CSV/JSON `media` record adds optional `alt_text` (up to 10000 code
points). It is supplied source metadata, not generated OCR. Omitted alternative text
remains unknown; an explicitly empty string stays empty. Caption and normalized
hashtags retain their existing exact post-text citations.

For example, a creator-owned export can contain:

```json
{
  "schema_version": "1.0",
  "source": {
    "dataset_id": "my-owned-carousel",
    "source_uri": "urn:owned:my-carousel",
    "permission_basis": "creator_owned_export"
  },
  "records": [
    {"record_type":"account","platform":"demo","external_id":"owner","niche":"cooking"},
    {"record_type":"post","platform":"demo","external_id":"meal","account_external_id":"owner","content_type":"carousel","published_at":"2026-01-01T12:00:00Z","caption":"A supplied preparation sequence"},
    {"record_type":"media","platform":"demo","post_external_id":"meal","position":0,"uri":"./slide-one.jpg","alt_text":"The finished meal"},
    {"record_type":"media","platform":"demo","post_external_id":"meal","position":1,"uri":"./slide-two.png","alt_text":"The preparation steps"}
  ]
}
```

Replace the relative paths with actual authorized files. Import does not decode or
download references. Paths are relative to the export file. Its returned `post_ids`
provide the real `POST_ID` for analysis:

```sh
socialdna import json owned.json --format json
socialdna analyze carousel POST_ID --max-items 20 --no-ai --format json
socialdna analyze carousel POST_ID --max-items 5 --ocr --format json
```

Only posts declared `carousel` use that command. Supplied **zero-based positions**
are preserved, including gaps. Identical bytes at different positions are retained
as separate placements with `duplicate_of` pointing to the first analyzed position;
the underlying image task is cached, not inferred again. Reordering inputs changes
the manifest and produces a new analysis. Old run reports retain their original
positions, text, citations and observations while retention is permitted.

Local image references and existing linked local image assets work offline. Remote
URLs, missing files, malformed images and mixed-in videos remain explicit unavailable
items. No downloader runs and videos are not passed through static-image processing.
The separate existing video workflow remains available for those video assets.

`--max-items` permits 1–100 analyzed placements, default 20; declared manifests are
bounded at 1000 items. Budget-excluded items remain `budget_skipped`. Failures do not
discard successful items. The aggregate `carousel-appearance-1` reports supplied
item count, available-image coverage, unique analyzed images and **position-weighted
available-item mean brightness**. Repeated placements count in that mean but are not
independent observations. Supplied coverage is not verified platform completeness,
viewer progression, retention or whole-post effectiveness.

## Optional OCR and exact region evidence

`--ocr` resolves only the configured prepared local OCR model. It uses the same
verified provider/worker protocol as video OCR, with a static image identity instead
of persisted frames or fake timestamps. OCR reports preserve provider/model/revision,
runtime/configuration and actual universal input citations.
Recognized strings remain opaque to internal artifact-handle substitution, so literal
text such as `@artifact:display` is preserved exactly rather than becoming an artifact ID.

Missing providers or inference failures retain deterministic observations and return
`partial`; boxes stay unavailable, not an assertion that no text exists. `--no-ai`
at the root or image/carousel command suppresses OCR even when `--ocr` is present.
OCR text, source alternative text, caption and hashtags are separate report fields.
OCR confidence is model confidence, not evidence of audience understanding.

The `image_record` locator uses exact media/subject revisions and, when applicable,
the frozen post revision, carousel position, display artifact and OCR box index/quote.
Regions are normalized `[left, top, right, bottom]` on the orientation-corrected display,
not raw rotated sensor pixels. The resolver checks nonempty bounds, actual OCR text,
asset ownership and exact frozen placement. Standalone image citations cannot invent
carousel positions. No locator has a media interval or viewing duration.

## Accounts, cache and reports

```sh
socialdna analyze account ACCOUNT_ID --metric METRIC_KEY --analyze-media --max-posts 10 --max-items 5 --format json
```

Existing explicit metric/design requirements still apply. `--max-posts` selects the
bounded post batch and `--max-items` limits placements per post. Photos dispatch to
static analysis, carousels to the ordered workflow, and ordinary video entries retain
the existing pipeline. Account `--with-local-models` can request prepared OCR; normal
no-model batches do not enable it. Static images have no invented duration, motion
or audio measurements; performance features that require them remain missing.
Static appearance values are not silently inserted into legacy video time-window
recipes; richer static-feature research requires an explicitly versioned adapter.

The normal JSON envelope and exit conventions apply: partial output has exit code 5,
not success code 0. JSON/escaped Markdown reports have actual evidence and descriptive
review prompts, not promised performance improvements. `report generate --run` works
after restart without rerunning analysis. This is not U2's portable skill or polished
product interface.

Method, input checksum, options, limits, numerical-library versions and prepared OCR
identity/runtime pin the existing task fingerprint. Cache reuse verifies retained
artifacts and actual universal input eligibility. Missing/corrupt derivatives are
recomputed from valid originals; changed original bytes cannot reuse an old image ID.
`analyze image ... --resume RUN_ID` requires the same source/configuration; completing
a partial run creates a new immutable static revision. A completed resume reads the
committed result. Historical revision citations remain explicit.

## Persistence and retention

`0017_images` adds three first-use tables: `static_records` binds actual image/carousel
runs or captured post-media inputs to real media/post revisions;
`static_evidence_bindings` binds typed universal citations; `task_citation_inputs`
preserves non-temporal model-input evidence without inventing legacy video records.
The evidence CHECK is atomically extended using the existing FK-checked rebuild,
preserving old rows, IDs, indexes and journal triggers. Released migrations are unchanged.

`post_media_input` records freeze URI/position/alternative text and actual source
authority. Completed image/carousel records and content-addressed archives remain
canonical. No new database server, dependency, embedding collection or research
registration is introduced. Basic analysis does not run indexing or graph queries.

Withdrawal gates source inputs before carousel work and on report/evidence reads.
Confirmed source erasure scrubs dependent static payloads, derivative/report artifacts
and original/reused static task caches. Erased inputs cannot be restored by cached
work. Permitted structural audit IDs remain; exact reproduction may be lost.

Controlled tests establish these software contracts, not real OCR accuracy, human
reviewer agreement, psychological mechanisms or social-media effectiveness.
