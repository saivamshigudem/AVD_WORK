"""Configuration loader for Peer Review Agent."""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any
import json


class ConfigLoader:
    """Loads and manages configuration from YAML and environment variables."""
    
    def __init__(self, config_path: str = "config.yaml", env_path: str = ".env"):
        """Initialize configuration loader.
        
        Args:
            config_path: Path to YAML configuration file
            env_path: Path to .env file
        """
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self.config: Dict[str, Any] = {}
        self.guidelines: Dict[str, Any] = {}
        
        # Load environment variables
        if self.env_path.exists():
            load_dotenv(self.env_path)
        
        # Load YAML config
        self._load_config()
        
        # Load guidelines
        self._load_guidelines()
        
        # Override with environment variables
        self._override_with_env()
    
    def _load_config(self):
        """Load configuration from YAML file."""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
    
    def _load_guidelines(self):
        """Load coding guidelines from JSON file."""
        guidelines_path = Path("guidelines.json")
        if guidelines_path.exists():
            with open(guidelines_path, 'r') as f:
                self.guidelines = json.load(f)
        else:
            raise FileNotFoundError(f"Guidelines file not found: {guidelines_path}")
    
    def _override_with_env(self):
        """Override configuration with environment variables."""
        # Azure DevOps
        if os.getenv("AZURE_DEVOPS_ORG"):
            self.config["azure_devops"]["organization"] = os.getenv("AZURE_DEVOPS_ORG")
        if os.getenv("AZURE_DEVOPS_PROJECT"):
            self.config["azure_devops"]["project"] = os.getenv("AZURE_DEVOPS_PROJECT")
        if os.getenv("AZURE_DEVOPS_PAT"):
            self.config["azure_devops"]["personal_access_token"] = os.getenv("AZURE_DEVOPS_PAT")
        
        # LLM
        if os.getenv("OPENAI_API_KEY"):
            self.config["llm"]["api_key"] = os.getenv("OPENAI_API_KEY")
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            self.config["llm"]["azure_endpoint"] = os.getenv("AZURE_OPENAI_ENDPOINT")
        if os.getenv("AZURE_OPENAI_API_KEY"):
            self.config["llm"]["azure_api_key"] = os.getenv("AZURE_OPENAI_API_KEY")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key path.
        
        Args:
            key_path: Dot-separated path to config value (e.g., "azure_devops.organization")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_guidelines(self) -> Dict[str, Any]:
        """Get coding guidelines.
        
        Returns:
            Dictionary containing all coding guidelines
        """
        return self.guidelines

