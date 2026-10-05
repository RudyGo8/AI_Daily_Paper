from datetime import datetime, timedelta, timezone

from src.models.schemas import NewsItem
from src.processors.hot_scorer import HotScorer
from src.topics import TopicConfig

NOW = datetime(2026, 10, 4, 4, tzinfo=timezone.utc)


def item(title="MCP developer tool", hours=1, weight=3, **kwargs):
    return NewsItem("Source", title, "https://example.com/" + title,
                    NOW - timedelta(hours=hours), title, source_weight=weight, **kwargs)


def test_authority_freshness_and_independent_sources():
    topic = TopicConfig.from_config("agent", {"keywords": ["mcp", "agent"]})
    scorer = HotScorer(topic, NOW)
    official, ordinary, old = item(weight=5), item(weight=1), item(hours=18, weight=5)
    scorer.score_all([official, ordinary, old])
    assert official.hot_score > ordinary.hot_score
    assert official.hot_score > old.hot_score
    repeated = item(merged_sources=["A", "B", "C"], cluster_size=8)
    scorer.score_all([repeated])
    assert repeated.cross_source_score == 2
    single_source = item(merged_sources=["A"], cluster_size=8)
    scorer.score_all([single_source])
    assert single_source.cross_source_score == 0
    assert official.score_reasons


def test_topic_filter_does_not_allow_generic_ai_into_agent():
    topic = TopicConfig.from_config("agent", {"keywords": ["agent", "mcp"], "min_keyword_matches": 1})
    scorer = HotScorer(topic, NOW)
    assert scorer.matches(item("Claude Code MCP server"))
    assert not scorer.matches(item("AI model benchmark"))
    assert not scorer.matches(item("company roadmap"))  # MCP must match a word


def test_policy_uses_own_weights_and_exclusions():
    topic = TopicConfig.from_config("policy", {"keywords": ["人才"],
        "exclude_keywords": ["广告"], "score_weights": {"source": 2, "popularity": 0}})
    scorer = HotScorer(topic, NOW)
    policy = item("人才补贴政策", weight=5)
    scorer.score_all([policy])
    assert policy.source_score == 10
    assert not scorer.matches(item("人才培训广告"))


def test_growth_can_outweigh_old_total_stars():
    topic = TopicConfig.from_config("github", {})
    scorer = HotScorer(topic, NOW)
    old = item("old", metadata={"stars": 100000, "forks": 5000})
    growing = item("new", metadata={"stars": 1000, "forks": 50, "star_growth": 600,
                                    "star_growth_days": 7, "release_at": NOW.isoformat()})
    scorer.score_all([old, growing])
    assert growing.popularity_score > old.popularity_score


def test_news_filters_entertainment_headlines_without_blocking_policy_body():
    topic = TopicConfig.from_config("news", {"keywords": ["科技", "政策"], "min_keyword_matches": 1,
        "exclude_title_keywords": ["电影", "球赛", "限时优惠"]})
    scorer = HotScorer(topic, NOW)
    assert not scorer.matches(item("科技大片电影明日上映"))
    assert not scorer.matches(item("科技手机限时优惠"))
    assert scorer.matches(item("数字产业政策发布", content="政策涵盖电影制作和人工智能产业"))
