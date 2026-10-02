from fastapi import FastAPI

app = FastAPI(title="ClipFlow API")

@app.get("/health")
def health():
    return {"status": "ok"}