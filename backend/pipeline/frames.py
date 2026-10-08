import subprocess
import sys
from pathlib import Path

import cv2


def extract_frames(video_path: str, out_dir: str, fps: float = 1.0, width: int = 480) -> list[Path]:
    """Pull frames out of a video at a fixed rate, resized small for fast analysis."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video_path,
            "-vf", f"fps={fps},scale={width}:-2",
            "-q:v", "3",
            str(out / "frame_%05d.jpg"),
        ],
        check=True,
    )
    return sorted(out.glob("frame_*.jpg"))


def sharpness(image_path: Path) -> float:
    """Higher = sharper. Measures how strong the edges in the image are."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def brightness(image_path: Path) -> float:
    """Average pixel brightness from 0 (black) to 255 (white)."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    return float(img.mean())


if __name__ == "__main__":
    video = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "outputs/frames"

    frames = extract_frames(video, out_dir)
    print(f"Extracted {len(frames)} frames to {out_dir}")

    scores = [(f.name, sharpness(f), brightness(f)) for f in frames]
    blurry = [s for s in scores if s[1] < 100]
    dark = [s for s in scores if s[2] < 40]
    print(f"Blurry frames: {len(blurry)}")
    print(f"Dark frames: {len(dark)}")
    print("Sharpest 5:")
    for name, sharp, _ in sorted(scores, key=lambda s: s[1], reverse=True)[:5]:
        print(f"  {name}  sharpness={sharp:.0f}")