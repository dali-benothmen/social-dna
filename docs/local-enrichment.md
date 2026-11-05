# Optional local model enrichment (Milestone 3)

Status: implemented `0.0.4` enrichment behavior. The revised [roadmap](../PLAN.md)
preserves this historical milestone; R3 creative events and R7 psychological research
are planned additions, not features of the current reasoning endpoint.

This milestone was implemented before Milestone 2 at the user's explicit request.
It uses the existing task DAG, SQLite timeline, evidence, provenance and artifacts.
Semantic search, vector indexing, persistent graph queries and psychological discovery
are still unavailable. Revised R6 supersedes the old memory milestone. Memory and
research remain optional for ordinary transcription/video analysis.

## Install and prepare ASR/OCR

```bash
uv sync --locked --extra speech --extra ocr
uv run socialdna models status --format json
uv run socialdna models prepare asr-tiny --allow-download --data-dir ./research-data
uv run socialdna models prepare ocr-en --allow-download --data-dir ./research-data
uv run socialdna analyze video /path/to/video.mp4 --data-dir ./research-data --depth deep --offline --format json
```

Use the same data directory for preparation and analysis. The default ASR bundle is
`Systran/faster-whisper-tiny` at revision `d90ca5fe260221311c53c58e660288d3deb8d356`
(about 78 MB of files), with CPU/int8 as the default. The OCR bundle uses pinned
PP-OCRv4 detection/English-recognition ONNX weights. Every asset has an expected
SHA-256 and maximum byte count; mismatched files are rejected and existing corrupt
files are not overwritten. Download consent does not transfer any input media.

`models prepare` requires `--allow-download` or explicit TOML `allow_download=true`;
`--offline` always blocks downloads. Already verified weights remain usable offline.
Analysis never downloads, even if download permission is configured. `models status`
and `doctor` inspect weights, dependency metadata, licenses and device capabilities;
they do not load models, verify GPU availability, or establish native ABI compatibility.
`state=ready` means file checksums pass; `runtime_ready` separately checks package metadata.

Local workers run as bounded subprocesses. Their Python network operations and model
hub online behavior are disabled. Local weights/tokenizers must exist before inference.
Native libraries are trusted executable dependencies, not an OS sandbox: use reviewed
packages/models, and separate environments for incompatible runtimes.

## Profiles and commands

| Profile/flag | Behavior |
|---|---|
| quick | Deterministic analysis; ASR/OCR only when explicitly requested |
| standard | Use prepared ASR/OCR when available; segment timing |
| deep | Denser frames, prepared ASR/OCR, model word timestamps, pre-run resource estimate |
| `--no-ai` | Disable every enrichment task, including configured reasoning |
| `--transcribe` / `--no-transcribe` | Explicitly require or disable ASR |
| `--ocr` / `--no-ocr` | Explicitly require or disable OCR |
| `--align` | WhisperX forced alignment using a separately configured local bundle |
| `--pose` | Prepared MediaPipe pose geometry only; no identity/emotion classifier |
| `--classify-audio` | Prepared YAMNet event candidates with uncalibrated scores |
| `--reason` | Bounded derived evidence to an explicitly configured compatible server |

Unprepared auto-selected models are skipped with reasons. Explicitly requested but
unavailable models, actual inference failures, invalid responses or rejected transfers
produce partial analysis/exit 5 while preserving deterministic results. Optional missing
audio/subtitles are skips, not fabricated tracks. A model failure blocks its dependent
tasks but not independent deterministic or other-modality tasks.

Useful `[socialdna]` TOML settings (also `SOCIALDNA_*` environment variables):

```toml
[socialdna]
asr_model = "asr-tiny"
ocr_model = "ocr-en"
asr_device = "cpu"                    # cpu | cuda | auto
asr_compute_type = "int8"             # int8 | float16 | float32 | int8_float16
asr_language = "en"                   # omit for model language detection
inference_threads = 2
inference_timeout_seconds = 300.0
max_enrichment_frames = 24
max_input_bytes = 2000000
max_input_tokens = 16000
max_output_tokens = 2000
max_provider_attempts = 2
```

Limits apply per task/request, with sequential inference. Quick/standard/deep use at
most 4/12/24 evidence frames, additionally bounded by `max_enrichment_frames`. OCR
infers identical artifact bytes once and maps the output to every selected timestamp.
Small text can be missed in the 320-pixel proxy. Matching nearby OCR samples form a
persistence segment, but between-sample visibility is not verified; every box still
points to its actual observed frame and normalized quadrilateral.

