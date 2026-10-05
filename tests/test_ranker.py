from datetime import datetime, timedelta, timezone

from src.models.schemas import NewsItem
from src.processors.ranker import rank


def test_top_k_after_scores_and_stable_ties():
    now = datetime.now(timezone.utc)
    low = NewsItem("A", "low", "https://a", now, "", topic="ai", hot_score=1)
    high = NewsItem("B", "high", "https://b", now - timedelta(hours=2), "", topic="ai", hot_score=10)
    tie = NewsItem("C", "tie", "https://c", now, "", topic="ai", hot_score=10)
    other = NewsItem("D", "other", "https://d", now, "", topic="python", hot_score=100)
    assert rank([low, high, other, tie], "ai", 2) == [tie, high]
