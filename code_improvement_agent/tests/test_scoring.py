import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.scoring import compute_repo_score, classify_tag, recommend_action


class MockConfig:
    def __init__(self, weights=None):
        self.scoring = {
            "weights": weights or {
                "quality": 0.3,
                "structure": 0.2,
                "security": 0.3,
                "usefulness": 0.2
            }
        }


class MockAnalyzerResult:
    def __init__(self, analyzer_name, score):
        self.analyzer_name = analyzer_name
        self.score = score


class MockRepoScore:
    def __init__(self):
        self.quality = 0
        self.structure = 0
        self.security = 0
        self.usefulness = 0
        self.overall = 0


@pytest.fixture
def default_config():
    return MockConfig()


@pytest.fixture
def mock_repo_score():
    with patch('code_improvement_agent.scoring.RepoScore', MockRepoScore):
        yield


class TestComputeRepoScore:
    
    def test_compute_repo_score_with_all_analyzer_results(self, mock_repo_score):
        analyzer_results = [
            MockAnalyzerResult("clarity", 8.0),
            MockAnalyzerResult("functionality", 7.0),
            MockAnalyzerResult("structure", 6.0),
            MockAnalyzerResult("reusability", 9.0),
            MockAnalyzerResult("security", 5.0),
            MockAnalyzerResult("automation", 8.0)
        ]
        config = MockConfig()
        
        score = compute_repo_score(analyzer_results, config)
        
        assert score.quality == 7.5  # (8 + 7) / 2
        assert score.structure == 7.5  # (6 + 9) / 2
        assert score.security == 5.0
        assert score.usefulness == 7.8  # (8 + 7.5) / 2, rounded
        assert score.overall == 6.9  # weighted sum, rounded
    
    def test_compute_repo_score_with_missing_analyzers(self, mock_repo_score):
        analyzer_results = [
            MockAnalyzerResult("clarity", 6.0),
            MockAnalyzerResult("security", 8.0)
        ]
        config = MockConfig()
        
        score = compute_repo_score(analyzer_results, config)
        
        assert score.quality == 8.0  # (6 + 10) / 2, functionality defaults to 10
        assert score.structure == 10.0  # both default to 10
        assert score.security == 8.0
        assert score.usefulness == 9.0  # (10 + 8.0) / 2
    
    def test_compute_repo_score_with_empty_results(self, mock_repo_score):
        analyzer_results = []
        config = MockConfig()
        
        score = compute_repo_score(analyzer_results, config)
        
        assert score.quality == 10.0
        assert score.structure == 10.0
        assert score.security == 10.0
        assert score.usefulness == 10.0
        assert score.overall == 10.0
    
    def test_compute_repo_score_case_insensitive_analyzer_names(self, mock_repo_score):
        analyzer_results = [
            MockAnalyzerResult("CLARITY", 5.0),
            MockAnalyzerResult("Security", 7.0)
        ]
        config = MockConfig()
        
        score = compute_repo_score(analyzer_results, config)
        
        assert score.quality == 7.5  # (5 + 10) / 2
        assert score.security == 7.0
    
    @patch('code_improvement_agent.scoring.load_config')
    def test_compute_repo_score_loads_default_config(self, mock_load_config, mock_repo_score):
        mock_load_config.return_value = MockConfig()
        analyzer_results = [MockAnalyzerResult("clarity", 6.0)]
        
        score = compute_repo_score(analyzer_results)
        
        mock_load_config.assert_called_once()
        assert score.quality == 8.0
    
    def test_compute_repo_score_with_custom_weights(self, mock_repo_score):
        custom_weights = {
            "quality": 0.4,
            "structure": 0.3,
            "security": 0.2,
            "usefulness": 0.1
        }
        config = MockConfig(custom_weights)
        analyzer_results = [
            MockAnalyzerResult("clarity", 8.0),
            MockAnalyzerResult("functionality", 6.0)
        ]
        
        score = compute_repo_score(analyzer_results, config)
        
        expected_overall = 7.0 * 0.4 + 10.0 * 0.3 + 10.0 * 0.2 + 8.5 * 0.1
        assert score.overall == round(expected_overall, 1)