Supplied subtitles, ASR, aligned ASR and OCR are separate tracks. Word timing is
nullable and never inferred by evenly splitting segment text. Zero-duration/unmatched
word estimates retain text with null timing. ASR/words are estimates; OCR and landmark
scores are not calibrated truth. The ASR/subtitle comparison is symmetric token
agreement, not WER/accuracy without a gold reference. No diarization or speaker identity
inference is enabled.

Aligned tracks share a clock; they do not yet establish a semantic relationship
between a promise, a reveal, a sound effect, and an audience response. Sparse sampled
frames cannot establish cue absence. Planned R3 creative events will record explicit
cross-modal relationships, boundary uncertainty, coverage, and source evidence without
rewriting existing observations. See [research contracts](research-contracts.md).

## Isolated optional pose/audio runtimes

MediaPipe depends on full/contrib OpenCV, whereas the engine uses headless OpenCV.
Do not install all extras together or replace the engine's native library. A worker can
use a separate Python without installing SocialDNA there (the engine invokes its own
standalone worker script):

```bash
uv venv /path/to/mediapipe-env --python 3.11
uv pip install --python /path/to/mediapipe-env/bin/python 'mediapipe==1.2.2' 'soundfile>=0.13,<1' 'Pillow>=11,<13'
uv run socialdna models prepare pose-lite --allow-download --data-dir ./research-data
uv run socialdna models prepare yamnet --allow-download --data-dir ./research-data
```

Configure per-capability interpreters in the same TOML config:

```toml
[socialdna.provider_pythons]
pose = "/path/to/mediapipe-env/bin/python"
audio_classifier = "/path/to/mediapipe-env/bin/python"
```

Then run with `--pose --classify-audio --config ...`. Windows uses the environment's
`Scripts/python.exe`. `provider_python` optionally overrides the default interpreter
for every capability; `provider_pythons` overrides individual capabilities.

Pose observations contain 33 body landmarks per detected pose, image-relative x/y/z
and visibility/presence estimates. Coordinates may lie outside the image. Pose indices
are frame-local, not identities or tracked people. Audio labels are explicitly uncertain
`hypothesis` candidates with raw model scores, not verified music/SFX/emotion classes.
Runtime licenses and model-weight terms are separate; pose-weight redistribution terms
are not independently established here. Models are downloaded, not bundled in releases.

## WhisperX alignment and custom bundles

The optional `alignment` extra pins WhisperX 3.8.6 (Python <3.14) and has a substantial
PyTorch/torchaudio dependency tree. Use a separate compatible worker environment and
set `provider_pythons.alignment` plus `alignment_model` in TOML. No alignment, diarization
or NLTK data is downloaded on demand. Alignment is language-specific: the prepared
manifest must declare the detected ASR language.

Register custom, reviewed local assets with:

```bash
socialdna models prepare CUSTOM_NAME --manifest /path/to/manifest.json --from-dir /path/to/reviewed-files --offline
```

The JSON manifest contains `name`, `capability`, `identity` (`provider`, `model`, exact
`revision`, `execution="local"`), `license`, `languages`, `expected_ram_mb`, and `files`.
Each file declares a relative `name`, exact lowercase `sha256`, `max_bytes` and optional
HTTPS `url`. No scripts, absolute paths, traversal, or remote-code loaders are accepted.
The manifest and verified files are installed beneath `models/<name>/<manifest-hash>`.
Only explicit preparation changes aliases; retain custom manifests with backups.
The provider identity must match the implemented backend: `faster-whisper`, `rapidocr`,
`whisperx`, or `mediapipe`, depending on capability.

ASR requires `config.json`, `model.bin`, `tokenizer.json` and vocabulary TXT/JSON.
OCR expects `det.onnx` and `rec.onnx`; pose/audio use `model.task`/`model.tflite`.
Alignment requires a compatible local Wav2Vec2 checkpoint with `model.safetensors`
(not a pickle checkpoint), config, processor/tokenizer/vocabulary files, and preinstalled
language-specific NLTK `punkt_tab` data under the bundle's `nltk_data/` tree. A missing
alignment/NLTK file fails locally; there is no fallback download. Alignment remains a
separate track and cannot overwrite the original ASR. The real large alignment runtime
was not exercised in this workspace; its offline API/timing contract is unit-tested.

