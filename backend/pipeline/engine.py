import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from pipeline.faces import find_face, make_detector
from pipeline.frames import extract_frames

RECIPES = Path(__file__).parent / "recipes.json"
MIN_SCORE = 0.25         # windows scoring below this aren't good enough to use
MIN_VIDEO_SECONDS = 4    # anything shorter isn't worth making
GOOD_FACE_CONF = 0.8     # how sure the detector must be to count as a clear face
GOOD_FACE_WIDTH = 0.15   # face must fill at least 15% of the frame width (client up close)
MIN_CHANGE = 0.15        # the after has to look this different from the before
ZONES = {"before": (0.0, 0.25), "progress": (0.2, 0.85), "after": (0.75, 1.0)}

# Ways a video might need turning, as (OpenCV rotation for frames, FFmpeg filter for rendering)
ROTATIONS = {
    0: (None, ""),
    90: (cv2.ROTATE_90_CLOCKWISE, "transpose=1,"),
    180: (cv2.ROTATE_180, "transpose=1,transpose=1,"),
    270: (cv2.ROTATE_90_COUNTERCLOCKWISE, "transpose=2,"),
}


def detect_rotation(frames, detector) -> int:
    """Check a sample of frames at every rotation and keep whichever shows the most upright faces."""
    sample = frames[:: max(1, len(frames) // 20)]
    counts = {}
    for angle, (cv_rot, _) in ROTATIONS.items():
        found = 0
        for f in sample:
            img = cv2.imread(str(f))
            if cv_rot is not None:
                img = cv2.rotate(img, cv_rot)
            face = find_face(detector, img)
            if face and face["conf"] >= GOOD_FACE_CONF:
                found += 1
        counts[angle] = found
    best = max(counts, key=counts.get)
    # Only turn the video if it clearly helps, otherwise leave it alone
    return best if counts[best] > counts[0] * 1.5 + 1 else 0


def head_snapshot(img, face):
    """A tiny grayscale picture of the head and hair area, used to measure how much it changed."""
    H, W = img.shape[:2]
    x, y, w, h = face["x"] * W, face["y"] * H, face["w"] * W, face["h"] * H
    x0, x1 = int(max(0, x - 0.6 * w)), int(min(W, x + 1.6 * w))
    y0, y1 = int(max(0, y - 1.0 * h)), int(min(H, y + 0.4 * h))
    crop = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return cv2.resize(crop, (24, 24)).astype(np.float32) / 255


def analyze(video: str, out_root: Path):
    """Look at one frame per second: how sharp it is, where the face is, and how much the head changed."""
    out_dir = out_root / "frames"
    shutil.rmtree(out_dir, ignore_errors=True)
    frames = extract_frames(video, str(out_dir))
    detector = make_detector()

    rotation = detect_rotation(frames, detector)
    if rotation:
        print(f"  Video looks sideways, turning it {rotation} degrees")
        for f in frames:
            cv2.imwrite(str(f), cv2.rotate(cv2.imread(str(f)), ROTATIONS[rotation][0]))

    seconds = []
    for f in frames:
        img = cv2.imread(str(f))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face = find_face(detector, img)
        good = bool(face and face["conf"] >= GOOD_FACE_CONF and face["w"] >= GOOD_FACE_WIDTH)
        seconds.append({
            "sharp": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
            "bright": float(gray.mean()),
            "face": face,
            "good_face": good,
            "snap": head_snapshot(img, face) if good else None,
        })

    # Cap sharpness at the 95th percentile so text overlays and end screens can't dominate
    cap = float(np.percentile([s["sharp"] for s in seconds], 95)) or 1.0
    for s in seconds:
        ok_light = 40 <= s["bright"] <= 220
        s["quality"] = min(s["sharp"] / cap, 1.0) if ok_light else 0.0

    # The "before" look = average of the first few clear face shots
    early = [s["snap"] for s in seconds[: max(1, len(seconds) // 4)] if s["snap"] is not None][:10]
    ref = np.median(early, axis=0) if early else None
    for s in seconds:
        s["change"] = float(np.abs(s["snap"] - ref).mean()) if (ref is not None and s["snap"] is not None) else None

    # Remember the last place we saw the face, so shots without one still crop sensibly
    last_x = 0.5
    for s in seconds:
        if s["face"]:
            last_x = s["face"]["x"] + s["face"]["w"] / 2
        s["center_x"] = last_x
    return seconds, rotation


def section_scores(seconds, kind):
    """How good each second is for this kind of shot."""
    scores = []
    for s in seconds:
        if kind == "progress":
            # The work itself: hands and clippers are fine, but a visible client is better
            scores.append(s["quality"] * (1.0 if s["face"] else 0.6))
        elif kind == "before":
            scores.append(s["quality"] * s["face"]["conf"] if s["good_face"] else 0.0)
        else:  # after: clear face AND it has to actually look different from the before
            changed = s["change"] is not None and s["change"] >= MIN_CHANGE
            scores.append(s["quality"] * s["face"]["conf"] if (s["good_face"] and changed) else 0.0)
    return scores


def zone_bounds(kind: str, total: int) -> tuple[int, int]:
    lo, hi = ZONES[kind]
    return int(lo * total), int(hi * total)


def overlaps(start: int, length: int, used: list[tuple[int, int]]) -> bool:
    return any(start < u_start + u_len and u_start < start + length for u_start, u_len in used)


def pick_windows(scores, zone, length, count, used, offset=0):
    """Find the best non-overlapping stretches of `length` seconds inside a zone."""
    start, end = zone
    candidates = []
    for s in range(start, end - length + 1):
        avg = sum(scores[s:s + length]) / length
        if avg >= MIN_SCORE:
            candidates.append((avg, s))
    candidates.sort(reverse=True)

    picks = []
    for _, s in candidates:
        if not overlaps(s, length, used + [(p, length) for p in picks]):
            picks.append(s)
        if len(picks) == count + offset:
            break

    chosen = picks[offset:offset + count] if len(picks) >= offset + count else picks[:count]
    used.extend((s, length) for s in chosen)
    return chosen


def plan_section(section, seconds, used, offset):
    """Turn one recipe section into a list of shots: (start, source_seconds, speed)."""
    kind = section["type"]
    scores = section_scores(seconds, kind)
    zone = zone_bounds(kind, len(seconds))
    style = section.get("style")

    if style == "timelapse":
        speed = section["speed"]
        source = min(math.ceil(section["seconds"] * speed), zone[1] - zone[0])
        if source < 2:
            return []
        picks = pick_windows(scores, zone, source, 1, used, offset)
        return [(s, source, speed) for s in picks]

    if style == "montage":
        clip = section["clip_seconds"]
        count = int(section["seconds"] // clip)
    else:
        count = section.get("angles", 1)
        clip = section["seconds"] / count

    picks = sorted(pick_windows(scores, zone, math.ceil(clip), count, used, offset))
    return [(s, clip, 1.0) for s in picks]


def video_size(video: str) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", video],
        capture_output=True, text=True, check=True,
    )
    w, h = out.stdout.strip().split(",")[:2]
    return int(w), int(h)


def render_clip(video, start, source_len, speed, center_x, size, rotation, out_path):
    """Cut a shot, turn it upright, crop a vertical 9:16 window around the client, speed it up if needed."""
    W, H = (size[1], size[0]) if rotation in (90, 270) else size
    crop_w = min(W, int(H * 9 / 16) // 2 * 2)
    crop_h = H if crop_w < W else int(W * 16 / 9) // 2 * 2
    x = int(min(max(center_x * W - crop_w / 2, 0), W - crop_w))
    vf = (f"{ROTATIONS[rotation][1]}"
          f"crop={crop_w}:{min(crop_h, H)}:{x}:0,"
          f"setpts=PTS/{speed},"
          "scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1,fps=30")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-ss", str(start), "-t", str(source_len), "-i", video,
         "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         str(out_path)],
        check=True,
    )


def build_reel(video, recipe, seconds, index, out_root: Path, size, rotation):
    used, shots = [], []

    for section in recipe["sections"]:
        planned = plan_section(section, seconds, used, offset=index)
        if section["type"] in ("before", "after") and not planned:
            print(f"  Skipped: no good {section['type']} shot found")
            return None
        shots.extend(planned)

    total = sum(length / speed for _, length, speed in shots)
    if total < MIN_VIDEO_SECONDS:
        print(f"  Skipped: only {total:.1f}s of good footage")
        return None

    clip_dir = out_root / "reels" / recipe["name"]
    shutil.rmtree(clip_dir, ignore_errors=True)
    clip_dir.mkdir(parents=True)

    paths = []
    for i, (start, length, speed) in enumerate(shots):
        # Crop around where the face is on average during this shot
        span = seconds[start:start + max(1, math.ceil(length))]
        center_x = float(np.median([s["center_x"] for s in span]))
        path = clip_dir / f"clip_{i:02d}.mp4"
        render_clip(video, start, length, speed, center_x, size, rotation, path)
        paths.append(path)

    list_file = clip_dir / "clips.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))
    final = out_root / "reels" / f"{index + 1}_{recipe['name']}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(final)],
        check=True,
    )
    print(f"  {final.name}: {total:.1f}s (target {recipe['target_seconds']}s, {len(shots)} clips)")
    return final


def run_engine(video: str, out_root: Path, on_progress=None) -> list[Path]:
    """Analyze the video once, then build every recipe. Reports progress as it goes."""
    def report(message, fraction, reel=None):
        print(message)
        if on_progress:
            on_progress(message, fraction, reel)

    recipes = json.loads(RECIPES.read_text())
    report("Finding faces and scoring footage...", 0.05)
    seconds, rotation = analyze(video, out_root)
    size = video_size(video)

    reels = []
    total = len(recipes)
    for i, recipe in enumerate(recipes):
        report(f"Building reel {i + 1} of {total}...", 0.2 + 0.8 * i / total)
        reel = build_reel(video, recipe, seconds, i, out_root, size, rotation)
        if reel:
            reels.append(reel)
            report(f"Finished reel {i + 1} of {total}", 0.2 + 0.8 * (i + 1) / total, reel)

    report("Done", 1.0)
    return reels


if __name__ == "__main__":
    reels = run_engine(sys.argv[1], Path("outputs"))
    print(f"Made {len(reels)} reels")