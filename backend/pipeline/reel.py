import subprocess
import sys
from pathlib import Path


def probe_duration(video: str) -> float:
    """Ask ffprobe how long the video is, in seconds."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def cut_clip(video: str, start: float, length: float, out_path: Path) -> None:
    """Cut a clip and convert it to vertical 1080x1920 at 30fps."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-ss", str(start), "-i", video, "-t", str(length),
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,setsar=1,fps=30",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         str(out_path)],
        check=True,
    )


if __name__ == "__main__":
    video = sys.argv[1]
    out_dir = Path("outputs/reel")
    out_dir.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(video)
    clip_len = 2.0
    plan = [
        ("before", 0.5),
        ("progress", duration * 0.5 - clip_len / 2),
        ("after", duration - clip_len - 0.5),
    ]

    clips = []
    for name, start in plan:
        path = out_dir / f"{name}.mp4"
        cut_clip(video, max(start, 0), clip_len, path)
        clips.append(path)
        print(f"Cut {name} clip at {start:.1f}s")

    list_file = out_dir / "clips.txt"
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in clips))

    final = out_dir / "reel_v0.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-c", "copy", str(final)],
        check=True,
    )
    print(f"Done: {final}")