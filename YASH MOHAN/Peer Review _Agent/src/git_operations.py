"""Git operations for committing and pushing changes."""
from pathlib import Path
from typing import Optional, List, Dict
import logging
from git import Repo, GitCommandError
from git.exc import InvalidGitRepositoryError

logger = logging.getLogger(__name__)


class GitOperations:
    """Handles Git operations for the peer review agent."""
    
    def __init__(self, repo_path: Path):
        """Initialize Git operations.
        
        Args:
            repo_path: Path to git repository
        """
        self.repo_path = Path(repo_path)
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise ValueError(f"Not a valid git repository: {self.repo_path}")
    
    def get_current_branch(self) -> str:
        """Get current branch name.
        
        Returns:
            Current branch name
        """
        try:
            return self.repo.active_branch.name
        except Exception as e:
            logger.error(f"Error getting current branch: {str(e)}")
            return "unknown"
    
    def create_branch(self, branch_name: str, base_branch: Optional[str] = None) -> bool:
        """Create a new branch.
        
        Args:
            branch_name: Name of new branch
            base_branch: Base branch name (defaults to current branch)
            
        Returns:
            True if successful
        """
        try:
            if base_branch:
                # Checkout base branch first
                self.repo.git.checkout(base_branch)
            
            # Create and checkout new branch
            self.repo.git.checkout('-b', branch_name)
            logger.info(f"Created and checked out branch: {branch_name}")
            return True
            
        except GitCommandError as e:
            logger.error(f"Error creating branch {branch_name}: {str(e)}")
            return False
    
    def stage_files(self, file_paths: Optional[List[str]] = None) -> bool:
        """Stage files for commit.
        
        Args:
            file_paths: List of file paths to stage (None = all changes)
            
        Returns:
            True if successful
        """
        try:
            if file_paths:
                for file_path in file_paths:
                    self.repo.git.add(file_path)
            else:
                self.repo.git.add(A=True)  # Stage all changes
            
            logger.info(f"Staged files: {file_paths or 'all'}")
            return True
            
        except GitCommandError as e:
            logger.error(f"Error staging files: {str(e)}")
            return False
    
    def commit(self, message: str, author: Optional[str] = None) -> bool:
        """Commit staged changes.
        
        Args:
            message: Commit message
            author: Author string (format: "Name <email>")
            
        Returns:
            True if successful
        """
        try:
            commit_kwargs = {}
            if author:
                commit_kwargs['author'] = author
            
            self.repo.index.commit(message, **commit_kwargs)
            logger.info(f"Committed changes: {message[:50]}...")
            return True
            
        except GitCommandError as e:
            logger.error(f"Error committing: {str(e)}")
            return False
    
    def push(self, remote: str = "origin", branch: Optional[str] = None, force: bool = False) -> bool:
        """Push changes to remote.
        
        Args:
            remote: Remote name
            branch: Branch name (defaults to current branch)
            force: Whether to force push
            
        Returns:
            True if successful
        """
        try:
            branch = branch or self.get_current_branch()
            
            if force:
                self.repo.git.push(remote, branch, force=True)
            else:
                self.repo.git.push(remote, branch)
            
            logger.info(f"Pushed branch {branch} to {remote}")
            return True
            
        except GitCommandError as e:
            logger.error(f"Error pushing to {remote}/{branch}: {str(e)}")
            return False
    
    def get_changed_files(self) -> List[Dict[str, str]]:
        """Get list of changed files.
        
        Returns:
            List of dictionaries with 'path' and 'status' keys
        """
        changed_files = []
        
        try:
            # Unstaged changes
            for item in self.repo.index.diff(None):
                if item.a_path:
                    changed_files.append({
                        "path": item.a_path,
                        "status": "modified"
                    })
            
            # Staged changes
            for item in self.repo.index.diff("HEAD"):
                if item.a_path and not any(f["path"] == item.a_path for f in changed_files):
                    changed_files.append({
                        "path": item.a_path,
                        "status": "staged"
                    })
            
        except Exception as e:
            logger.error(f"Error getting changed files: {str(e)}")
        
        return changed_files
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get remote URL.
        
        Args:
            remote: Remote name
            
        Returns:
            Remote URL or None
        """
        try:
            return self.repo.remotes[remote].url
        except Exception as e:
            logger.error(f"Error getting remote URL: {str(e)}")
            return None

