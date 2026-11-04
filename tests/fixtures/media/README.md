# Deterministic media fixtures

Tests synthesize authorized test videos using FFmpeg's built-in lavfi sources.
No external media, model download, or network access is used. The main fixture has
two colored shots, a moving test pattern, a 440 Hz tone, and supplied SRT cues.
Other fixtures cover variable frame rate, a non-zero source timestamp, no audio,
malformed media, and filenames containing shell metacharacters. Generated binaries
remain in pytest's temporary directory.
