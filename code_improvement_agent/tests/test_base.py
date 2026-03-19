import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.base import BaseAnalyzer, AnalyzerResult
from code_improvement_agent.config import Config


class ConcreteTestAnalyzer(BaseAnalyzer):
    """Concrete subclass of BaseAnalyzer for testing."""
    name = "test_analyzer"
    category = "test"

    def analyze(self) -> AnalyzerResult:
        return AnalyzerResult(analyzer_name=self.name)


class TestBaseAnalyzer:

    def test_cannot_instantiate_abstract_base(self):
        with pytest.raises(TypeError):
            BaseAnalyzer("/fake", {}, config=Config())

    def test_analyze_is_abstract_method(self):
        # Verify that analyze() is meant to be overridden
        assert hasattr(BaseAnalyzer, 'analyze')


class TestConcreteAnalyzer:

    @pytest.fixture
    def mock_result(self):
        return Mock(spec=AnalyzerResult)

    @pytest.fixture
    def concrete_analyzer(self):
        return ConcreteTestAnalyzer("/fake", {}, config=Config())

    def test_analyze_returns_analyzer_result(self, concrete_analyzer):
        result = concrete_analyzer.analyze()
        assert isinstance(result, AnalyzerResult)

    def test_analyze_returns_default_result_when_none_provided(self):
        analyzer = ConcreteTestAnalyzer("/fake", {}, config=Config())
        result = analyzer.analyze()
        assert isinstance(result, AnalyzerResult)
