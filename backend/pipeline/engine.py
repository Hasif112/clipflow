import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.frames import brightness, extract_frames, sharpness

RECIPES = Path(__file__).parent / "recipes.json"
MIN_SCORE = 0.25       # windows scoring below this aren't good enough to use
MIN_VIDEO_SECONDS = 4  # anything shorter isn't worth making
ZONES = {"before": (0.0, 0.25), "progress": (0.25, 0.75), "after": (0.75, 1.0)}


def score_frames(video: str, out_root: Path) -> list[float]:
    """One quality score (0 to 1) for every second of video."""
    out_dir = out_root / "frames"
    shutil.rmtree(out_dir, ignore_errors=True)
    frames = extract_frames(video, str(out_dir))
    sharp = [sharpness(f) for f in frames]
    top = max(sharp) or 1.0
    scores = []
    for f, s in zip(frames, sharp):
        b = brightness(f)
        scores.append(0.0 if b < 40 or b > 220 else s / top)
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

    # offset makes each recipe prefer different picks, falls back to the best if footage is short
    chosen = picks[offset:offset + count] if len(picks) >= offset + count else picks[:count]
    used.extend((s, length) for s in chosen)
    return chosen


def plan_section(section, scores, used, offset):
    """Turn one recipe section into a list of shots: (start, source_seconds, speed)."""
    kind = section["type"]
    zone = zone_bounds(kind, len(scores))
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


def render_clip(video, start, source_len, speed, out_path):
    """Cut a shot, speed it up if needed, and make it vertical 1080x1920."""
    vf = (f"setpts=PTS/{speed},"
          "scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1,fps=30")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-ss", str(start), "-t", str(source_len), "-i", video,
         "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         str(out_path)],
        check=True,
    )


def build_reel(video, recipe, scores, index, out_root: Path):
    used, shots, after_first = [], [], None

    for section in recipe["sections"]:
        planned = plan_section(section, scores, used, offset=index)
        if section["type"] in ("before", "after") and not planned:
            print(f"  Skipped: no good {section['type']} shot found")
            return None
        if section["type"] == "after":
            after_first = planned[0]
        shots.extend(planned)

    if recipe.get("hook") and after_first:
        shots.insert(0, (after_first[0], 0.5, 1.0))

    total = sum(length / speed for _, length, speed in shots)
    if total < MIN_VIDEO_SECONDS:
        print(f"  Skipped: only {total:.1f}s of good footage")
        return None

    clip_dir = out_root / "reels" / recipe["name"]
    shutil.rmtree(clip_dir, ignore_errors=True)
    clip_dir.mkdir(parents=True)

    paths = []
    for i, (start, length, speed) in enumerate(shots):
        path = clip_dir / f"clip_{i:02d}.mp4"
        render_clip(video, start, length, speed, path)
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


def run_engine(video: str, out_root: Path) -> list[Path]:
    """Score the video once, then build every recipe. Returns the finished reels."""
    recipes = json.loads(RECIPES.read_text())
    scores = score_frames(video, out_root)
    reels = []
    for i, recipe in enumerate(recipes):
        print(f"Building {recipe['name']}...")
        reel = build_reel(video, recipe, scores, i, out_root)
        if reel:
            reels.append(reel)
    return reels


if __name__ == "__main__":
    reels = run_engine(sys.argv[1], Path("outputs"))
    print(f"Made {len(reels)} reels")