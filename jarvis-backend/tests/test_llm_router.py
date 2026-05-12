"""Test the LLM router."""
import pytest
from app.services.llm_router import LLMRouter


@pytest.fixture
def router():
    return LLMRouter()


class TestLLMRouter:
    def test_route_complex_task(self, router):
        model = router.route("plan a weekly meal schedule")
        assert model == "gpt-4.1-nano"

    def test_route_simple_task(self, router):
        model = router.route("classify this text as spam or not")
        assert model == "gemini"

    def test_route_default_to_gemini(self, router):
        model = router.route("hello how are you")
        assert model == "gemini"

    def test_route_analysis(self, router):
        model = router.route("analyze the market trends for this quarter")
        assert model == "gpt-4.1-nano"

    def test_route_extraction(self, router):
        model = router.route("extract the date and price from this text")
        assert model == "gemini"

    def test_route_multi_step(self, router):
        model = router.route("multi-step task involving several operations")
        assert model == "gpt-4.1-nano"

    def test_route_summarization(self, router):
        model = router.route("summarize this article in 3 sentences")
        assert model == "gemini"

    def test_complex_keywords(self, router):
        assert "plan" in router.COMPLEX_KEYWORDS
        assert "analyze" in router.COMPLEX_KEYWORDS
        assert "reason" in router.COMPLEX_KEYWORDS

    def test_simple_keywords(self, router):
        assert "classify" in router.SIMPLE_KEYWORDS
        assert "extract" in router.SIMPLE_KEYWORDS
        assert "summarize" in router.SIMPLE_KEYWORDS
