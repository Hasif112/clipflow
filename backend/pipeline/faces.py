import sys
from pathlib import Path

import cv2

MODEL = Path(__file__).parent / "models" / "face_detection_yunet_2023mar.onnx"


def make_detector():
    return cv2.FaceDetectorYN.create(str(MODEL), "", (320, 320), score_threshold=0.6)


def find_face(detector, image_path: Path):
    """Return the biggest face in the frame as (x, y, w, h, confidence), or None."""
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        return None
    best = max(faces, key=lambda f: f[2] * f[3])
    x, y, fw, fh = best[:4]
    return {
        "x": float(x / w), "y": float(y / h), "w": float(fw / w), "h": float(fh / h),
        "conf": float(best[-1]),
    }


if __name__ == "__main__":
    frames_dir = Path(sys.argv[1])
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    detector = make_detector()
    found = 0
    for i, f in enumerate(frames):
        face = find_face(detector, f)
        if face:
            found += 1
        if i % 30 == 0:
            label = f"face {face['w']*100:.0f}% wide, conf {face['conf']:.2f}" if face else "no face"
            print(f"{i // 60:02d}:{i % 60:02d}  {label}")
    print(f"Faces found in {found} of {len(frames)} frames")