"""Code analysis module using LLM with RAG approach."""
import os
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Progress bar
from tqdm.asyncio import tqdm_asyncio

# Token counting
import tiktoken

# OpenAI
try:
    from openai import AsyncOpenAI, OpenAI, OpenAIError, RateLimitError, APIError, AuthenticationError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """Analyzes code against user stories and coding guidelines using LLM."""
    
    def __init__(self, config: Dict[str, Any], guidelines: Dict[str, Any]):
        """Initialize code analyzer.
        
        Args:
            config: Configuration dictionary
            guidelines: Coding guidelines dictionary
        """
        self.config = config
        self.guidelines = guidelines
        self.workspace_path = Path.cwd()
        self.model_name = self.config.get("llm", {}).get("model", "gpt-4-turbo-preview")
        self.max_tokens = self.config.get("llm", {}).get("max_tokens", 4000)
        self.temperature = self.config.get("llm", {}).get("temperature", 0.1)
        
        # metrics
        self.total_tokens_used = 0
        self.total_cost = 0.0
        
        # Initialize Async Client
        self.client = self._initialize_client()

    def _initialize_client(self) -> Optional[Union[AsyncOpenAI, Any]]:
        """Initialize Async OpenAI client."""
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not installed. Please install 'openai'.")

        llm_config = self.config.get("llm", {})
        provider = llm_config.get("provider", "openai")
        api_key = llm_config.get("api_key", os.getenv("OPENAI_API_KEY"))
        
        if not api_key:
            raise ValueError("LLM API key not found in config or environment variables")
            
        if provider == "openai":
            return AsyncOpenAI(api_key=api_key)
        elif provider == "azure_openai":
            return AsyncOpenAI(
                api_key=llm_config.get("azure_api_key", api_key),
                base_url=llm_config.get("azure_endpoint"),
                api_version=llm_config.get("azure_api_version", "2024-02-15-preview")
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def analyze_code(
        self,
        code_files: List[Dict[str, str]],
        user_stories: List[Dict],
        changed_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Analyze code files in parallel.
        
        Args:
            code_files: List of dictionaries with 'path' and 'content' keys
            user_stories: List of user story dictionaries
            changed_files: Optional list of changed file paths
            
        Returns:
            Analysis results dictionary
        """
        # Reset metrics
        self.total_tokens_used = 0
        self.total_cost = 0.0

        return asyncio.run(self._analyze_files_parallel(code_files, user_stories))

    async def _analyze_files_parallel(
        self, 
        code_files: List[Dict[str, str]], 
        user_stories: List[Dict]
    ) -> Dict[str, Any]:
        """Run analysis on multiple files in parallel."""
        
        formatted_guidelines = self._format_guidelines()
        formatted_user_stories = self._format_user_stories(user_stories)
        
        tasks = []
        for file_info in code_files:
            tasks.append(
                self._analyze_single_file(
                    file_info, 
                    formatted_guidelines, 
                    formatted_user_stories
                )
            )

        # Execute tasks with progress bar
        print(f"\nAnalyzing {len(code_files)} files in parallel...")
        results = await tqdm_asyncio.gather(*tasks, desc="Analyzing files")
        
        # Aggregate results
        aggregated_analysis = {
            "summary": {
                "total_issues": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "user_story_alignment": "aligned"  # optimistic default
            },
            "issues": [],
            "user_story_compliance": []
        }
        
        failed_files = 0
        
        for res in results:
            if res.get("status") == "error":
                failed_files += 1
                continue
                
            analysis = res.get("analysis", {})
            
            # Aggregate content
            if "issues" in analysis:
                aggregated_analysis["issues"].extend(analysis["issues"])
                
            # Naive summation of summary stats
            if "summary" in analysis:
                for k in ["total_issues", "critical", "high", "medium", "low"]:
                    aggregated_analysis["summary"][k] += analysis["summary"].get(k, 0)
            
            # Merge compliance (this might duplicate if multiple files review same stories)
            # Strategy: We'll take the distinct set of compliance notes or just append
            # Merge compliance (this might duplicate if multiple files review same stories)
            # Strategy: We'll take the distinct set of compliance notes or just append
            if "user_story_compliance" in analysis:
                # Deduplication logic could go here, for now just extend
                 aggregated_analysis["user_story_compliance"].extend(analysis["user_story_compliance"])

            # Capture thought process (Use the most recent one that has content, or merge)
            if "thought_process" in analysis:
                # For now, we will simply assign it. In a multi-file scenario, this means 
                # we get the thought process of the last analyzed file, which is a known limitation 
                # but ensures the field exists for the report. 
                # A better approach would be to aggregate per file, but ReportGenerator expects a single dict.
                aggregated_analysis["thought_process"] = analysis["thought_process"]

        return {
            "status": "success",
            "analysis": aggregated_analysis,
            "raw_response": "Parallel Execution",
            "files_analyzed": len(code_files),
            "failed_files": failed_files,
            "metrics": {
                "total_tokens": self.total_tokens_used,
                "estimated_cost_usd": self.total_cost
            }
        }

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _analyze_single_file(
        self, 
        file_info: Dict[str, str], 
        guidelines_str: str, 
        user_stories_str: str
    ) -> Dict[str, Any]:
        """Analyze a single file asynchronously."""
        
        file_path = file_info.get("path", "unknown")
        content = file_info.get("content", "")
        
        # Language specific guidelines
        lang_guidelines = self._get_language_guidelines(file_path)
        full_guidelines = f"{guidelines_str}\n\n{lang_guidelines}"

        # Create Prompt
        prompt_messages = self._create_analysis_messages(
            full_guidelines, 
            user_stories_str, 
            f"File: {file_path}\n```\n{content}\n```"
        )
        
        try:
            # Check context length (approx)
            if self._estimate_tokens(str(prompt_messages)) > 100000:
                logger.warning(f"File {file_path} is too large. Skipping analysis.")
                return {"status": "error", "error": "Context limit exceeded"}

            # Call OpenAI with JSON mode
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=prompt_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"}
            )
            
            # Metrics
            if response.usage:
                self.total_tokens_used += response.usage.total_tokens
                # Approx cost calc (GPT-4 Turbo pricing: $10/1M input, $30/1M output)
                input_cost = (response.usage.prompt_tokens / 1_000_000) * 10.0
                output_cost = (response.usage.completion_tokens / 1_000_000) * 30.0
                self.total_cost += (input_cost + output_cost)

            result_text = response.choices[0].message.content
            analysis = json.loads(result_text)
            
            # Add file meta to issues if missing
            if "issues" in analysis:
                for issue in analysis["issues"]:
                    if "file" not in issue:
                        issue["file"] = file_path

            return {
                "status": "success", 
                "analysis": analysis,
                "file": file_path
            }

        except AuthenticationError:
            logger.error("Authentication failed. Check your API Key.")
            return {"status": "error", "error": "Authentication failed"}
        except OpenAIError as e:
            logger.error(f"OpenAI API Error for {file_path}: {e}")
            return {"status": "error", "error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"JSON Parse Error for {file_path}: {e}")
            return {"status": "error", "error": "Invalid JSON response"}
        except Exception as e:
            logger.error(f"Unknown error for {file_path}: {e}")
            return {"status": "error", "error": str(e)}

    def _get_language_guidelines(self, file_path: str) -> str:
        """Get language-specific guidelines based on extension."""
        ext = Path(file_path).suffix.lower()
        lang_key = ""
        if ext == ".py":
            lang_key = "python"
        elif ext in [".js", ".jsx"]:
            lang_key = "javascript"
        elif ext in [".ts", ".tsx"]:
            lang_key = "typescript"
            
        if lang_key and "languages" in self.guidelines:
             spec = self.guidelines["languages"].get(lang_key)
             if spec:
                 return f"LANGUAGE SPECIFIC GUIDELINES ({lang_key}):\n{json.dumps(spec, indent=2)}"
        return ""

    def _estimate_tokens(self, text: str) -> int:
        """Estimate tokens using tiktoken."""
        try:
            encoding = tiktoken.encoding_for_model(self.model_name)
            return len(encoding.encode(text))
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4  # fallback

    def _format_guidelines(self) -> str:
        """Format base coding guidelines."""
        # exclude languages key from base dump
        base_guidelines = {k: v for k, v in self.guidelines.items() if k != "languages"}
        return f"CODING GUIDELINES:\n\n{json.dumps(base_guidelines, indent=2)}"

    def _format_user_stories(self, user_stories: List[Dict]) -> str:
        """Format user stories."""
        if not user_stories:
            return "No user stories provided."
        
        stories_text = "USER STORIES:\n\n"
        for story in user_stories:
            stories_text += f"Story ID: {story.get('id', 'N/A')}\n"
            stories_text += f"Title: {story.get('title', 'N/A')}\n"
            stories_text += f"Acceptance Criteria: {story.get('acceptance_criteria', 'N/A')}\n"
            stories_text += "-" * 30 + "\n"
        return stories_text

    def _create_analysis_messages(self, guidelines: str, user_stories: str, code: str):
        """Create structured messages for Chat API."""
        system_prompt = """You are an expert, agentic code reviewer.
Analyze the code using a multi-step reasoning process before providing the final checking.

Phase 1: Deep Understanding & Planning
- Map User Story Acceptance Criteria to specific code blocks/functions.
- Trace data flow and logic.
- Identify potential missing contexts or imports.

Phase 2: Multi-Perspective Analysis
- Security: Check for injection, auth bypass, and secrets.
- Performance: Check for O(n^2) loops, memory leaks, and redundant calls.
- Compliance: Verify strict alignment with the provided User Stories.

Phase 3: Impact Analysis
- Determine the "Blast Radius" of changes.
- Check backward compatibility.

Phase 4: Self-Correction
- Review your own suggested fixes for syntax errors and import issues.
- Discard any fixes that do not strictly satisfy the acceptance criteria.

Output must be a valid JSON object with the following structure:
{
  "thought_process": {
    "understanding": "Clear summary of what the code does",
    "user_story_mapping": "How the code relates to the stories",
    "gap_analysis": "What is missing or incorrect",
    "security_review": "Security findings",
    "impact_assessment": "Potential side effects of changes"
  },
  "summary": {
    "total_issues": 0,
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0,
    "user_story_alignment": "aligned" | "partially_aligned" | "misaligned"
  },
  "issues": [
    {
      "file": "filename",
      "line": 1,
      "type": "guideline_violation",
      "severity": "critical|high|medium|low",
      "description": "text",
      "current_code": "text",
      "suggested_fix": "text",
      "explanation": "text including why this fix is safe"
    }
  ],
  "user_story_compliance": [
    {
      "story_id": 123,
      "status": "compliant|partially_compliant|non_compliant",
      "missing_criteria": [],
      "notes": "text"
    }
  ]
}
"""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{guidelines}\n\n{user_stories}\n\n{code}"}
        ]
