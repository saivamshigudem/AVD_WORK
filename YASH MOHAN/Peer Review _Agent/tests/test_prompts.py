
import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.code_analyzer import CodeAnalyzer

class TestPrompts(unittest.TestCase):
    
    def setUp(self):
        config = {"llm": {"provider": "openai", "api_key": "dummy"}}
        guidelines = {"general": "follow pep8"}
        
        # We need to mock _initialize_client to avoid error during init if openai missing or key invalid
        # But CodeAnalyzer.__init__ calls _initialize_client.
        # So we can subclass or mock the class.
        pass

    def test_system_prompt_structure(self):
        config = {"llm": {"provider": "openai", "api_key": "dummy"}}
        guidelines = {"general": "follow pep8"}
        
        # Patch init to avoid client connection
        with unittest.mock.patch.object(CodeAnalyzer, '_initialize_client', return_value=MagicMock()):
            analyzer = CodeAnalyzer(config, guidelines)
            
            messages = analyzer._create_analysis_messages(
                guidelines="GUIDELINES",
                user_stories="STORIES",
                code="CODE"
            )
            
            system_prompt = messages[0]["content"]
            
            # Check for new agentic phases
            self.assertIn("Phase 1: Deep Understanding & Planning", system_prompt)
            self.assertIn("Phase 2: Multi-Perspective Analysis", system_prompt)
            self.assertIn("Phase 3: Impact Analysis", system_prompt)
            self.assertIn("Phase 4: Self-Correction", system_prompt)
            
            # Check for thought_process in JSON structure
            self.assertIn('"thought_process": {', system_prompt)
            self.assertIn('"understanding":', system_prompt)
            self.assertIn('"impact_assessment":', system_prompt)
            
            print("Prompt verification successful!")

if __name__ == '__main__':
    unittest.main()
