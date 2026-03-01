"""FastAPI application for Intent Engine."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import Domain, RankingMode, RankingRequest, RankingResponse, RankedItem, LatencyBreakdown
from .ranking_engine import RankingEngine
from .rules_translator import IntentTranslator
from .simple_ranker import IntentRanker
from .core.domain_engine import DomainRankingEngine
from .adapters.streaming import StreamingAdapter
from .adapters.ride_matching import RideMatchingAdapter
from .adapters.food_delivery import FoodDeliveryAdapter
import time

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

# Initialize engines (stateless singletons)
_ranking_engine = RankingEngine()
_translator = IntentTranslator()
_simple_ranker = IntentRanker(intent_weight=0.6)
_domain_engine = DomainRankingEngine({
    Domain.STREAMING: StreamingAdapter(),
    Domain.RIDE_MATCHING: RideMatchingAdapter(),
    Domain.FOOD_DELIVERY: FoodDeliveryAdapter(),
})


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


def _rank_simple(request: RankingRequest) -> RankingResponse:
    """Simple pipeline: IntentTranslator -> IntentRanker."""
    start = time.time()

    # Translate intent text (or fall back to neutral browse)
    intent_start = time.time()
    intent = _translator.translate(request.intent_text or "")
    intent_ms = (time.time() - intent_start) * 1000

    # Build a UserContext with the translated intent
    ctx = request.user_context.model_copy(update={"intent": intent})

    # Rank via simple ranker (accepts CandidateItem, Item inherits from it)
    rank_start = time.time()
    ranked = _simple_ranker.rank(list(request.items), ctx)
    rank_ms = (time.time() - rank_start) * 1000

    total_ms = (time.time() - start) * 1000

    return RankingResponse(
        ranked_items=ranked,
        latency=LatencyBreakdown(
            total_ms=total_ms,
            intent_parsing_ms=intent_ms,
            ranking_ms=rank_ms,
            diversity_check_ms=0.0,
        ),
        intent=intent,
    )


@app.post("/rank", response_model=RankingResponse)
async def rank_items(request: RankingRequest) -> RankingResponse:
    """Rank items based on user context and intent.

    Dispatches to the simple or advanced pipeline based on ``request.mode``.
    """
    try:
        # Domain-aware path (v3): delegate to adapter-based engine
        if request.domain is not None:
            return _domain_engine.rank(request)
        # Legacy paths
        if request.mode == RankingMode.SIMPLE:
            return _rank_simple(request)
        return _ranking_engine.rank(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ranking failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
