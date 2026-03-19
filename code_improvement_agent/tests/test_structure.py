import pytest
from unittest.mock import Mock, patch
from code_improvement_agent.analyzers.structure import StructureAnalyzer
from code_improvement_agent.analyzers.base import AnalyzerResult
from code_improvement_agent.config import Config


class TestStructureAnalyzer:
    
    @pytest.fixture
    def analyzer(self):
        file_contents = {
            'main.py': 'print("hello")',
            'config.py': 'DATABASE_URL = "localhost"',
            'utils.py': 'def helper(): pass'
        }
        return StructureAnalyzer("/fake", file_contents, config=Config())

    @pytest.fixture
    def empty_analyzer(self):
        return StructureAnalyzer("/fake", {}, config=Config())

    @patch.object(StructureAnalyzer, '_check_flat_structure')
    @patch.object(StructureAnalyzer, '_check_mixed_concerns') 
    @patch.object(StructureAnalyzer, '_check_missing_packaging')
    @patch.object(StructureAnalyzer, '_check_config_separation')
    @patch.object(StructureAnalyzer, '_calculate_score')
    def test_analyze_calls_all_check_methods(self, mock_calc, mock_config, 
                                           mock_packaging, mock_mixed, mock_flat, analyzer):
        result = analyzer.analyze()
        
        files = list(analyzer.file_contents.keys())
        mock_flat.assert_called_once_with(files, result)
        mock_mixed.assert_called_once_with(files, result)
        mock_packaging.assert_called_once_with(files, result)
        mock_config.assert_called_once_with(files, result)
        mock_calc.assert_called_once_with(result)

    def test_analyze_returns_analyzer_result_with_correct_name(self, analyzer):
        result = analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        assert result.analyzer_name == analyzer.name

    @patch.object(StructureAnalyzer, '_check_flat_structure')
    @patch.object(StructureAnalyzer, '_check_mixed_concerns')
    @patch.object(StructureAnalyzer, '_check_missing_packaging') 
    @patch.object(StructureAnalyzer, '_check_config_separation')
    @patch.object(StructureAnalyzer, '_calculate_score')
    def test_analyze_passes_same_result_object_to_all_methods(self, mock_calc, mock_config,
                                                             mock_packaging, mock_mixed, 
                                                             mock_flat, analyzer):
        analyzer.analyze()
        
        # Get the result object passed to each method
        flat_result = mock_flat.call_args[0][1]
        mixed_result = mock_mixed.call_args[0][1]
        packaging_result = mock_packaging.call_args[0][1]
        config_result = mock_config.call_args[0][1]
        calc_result = mock_calc.call_args[0][0]
        
        # All should be the same object
        assert flat_result is mixed_result is packaging_result is config_result is calc_result

    def test_analyze_with_empty_file_contents(self, empty_analyzer):
        result = empty_analyzer.analyze()
        
        assert isinstance(result, AnalyzerResult)
        assert result.analyzer_name == empty_analyzer.name

    @patch.object(StructureAnalyzer, '_check_flat_structure')
    @patch.object(StructureAnalyzer, '_check_mixed_concerns')
    @patch.object(StructureAnalyzer, '_check_missing_packaging')
    @patch.object(StructureAnalyzer, '_check_config_separation')
    @patch.object(StructureAnalyzer, '_calculate_score')
    def test_analyze_passes_empty_file_list_when_no_files(self, mock_calc, mock_config,
                                                         mock_packaging, mock_mixed, 
                                                         mock_flat, empty_analyzer):
        empty_analyzer.analyze()
        
        files_passed = mock_flat.call_args[0][0]
        assert files_passed == []

    @patch.object(StructureAnalyzer, '_check_flat_structure', side_effect=Exception("Test error"))
    def test_analyze_propagates_exceptions_from_check_methods(self, mock_flat, analyzer):
        with pytest.raises(Exception, match="Test error"):
            analyzer.analyze()

    def test_analyze_preserves_file_order(self, analyzer):
        with patch.object(StructureAnalyzer, '_check_flat_structure') as mock_flat:
            analyzer.analyze()
            
            files_passed = mock_flat.call_args[0][0]
            original_files = list(analyzer.file_contents.keys())
            assert files_passed == original_files
