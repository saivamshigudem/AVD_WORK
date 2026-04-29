"""Load code files from workspace for analysis."""
from pathlib import Path
from typing import List, Dict, Optional
import logging
import fnmatch

logger = logging.getLogger(__name__)


class CodeLoader:
    """Loads code files from the workspace."""
    
    def __init__(self, workspace_path: Path, config: Dict):
        """Initialize code loader.
        
        Args:
            workspace_path: Path to workspace root
            config: Configuration dictionary
        """
        self.workspace_path = Path(workspace_path)
        self.config = config
        self.exclude_patterns = config.get("code_analysis", {}).get("exclude_patterns", [])
        self.include_extensions = config.get("code_analysis", {}).get("include_extensions", [])
        self.max_files = config.get("code_analysis", {}).get("max_files_per_review", 50)
    
    def load_changed_files(self, git_repo_path: Optional[Path] = None) -> List[Dict[str, str]]:
        """Load changed files from git repository.
        
        Args:
            git_repo_path: Path to git repository (defaults to workspace_path)
            
        Returns:
            List of dictionaries with 'path' and 'content' keys
        """
        try:
            from git import Repo
            
            repo_path = git_repo_path or self.workspace_path
            repo = Repo(repo_path)
            
            # Get changed files (unstaged + staged)
            changed_files = []
            
            # Unstaged changes
            for item in repo.index.diff(None):
                if item.a_path:
                    file_path = self.workspace_path / item.a_path
                    if self._should_include_file(file_path):
                        content = self._read_file_safe(file_path)
                        if content:
                            changed_files.append({
                                "path": str(file_path.relative_to(self.workspace_path)),
                                "content": content,
                                "status": "modified"
                            })
            
            # Staged changes
            for item in repo.index.diff("HEAD"):
                if item.a_path:
                    file_path = self.workspace_path / item.a_path
                    if self._should_include_file(file_path) and not any(
                        f["path"] == str(file_path.relative_to(self.workspace_path))
                        for f in changed_files
                    ):
                        content = self._read_file_safe(file_path)
                        if content:
                            changed_files.append({
                                "path": str(file_path.relative_to(self.workspace_path)),
                                "content": content,
                                "status": "staged"
                            })
            
            # Limit number of files
            if len(changed_files) > self.max_files:
                logger.warning(f"Limiting to {self.max_files} files (found {len(changed_files)})")
                changed_files = changed_files[:self.max_files]
            
            return changed_files
            
        except ImportError:
            logger.error("GitPython not installed. Cannot load changed files.")
            return []
        except Exception as e:
            logger.error(f"Error loading changed files: {str(e)}")
            return []
    
    def load_files_by_paths(self, file_paths: List[str]) -> List[Dict[str, str]]:
        """Load specific files by their paths.
        
        Args:
            file_paths: List of file paths (relative to workspace)
            
        Returns:
            List of dictionaries with 'path' and 'content' keys
        """
        files = []
        
        for file_path_str in file_paths:
            file_path = self.workspace_path / file_path_str
            
            if not file_path.exists():
                logger.warning(f"File not found: {file_path}")
                continue
            
            if not self._should_include_file(file_path):
                logger.debug(f"Skipping excluded file: {file_path}")
                continue
            
            content = self._read_file_safe(file_path)
            if content:
                files.append({
                    "path": str(file_path.relative_to(self.workspace_path)),
                    "content": content
                })
        
        return files
    
    def load_all_code_files(self) -> List[Dict[str, str]]:
        """Load all code files from workspace.
        
        Returns:
            List of dictionaries with 'path' and 'content' keys
        """
        files = []
        
        for file_path in self._walk_directory(self.workspace_path):
            if self._should_include_file(file_path):
                content = self._read_file_safe(file_path)
                if content:
                    files.append({
                        "path": str(file_path.relative_to(self.workspace_path)),
                        "content": content
                    })
                    
                    if len(files) >= self.max_files:
                        logger.warning(f"Reached max files limit: {self.max_files}")
                        break
        
        return files
    
    def _walk_directory(self, directory: Path):
        """Walk directory and yield file paths.
        
        Args:
            directory: Directory to walk
            
        Yields:
            File paths
        """
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    yield item
        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in analysis.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file should be included
        """
        # Check extension
        if self.include_extensions:
            if not any(file_path.suffix == ext for ext in self.include_extensions):
                return False
        
        # Check exclude patterns
        file_path_str = str(file_path.relative_to(self.workspace_path))
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path_str, pattern) or fnmatch.fnmatch(str(file_path), pattern):
                return False
        
        return True
    
    def _read_file_safe(self, file_path: Path, max_size: int = 100000) -> Optional[str]:
        """Safely read file content.
        
        Args:
            file_path: Path to file
            max_size: Maximum file size to read (bytes)
            
        Returns:
            File content or None if error
        """
        try:
            if file_path.stat().st_size > max_size:
                logger.warning(f"File too large, skipping: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return None

