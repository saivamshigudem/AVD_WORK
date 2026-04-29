import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.fix_applier import FixApplier
from src.code_analyzer import CodeAnalyzer
from src.user_story_fetcher import UserStoryFetcher

class TestImprovements(unittest.TestCase):
    
    def setUp(self):
        self.workspace = Path("test_workspace")
        self.fix_applier = FixApplier(self.workspace)
        
    def test_fuzzy_matching(self):
        """Test that fuzzy matching works when exact match fails."""
        lines = [
            "def hello():",
            "    print('hello world')",
            "    return True"
        ]
        
        # Slightly different code (different whitespace)
        current_code = "    print( 'hello world' )"
        suggested_fix = "    print('Hello World')"
        
        # Mock the file reading/writing part since we are testing the logic directly
        # We'll test _apply_fuzzy_fix directly
        
        result = self.fix_applier._apply_fuzzy_fix(lines, 1, current_code, suggested_fix)
        
        self.assertTrue(result, "Fuzzy match should have succeeded")
        self.assertEqual(lines[1], suggested_fix, "Line should have been updated")

    def test_json_parsing_robustness(self):
        """Test that JSON parsing handles markdown and extra text."""
        # Mock config to avoid API key error
        config = {"llm": {"api_key": "dummy"}}
        with patch("src.code_analyzer.CodeAnalyzer._initialize_llm"):
            analyzer = CodeAnalyzer(config, {})
            
            # Case 1: Markdown code block
            response1 = """Here is the analysis:
```json
{
    "summary": {"total_issues": 1},
    "issues": []
}
```
Hope this helps!"""
            result1 = analyzer._parse_analysis_response(response1)
            self.assertEqual(result1["summary"]["total_issues"], 1)
            
            # Case 2: No code block, just text
            response2 = """
{
    "summary": {"total_issues": 2},
    "issues": []
}
"""
            result2 = analyzer._parse_analysis_response(response2)
            self.assertEqual(result2["summary"]["total_issues"], 2)

    def test_branch_parsing(self):
        """Test improved branch name parsing."""
        fetcher = UserStoryFetcher(MagicMock(), "test_project")
        
        # Mock fetch_by_id to return something so we know it tried to fetch
        fetcher.fetch_by_id = MagicMock(return_value={"id": 123})
        
        # Test new patterns
        fetcher.fetch_by_branch("feature/123-new-feature")
        fetcher.fetch_by_id.assert_called_with(123)
        
        fetcher.fetch_by_branch("bugfix/US456")
        fetcher.fetch_by_id.assert_called_with(456)
        
        fetcher.fetch_by_branch("12345-hotfix") # 3+ digits at start
        fetcher.fetch_by_id.assert_called_with(12345)

if __name__ == '__main__':
    unittest.main()