class TestClassifyTag:
    
    def test_classify_tag_biz_signals_in_content(self):
        file_contents = {
            "app.py": "def process_payment():\n    pass",
            "user.py": "class User:\n    def login(self):\n        pass"
        }
        
        result = classify_tag(file_contents, "my-repo")
        
        assert result == "biz"
    
    def test_classify_tag_ops_signals_in_repo_name(self):
        file_contents = {"main.py": "print('hello')"}
        
        result = classify_tag(file_contents, "docker-deployment")
        
        assert result == "ops"
    
    def test_classify_tag_lab_signals(self):
        file_contents = {
            "experiment.py": "# This is a test experiment",
            "prototype.py": "def demo_function():\n    pass"
        }
        
        result = classify_tag(file_contents, "research-project")
        
        assert result == "lab"
    
    def test_classify_tag_util_signals(self):
        file_contents = {
            "helper.py": "def utility_function():\n    pass",
            "tool.py": "import argparse"
        }
        
        result = classify_tag(file_contents, "my-tools")
        
        assert result == "util"
    
    def test_classify_tag_no_signals_defaults_to_util(self):
        file_contents = {
            "random.py": "def some_function():\n    return 42"
        }
        
        result = classify_tag(file_contents, "random-repo")
        
        assert result == "util"
    
    def test_classify_tag_multiple_signals_picks_highest_score(self):
        file_contents = {
            "payment.py": "def checkout(): pass",  # 2 biz signals
            "deploy.py": "def deploy(): pass"      # 1 ops signal
        }
        
        result = classify_tag(file_contents, "business-automation")
        
        assert result == "biz"
    
    def test_classify_tag_case_insensitive(self):
        file_contents = {
            "PAYMENT.PY": "CUSTOMER_DATA = {}"
        }
        
        result = classify_tag(file_contents, "BUSINESS-APP")
        
        assert result == "biz"
    
    def test_classify_tag_empty_content(self):
        file_contents = {}
        
        result = classify_tag(file_contents, "empty-repo")
        
        assert result == "util"


class TestRecommendAction:
    
    def test_recommend_action_promote_high_quality_many_files(self):
        score = MockRepoScore()
        score.overall = 8.5
        
        result = recommend_action(score, 5)
        
        assert result == "promote"
    
    def test_recommend_action_promote_exact_threshold(self):
        score = MockRepoScore()
        score.overall = 7.5
        
        result = recommend_action(score, 4)
        
        assert result == "promote"
    
    def test_recommend_action_maintain_decent_quality(self):
        score = MockRepoScore()
        score.overall = 6.0
        
        result = recommend_action(score, 5)
        
        assert result == "maintain"
    
    def test_recommend_action_maintain_exact_threshold(self):
        score = MockRepoScore()
        score.overall = 4.5
        
        result = recommend_action(score, 3)
        
        assert result == "maintain"
    
    def test_recommend_action_maintain_low_score_few_files(self):
        score = MockRepoScore()
        score.overall = 3.0
        
        result = recommend_action(score, 2)
        
        assert result == "maintain"
    
    def test_recommend_action_maintain_low_score_exact_file_threshold(self):
        score = MockRepoScore()
        score.overall = 1.0
        
        result = recommend_action(score, 2)
        
        assert result == "maintain"
    
    def test_recommend_action_archive_very_low_quality(self):
        score = MockRepoScore()
        score.overall = 1.5
        
        result = recommend_action(score, 5)
        
        assert result == "archive"
    
    def test_recommend_action_archive_exact_threshold(self):
        score = MockRepoScore()
        score.overall = 2.4
        
        result = recommend_action(score, 5)
        
        assert result == "archive"
    
    def test_recommend_action_high_quality_few_files_no_promote(self):
        score = MockRepoScore()
        score.overall = 9.0
        
        result = recommend_action(score, 3)
        
        assert result == "maintain"
