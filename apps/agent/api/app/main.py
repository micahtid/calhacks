from fastapi import FastAPI

app = FastAPI(title="Hunter")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