## Explicit compatible reasoning profiles

A local `llama-server`-style chat-completions endpoint can consume text and, if the
configured model/server supports it, sampled images. No inference server or large
vision/language model is installed or started by SocialDNA:

```toml
[socialdna.reasoning_profile]
enabled = true
endpoint = "http://127.0.0.1:8080/v1/chat/completions"
provider = "llama-server"
model = "your-reviewed-model"
revision = "your-exact-weight-revision-or-digest"
execution = "local"
modalities = ["text", "image"]
```

HTTP model/revision fields are operator-declared, not cryptographically verified by
the compatible API. Use a pinned, reviewed server deployment.

Local profiles require a literal loopback IP, not a DNS hostname that can resolve
elsewhere. Remote profiles require HTTPS, `execution="remote"`, explicit `allowed_data`
(text/image), an enabled profile and `--remote-media-consent` or matching TOML policy.
Offline mode rejects remote transfer. `api_key_env` names an environment variable;
its value is never stored in configuration, request artifacts or reports. There are no
implicit redirects, proxy-environment routing, endpoint discovery or remote fallbacks.

Only bounded derived evidence is eligible: text excerpts and selected JPEGs, never
the original video/audio. Image indices map to supplied evidence IDs. The text budget
uses a conservative UTF-8 byte upper bound, image count/serialized bytes are bounded,
and each attempt requests a maximum output token count. Server token accounting and
image tokenization vary; these are not billing guarantees. Responses are bounded to
1 MB and must validate against the Pydantic schema and the supplied evidence IDs.
Invalid output retries at most `max_provider_attempts`; exhaustion commits no model
observations and leaves the report partial. Compatible API behavior is contract-tested
with an injected HTTP transport; a real configured VLM/LLM server was not evaluated here.

Every attempt commits an exact JSON request artifact before transmission, then records
success/failure and validated response bytes. Headers/credentials are never included.
An interrupted `attempted` call may have reached the server; resume can repeat it and
cannot guarantee exactly-once provider billing. Request artifacts contain sensitive
derived evidence and should be protected like the source library. Reports expose audit
artifact IDs/paths, never authorization headers. Source/model text is treated as untrusted
data, and interpretations remain evidence-bound hypotheses requiring human review.
The current reasoning task is deliberately bounded to supplied images/text and
does not investigate psychological mechanisms or correlate comments/performance.
Its prompt prohibits audience-psychology and performance claims. A future research
service must preserve those boundaries for this task, use separate reviewed research
inputs, evaluate competing explanations, and distinguish observational association
from evidence of a psychological mechanism.

## Persistence, cache and verification

Model tasks write provider/model/revision/prompt configuration, immutable source-evidence
links and canonical outputs atomically. New schema `0003_enrichment` adds word timing,
OCR boxes, input-evidence links and provider-call audits without altering released migrations.
Changing only ASR identity/configuration reuses media decode/scenes/color/audio extraction
and OCR, while rerunning transcription-dependent comparison/reasoning/timeline tasks.
Model tasks can resume after interruption without copying prior observations.

Core tests use clearly labeled deterministic provider/HTTP doubles; they do not claim
to perform ML inference. Real CPU tests are separate and opt-in:

```bash
SOCIALDNA_TEST_MODEL_LIBRARY=/absolute/path/to/prepared-library uv run pytest -m local_models
# Also test isolated pose/audio (same library must contain pose-lite and yamnet):
SOCIALDNA_TEST_MODEL_LIBRARY=/absolute/path/to/prepared-library SOCIALDNA_TEST_MEDIAPIPE_PYTHON=/path/to/mediapipe-env/bin/python uv run pytest -m local_models
```

Speech is synthesized by FFmpeg/libflite and the OCR frame is generated with Pillow.
There is no scraped test media or hosted model API. A manual GitHub Actions workflow
prepares the pinned ASR/OCR assets explicitly before running their native tests.

Primary implementation references: [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[RapidOCR](https://github.com/RapidAI/RapidOCR),
[WhisperX alignment](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py),
[MediaPipe pose](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python),
[MediaPipe audio](https://developers.google.com/edge/mediapipe/solutions/audio/audio_classifier/python),
and [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server).
