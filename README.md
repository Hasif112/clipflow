# ClipFlow

Upload a full transformation video and get 5 edited reels back.

I made this for barbers, nail techs, braiders, lash techs, basically anyone whose work has a before and after. You drop in the whole session and it cuts it into short vertical videos you can post on IG, TikTok, or Shorts.

Still a work in progress.

## Why I'm building this

I run a content agency for barbershops. A lot of shops film their cuts, but nobody has time to go through an hour of footage and edit it. So I started building something that does it for them.

## How it works

1. It grabs one frame every second from the video and scores each one for how sharp and bright it is, so blurry or dark parts get skipped
2. Each reel style is set up in `recipes.json` (how long the before is, how many progress clips, timelapse speed, etc). The engine picks the best clips for each part without repeating any
3. If there isn't enough good footage, the reel just comes out shorter instead of using bad clips
4. FFmpeg cuts everything, crops it to vertical, and puts it together
5. Uploads run in the background and the site shows live progress, so reels show up one by one as they finish

## The 5 reels

| Reel | Length | What it is |
|---|---|---|
| Before / After | ~15s | Quick before, reveal from a few angles |
| Quick Hit | ~15s | Before, fast clips of the process, after |
| Timelapse | ~15s | Before, sped up process, after |
| Full Story | ~30s | More of the process, longer reveal |
| Slow Build | ~30s | Clips and timelapse, slower reveal |

## Built with

Python, FastAPI, FFmpeg, OpenCV, React, Vite, Tailwind

## Run it locally

You need Python 3.12, FFmpeg, and Node.

Backend:
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend (separate terminal):
```bash
cd frontend
npm install
npm run dev
```

Then go to http://localhost:5173

## What's next

- Face detection so it can actually find the before and after
- Train my own model on real session footage
- Editor for captions, fonts, colors, and transitions
- AI chat to edit or redo reels
- Accounts and putting it live online