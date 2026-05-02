import os
from fastapi import FastAPI, HTTPException

from finance_vibe.scoring_service import compute_vibe_score


app = FastAPI(title="Finance Vibe Scoring Service", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/score/{ticker}")
def get_score(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 10:
        raise HTTPException(status_code=400, detail="Invalid ticker")

    try:
        return compute_vibe_score(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to score {ticker}: {e}")


if __name__ == "__main__":
    # Convenience for local runs without Docker
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)

