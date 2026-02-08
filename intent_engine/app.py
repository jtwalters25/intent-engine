"""FastAPI application for Intent Engine."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import RankingRequest, RankingResponse
from .ranking_engine import RankingEngine

app = FastAPI(
    title="Intent Engine",
    description="A company-agnostic re-ranking system with rules-first intent parsing",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ranking engine
ranking_engine = RankingEngine()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Intent Engine",
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/rank", response_model=RankingResponse)
async def rank_items(request: RankingRequest) -> RankingResponse:
    """
    Rank items based on user context and intent.
    
    Args:
        request: RankingRequest containing items, user context, and optional intent
        
    Returns:
        RankingResponse with ranked items, explanations, and latency breakdown
        
    Raises:
        HTTPException: If ranking fails
    """
    try:
        response = ranking_engine.rank(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
