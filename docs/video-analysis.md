# Deterministic local video analysis

Milestone 1 supports authorized local video only. No remote inference, network media
fetching, model downloads, psychological judgments, or performance claims run here.

## Pipeline and persistence

```text
local registration → probe + SHA-256
  prepare: source presentation timestamps + downscaled lossless proxy
    ├─ adaptive scenes (with detector scores)
    ├─ optical-flow motion samples
    ├─ frames ← scenes + motion → visual observations
    ├─ mono analysis audio → audio observations
    └─ supplied subtitle track
  timeline summary → JSON + Markdown report snapshots
```

The application service owns this DAG; CLI callbacks only validate input and render
results. `TaskRunner` commits outputs through SQLAlchemy Core and the existing artifact
store. There is no second database/client lifecycle, job server, or repository abstraction
per table. Media-specific import logic lives in `application/import_service.py` until
additional ingestion adapters justify splitting it.

All media intervals are integer milliseconds, half-open `[start, end)`, on the normalized
source timeline. The origin is the earliest selected stream/container start reported by
FFprobe. Source per-frame best-effort presentation timestamps, not `frame_index / fps`,
align the proxy frames, scenes and visual evidence, including VFR and nonzero starts.
The final frame's packet duration (or nominal rate fallback) determines video end;
raw container metadata is retained separately. Queries return intersecting intervals,
not clipped observations. Audio offsets are retained and short tracks stop at their
actual sample end. Supplied subtitles must already use this normalized video timeline.

The proxy has a maximum 320-pixel side and uses FFV1 with all decoded source frames
retained. OpenCV runs scene/motion/frame passes over it; source media is not repeatedly
decoded by each visual analyzer. FFprobe itself decodes to read presentation timestamps,
and audio extraction/loudness have their own passes: this is not a single-pass decoder.
No audio gain normalization is applied; "normalized analysis format" means mono 16 kHz
PCM. FFmpeg measures original-mix EBU R128 integrated input loudness separately.

Scene first/mid/last frames, regular samples (quick: 2 s, standard: 1 s, deep: 250 ms),
and high-motion samples are merged, bounded by `--max-frames` (default 120), and
perceptually/pixel deduplicated. Scene keyframes are retained unless the overall bound
requires thinning. A contact sheet contains up to the first 24 selected frames. Frame
and contact-sheet blobs, audio, source subtitle bytes, and reports use content-addressed
storage; files have no extension and their MIME types live in SQLite.

## Measurements, not interpretations

Visual observations include quantized RGB palette, HSV histogram, LAB mean, brightness,
saturation, contrast, entropy, Canny edge density, Laplacian variance (a blur proxy),
sampled aspect ratio, shot durations/cut rate, and median Farneback optical flow. Proxy
geometry reflects FFmpeg's autorotation; source dimensions/rotation remain in probe metadata.
Framing here means geometry, not composition/subject detection. Camera and subject
motion are not distinguished. Scene thresholds are genre-dependent and configurable.

Audio observations use one-second windows: RMS/dBFS, spectral centroid/bandwidth/rolloff,
zero crossings, onset strength, short-window tempo candidates, low-energy intervals,
pYIN voiced-pitch medians, and variation across those medians. Silence uses a configurable
energy threshold, not speech VAD. Tempo/pitch may be unreliable in mixed speech/music.
These features do not identify music, speakers, delivery style, or emotion. Undefined
integrated loudness is absent with a limitation, never reported as zero LUFS.

Every observation and scene/frame/text/audio record has timestamped evidence; task
results link to provenance, source records, configurations, dependency fingerprints,
and tool/library versions. JSON reports include all timeline lanes and evidence IDs.
Markdown links evidence frames and cites subtitle/measurement evidence; it limits the
measurement listing to 250 entries and directs readers to JSON for the remainder.
Untrusted names/text are escaped, not interpreted as instructions or active Markdown.

Transcription, OCR, and multimodal understanding are explicit skipped tasks. Missing
subtitles/audio are skipped modalities, not an analysis failure. An actual analyzer
failure produces a partial report and exit 5; unaffected tasks continue, while dependent
tasks are skipped. The run's execution status is `failed` if any task failed, while its
report/output status is `partial`. Storage's existing task/run enum is unchanged.

## Cache, resume, and limits

Fingerprints include source identity, analyzer version, relevant configuration/library
versions, and dependency fingerprints. Successful results are reused after verifying
their directly owned artifact checksums. Cached tasks reference the original producer;
observations are not copied. Changing palette bins reuses decoding, scenes, motion,
frames and audio, and reruns visual measurements and the timeline summary.

Each invocation normally creates a new run and report snapshots. `--resume RUN_ID`
retries incomplete/failed tasks using the original run. Supply the same options and
subtitle content. Tool-version/configuration changes require a new run. A killed process
can leave a running task/lease, but the OS releases its data-directory lock and the next
resume safely retries it. Atomic file writes can leave unregistered blobs after a failed
commit; verification reports them without deleting data. Corrupt existing content is
reported, not overwritten or silently repaired.

Default bounds: 2 GB input, 600 s duration, 36,000 decoded frames, 120 evidence frames,
300 s per subprocess, 5 MB subtitles, 16 MB ordinary stdout, and 64 KB retained stderr.
FFprobe frame-list output has a frame-count-derived bound. Inputs exceeding limits
require explicit settings changes; processing can still be CPU-intensive, especially
pYIN and the first librosa/Numba compilation. No GPU is required. Temporary work is
removed on normal exit/interruption; SIGKILL may leave cache directories for inspection.
These limits/protocol restrictions are safeguards, not an OS sandbox for hostile codecs.

Qdrant semantic indexing, persistent graph construction and lexical search start in
Milestone 2 and do not trigger media reprocessing here.
