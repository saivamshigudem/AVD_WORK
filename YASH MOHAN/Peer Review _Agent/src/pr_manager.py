"""Manage pull requests in Azure DevOps."""
from azure.devops.v7_1.git.git_client import GitClient
from azure.devops.v7_1.git.models import (
    GitPullRequest,
    GitPullRequestSearchCriteria,
    CommentThread,
    Comment
)
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)


class PRManager:
    """Manages pull requests in Azure DevOps."""
    
    def __init__(self, git_client: GitClient, project: str, repository_id: str):
        """Initialize PR manager.
        
        Args:
            git_client: Azure DevOps Git client
            project: Project name
            repository_id: Repository ID or name
        """
        self.git_client = git_client
        self.project = project
        self.repository_id = repository_id
    
    def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: Optional[List[str]] = None
    ) -> Optional[GitPullRequest]:
        """Create a new pull request.
        
        Args:
            source_branch: Source branch name
            target_branch: Target branch name
            title: PR title
            description: PR description
            reviewers: Optional list of reviewer email addresses
            
        Returns:
            Created pull request or None if failed
        """
        try:
            # Get repository
            repository = self.git_client.get_repository(
                repository_id=self.repository_id,
                project=self.project
            )
            
            # Create PR
            pr = GitPullRequest(
                source_ref_name=f"refs/heads/{source_branch}",
                target_ref_name=f"refs/heads/{target_branch}",
                title=title,
                description=description
            )
            
            created_pr = self.git_client.create_pull_request(
                git_pull_request_to_create=pr,
                repository_id=repository.id,
                project=self.project
            )
            
            logger.info(f"Created PR #{created_pr.pull_request_id}: {title}")
            
            # Add reviewers if provided
            if reviewers and created_pr:
                self.add_reviewers(created_pr.pull_request_id, reviewers)
            
            return created_pr
            
        except Exception as e:
            logger.error(f"Error creating pull request: {str(e)}")
            return None
    
    def update_pull_request(
        self,
        pull_request_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """Update an existing pull request.
        
        Args:
            pull_request_id: PR ID
            title: New title (optional)
            description: New description (optional)
            
        Returns:
            True if successful
        """
        try:
            repository = self.git_client.get_repository(
                repository_id=self.repository_id,
                project=self.project
            )
            
            # Get existing PR
            pr = self.git_client.get_pull_request(
                repository_id=repository.id,
                pull_request_id=pull_request_id,
                project=self.project
            )
            
            # Update fields
            if title:
                pr.title = title
            if description:
                pr.description = description
            
            # Update PR
            self.git_client.update_pull_request(
                git_pull_request_to_update=pr,
                repository_id=repository.id,
                pull_request_id=pull_request_id,
                project=self.project
            )
            
            logger.info(f"Updated PR #{pull_request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating pull request: {str(e)}")
            return False
    
    def add_comment(
        self,
        pull_request_id: int,
        comment: str,
        parent_comment_id: Optional[int] = None
    ) -> bool:
        """Add a comment to a pull request.
        
        Args:
            pull_request_id: PR ID
            comment: Comment text
            parent_comment_id: Optional parent comment ID for replies
            
        Returns:
            True if successful
        """
        try:
            repository = self.git_client.get_repository(
                repository_id=self.repository_id,
                project=self.project
            )
            
            # Create comment thread
            comment_obj = Comment(content=comment)
            thread = CommentThread(
                comments=[comment_obj],
                status="active"
            )
            
            if parent_comment_id:
                thread.comments[0].parent_comment_id = parent_comment_id
            
            # Add comment
            self.git_client.create_thread(
                repository_id=repository.id,
                pull_request_id=pull_request_id,
                comment_thread=thread,
                project=self.project
            )
            
            logger.info(f"Added comment to PR #{pull_request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding comment to PR: {str(e)}")
            return False
    
    def attach_report(
        self,
        pull_request_id: int,
        report_content: str,
        report_title: str = "Peer Review Report"
    ) -> bool:
        """Attach a report as a comment to PR.
        
        Args:
            pull_request_id: PR ID
            report_content: Report content (markdown)
            report_title: Title for the report comment
            
        Returns:
            True if successful
        """
        comment = f"## {report_title}\n\n{report_content}"
        return self.add_comment(pull_request_id, comment)
    
    def add_reviewers(self, pull_request_id: int, reviewers: List[str]) -> bool:
        """Add reviewers to a pull request.
        
        Args:
            pull_request_id: PR ID
            reviewers: List of reviewer email addresses or IDs
            
        Returns:
            True if successful
        """
        # Note: This is a simplified implementation
        # Full implementation would require updating PR with reviewer identities
        logger.info(f"Reviewers requested for PR #{pull_request_id}: {reviewers}")
        return True
    
    def get_pull_request(self, pull_request_id: int) -> Optional[GitPullRequest]:
        """Get pull request details.
        
        Args:
            pull_request_id: PR ID
            
        Returns:
            Pull request object or None
        """
        try:
            repository = self.git_client.get_repository(
                repository_id=self.repository_id,
                project=self.project
            )
            
            pr = self.git_client.get_pull_request(
                repository_id=repository.id,
                pull_request_id=pull_request_id,
                project=self.project
            )
            
            return pr
            
        except Exception as e:
            logger.error(f"Error getting pull request: {str(e)}")
            return None

