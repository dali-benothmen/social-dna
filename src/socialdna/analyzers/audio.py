import math
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from socialdna.analyzers.base import TaskContext, TaskOutput


def audio_features(samples: NDArray[np.float64], sample_rate: int) -> dict[str, float]:
    rms = float(np.sqrt(np.mean(samples**2)))
    spectrum = np.abs(np.fft.rfft(samples))
    frequencies = np.fft.rfftfreq(len(samples), 1 / sample_rate)
    total = float(spectrum.sum())
    centroid = float(np.dot(frequencies, spectrum) / total) if total > 0 else 0.0
    bandwidth = (
        float(np.sqrt(np.dot((frequencies - centroid) ** 2, spectrum) / total))
        if total > 0
        else 0.0
    )
    rolloff = (
        float(
            frequencies[
                min(len(frequencies) - 1, int(np.searchsorted(np.cumsum(spectrum), 0.85 * total)))
            ]
        )
        if total > 0
        else 0.0
    )
    return {
        "rms": rms,
        "rms_dbfs": 20 * math.log10(max(rms, 1e-10)),
        "spectral_centroid": centroid,
        "spectral_bandwidth": bandwidth,
        "spectral_rolloff": rolloff,
        "zero_crossing_rate": float(np.mean(np.signbit(samples[1:]) != np.signbit(samples[:-1])))
        if len(samples) > 1
        else 0.0,
    }


def measure_audio(
    path: Path | None, start_ms: int, duration_ms: int, silence_db: float, context: TaskContext
) -> TaskOutput:
    if path is None:
        return TaskOutput(skipped="No extracted audio is available.")
    silent_ms, total_ms, pitches, tempo_values = 0, 0, [], []
    with sf.SoundFile(path) as source:
        sample_rate = source.samplerate
        for index, samples in enumerate(source.blocks(blocksize=sample_rate, dtype="float64")):
            begin = start_ms + index * 1000
            end = min(duration_ms, begin + round(len(samples) * 1000 / sample_rate))
            if end <= begin:
                break
            features = audio_features(samples, sample_rate)
            for key, value in features.items():
                unit = (
                    "Hz"
                    if key.startswith("spectral")
                    else "dBFS"
                    if key.endswith("dbfs")
                    else "ratio"
                )
                context.observe(
                    "audio." + key,
                    value,
                    begin,
                    end,
                    modality="audio",
                    unit=unit,
                    description=f"Deterministic {key}, mono 16 kHz, one-second windows.",
                )
            total_ms += end - begin
            if features["rms_dbfs"] < silence_db:
                silent_ms += end - begin
                segment_id = context.record(
                    "audio_segments",
                    {
                        "start_ms": begin,
                        "end_ms": end,
                        "segment_type": "low_energy",
                        "artifact_id": None,
                    },
                )
                context.evidence("audio_segment", segment_id, begin, end)
                continue
            # Pitch is a signal estimate, not perceived emotion or voice identity.
            if len(samples) >= 2048:
                pitch, voiced, _ = librosa.pyin(
                    samples, fmin=65, fmax=1000, sr=sample_rate, frame_length=1024, hop_length=512
                )
                values = pitch[np.isfinite(pitch) & voiced]
                if len(values):
                    median = float(np.median(values))
                    pitches.append(median)
                    context.observe(
                        "audio.pitch_hz",
                        median,
                        begin,
                        end,
                        modality="audio",
                        unit="Hz",
                        description="pYIN median over voiced frames; "
                        "unreliable with mixed speech/music.",
                    )
            # Onset strength is measured; no assertion that onsets are syllables or sound effects.
            onset = librosa.onset.onset_strength(
                y=samples, sr=sample_rate, n_fft=512, hop_length=256
            )
            context.observe(
                "audio.onset_strength",
                float(np.mean(onset)),
                begin,
                end,
                modality="audio",
                unit="spectral-flux",
                description="Mean positive spectral flux.",
            )
            if len(onset) > 4 and np.any(onset > 0):
                tempo = float(
                    np.asarray(
                        librosa.feature.tempo(onset_envelope=onset, sr=sample_rate, hop_length=256)
                    ).ravel()[0]
                )
                tempo_values.append(tempo)
                context.observe(
                    "audio.tempo_candidate_bpm",
                    tempo,
                    begin,
                    end,
                    modality="audio",
                    unit="BPM",
                    description="Autocorrelation tempo candidate on a short window; "
                    "not a reliable musical beat or speech-rate estimate.",
                )
    if total_ms:
        context.observe(
            "audio.low_energy_fraction",
            silent_ms / total_ms,
            start_ms,
            min(duration_ms, start_ms + total_ms),
            modality="audio",
            unit="ratio",
            description="Fraction of windows below the configured low-energy threshold; "
            "not a speech-pause detector.",
        )
    if len(pitches) > 1:
        context.observe(
            "audio.pitch_variation_hz",
            float(np.std(pitches)),
            start_ms,
            min(duration_ms, start_ms + total_ms),
            modality="audio",
            unit="Hz",
            description="Standard deviation of window-median voiced pitch estimates.",
        )
    context.output.result = {
        "analyzed_ms": total_ms,
        "low_energy_ms": silent_ms,
        "tempo_candidates_bpm": tempo_values,
        "limitations": [
            "Tempo and pitch are signal estimates; mixed audio may be unreliable. "
            "Speech tempo, music/SFX classes and delivery style require later model adapters."
        ],
    }
    return context.output
