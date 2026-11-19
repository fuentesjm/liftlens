"""Download the pretrained MediaPipe Pose Landmarker model into models/."""

import urllib.request
from pathlib import Path

URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
       "pose_landmarker_full/float16/latest/pose_landmarker_full.task")
DEST = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"

if __name__ == "__main__":
    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}\n  -> {DEST}")
    urllib.request.urlretrieve(URL, DEST)
    print(f"Done ({DEST.stat().st_size / 1e6:.1f} MB)")
