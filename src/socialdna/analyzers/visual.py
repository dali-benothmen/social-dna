from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
from PIL import Image

from socialdna.analyzers.base import TaskContext, TaskOutput
from socialdna.media.frames import ImageArray, iter_frames


def visual_features(frame: ImageArray, palette_bins: int) -> dict[str, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    histogram = np.bincount(gray.ravel(), minlength=256).astype(float)
    probability = histogram[histogram > 0] / gray.size
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    quantized = np.minimum((rgb.astype(np.int32) * palette_bins) // 256, palette_bins - 1)
    colors, counts = np.unique(quantized.reshape(-1, 3), axis=0, return_counts=True)
    order = np.argsort(counts)[::-1][:5]
    palette = [
        {
            "rgb": [round((int(component) + 0.5) * 256 / palette_bins) for component in colors[i]],
            "fraction": float(counts[i] / gray.size),
        }
        for i in order
    ]
    return {
        "brightness": float(gray.mean() / 255),
        "contrast": float(gray.std() / 255),
        "saturation": float(hsv[:, :, 1].mean() / 255),
        "entropy": float(-np.sum(probability * np.log2(probability))),
        "edge_density": float(np.mean(cv2.Canny(gray, 100, 200) > 0)),
        "laplacian_variance": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "aspect_ratio": float(frame.shape[1] / frame.shape[0]),
        "palette": palette,
        "hsv_histogram": [
            (
                np.histogram(hsv[:, :, channel], bins=8, range=(0, 180 if channel == 0 else 256))[0]
                / gray.size
            ).tolist()
            for channel in range(3)
        ],
        "lab_mean": lab.reshape(-1, 3).mean(axis=0).tolist(),
    }


def measure_visual(
    frames: list[dict[str, Any]], artifact_path: Any, palette_bins: int, context: TaskContext
) -> TaskOutput:
    for frame in frames:
        with Image.open(artifact_path(frame["artifact_id"])) as image:
            array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        for key, value in visual_features(cast(ImageArray, array), palette_bins).items():
            context.observe(
                "visual." + key,
                value,
                frame["timestamp_ms"],
                frame["end_ms"],
                modality="visual",
                unit="ratio"
                if key in ("brightness", "contrast", "saturation", "edge_density", "aspect_ratio")
                else "algorithm-defined",
                description=f"Deterministic {key}; downscaled evidence-frame measurement, "
                "not a perceptual judgment.",
            )
    context.output.result = {"measured_frames": len(frames), "palette_bins": palette_bins}
    return context.output


def measure_motion(
    proxy: Path, times: list[int], duration_ms: int, context: TaskContext
) -> TaskOutput:
    previous = None
    previous_time = 0
    samples = []
    for ordinal, timestamp, frame in iter_frames(proxy, times):
        if ordinal % 3:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if previous is not None and timestamp > previous_time:
            flow = cv2.calcOpticalFlowFarneback(
                previous,
                gray,
                np.empty((*gray.shape, 2), dtype=np.float32),
                0.5,
                3,
                15,
                3,
                5,
                1.2,
                0,
            )
            magnitude = np.linalg.norm(flow, axis=2)
            value = float(
                np.median(magnitude) / np.hypot(*gray.shape) / ((timestamp - previous_time) / 1000)
            )
            context.observe(
                "visual.optical_flow",
                value,
                previous_time,
                min(duration_ms, timestamp),
                modality="visual",
                unit="frame-diagonals/s",
                description="Median Farneback optical flow; "
                "camera and subject motion are not separated.",
            )
            samples.append({"ordinal": ordinal, "timestamp_ms": timestamp, "value": value})
        previous, previous_time = gray, timestamp
    context.output.result = {"samples": samples}
    return context.output
