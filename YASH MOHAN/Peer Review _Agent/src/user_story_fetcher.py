"""Fetch user stories from Azure DevOps Work Item Tracking API."""
from azure.devops.v7_1.work_item_tracking.work_item_tracking_client import WorkItemTrackingClient
from azure.devops.v7_1.work_item_tracking.models import Wiql
from typing import List, Dict, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


ALLOWED_WORK_ITEM_TYPES = {"User Story", "Task", "Story"}


class UserStoryFetcher:
    """Fetches user stories from Azure DevOps based on various filters."""
    
    def __init__(self, work_item_client: WorkItemTrackingClient, project: str):
        """Initialize user story fetcher.
        
        Args:
            work_item_client: Azure DevOps Work Item Tracking client
            project: Azure DevOps project name
        """
        self.work_item_client = work_item_client
        self.project = project
    
    def fetch_by_branch(self, branch_name: str) -> List[Dict]:
        """Fetch user stories related to a specific branch.
        
        Args:
            branch_name: Name of the branch (e.g., "feature/user-auth")
            
        Returns:
            List of user story dictionaries
        """
        # Extract work item IDs from branch name if present
        # Common pattern: feature/US-123 or feature/123 or user-story/123
        import re
        work_item_ids = re.findall(r'[Uu][Ss]-?(\d+)', branch_name)
        work_item_ids.extend(re.findall(r'/(\d+)(?:-|$)', branch_name))
        # Also catch just numbers at the start or end if they look like IDs (3+ digits)
        work_item_ids.extend(re.findall(r'(?:^|/)(\d{3,})(?:$|-)', branch_name))
        
        # Remove duplicates
        work_item_ids = list(set(work_item_ids))
        
        stories = []
        for wi_id in work_item_ids:
            try:
                story = self.fetch_by_id(int(wi_id))
                if story:
                    stories.append(story)
            except Exception as e:
                logger.warning(f"Could not fetch work item {wi_id}: {str(e)}")
        
        # Also query by iteration path if branch contains iteration info
        if not stories:
            stories = self.fetch_by_iteration_path(branch_name)
        
        return stories
    
    def fetch_by_id(self, work_item_id: int) -> Optional[Dict]:
        """Fetch a specific user story by ID.
        
        Args:
            work_item_id: Work item ID
            
        Returns:
            User story dictionary or None if not found
        """
        try:
            work_item = self.work_item_client.get_work_item(
                id=work_item_id,
                expand="all"
            )

            if work_item.fields.get("System.WorkItemType") in ALLOWED_WORK_ITEM_TYPES:
                return self._format_user_story(work_item)

            logger.warning(
                "Work item %s is of type %s and was skipped.",
                work_item_id,
                work_item.fields.get("System.WorkItemType"),
            )
            return None
            
        except Exception as e:
            logger.error(f"Error fetching work item {work_item_id}: {str(e)}")
            return None
    
    def fetch_by_iteration_path(self, iteration_path: str) -> List[Dict]:
        """Fetch user stories by iteration path.
        
        Args:
            iteration_path: Iteration path (e.g., "Project\\Sprint 1")
            
        Returns:
            List of user story dictionaries
        """
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.Description]
        FROM WorkItems
        WHERE [System.TeamProject] = @project
        AND [System.WorkItemType] = 'User Story'
        AND [System.IterationPath] = '{iteration_path}'
        ORDER BY [System.Id]
        """
        
        return self._execute_wiql_query(wiql_query)
    
    def fetch_by_tags(self, tags: List[str]) -> List[Dict]:
        """Fetch user stories by tags.
        
        Args:
            tags: List of tags to filter by
            
        Returns:
            List of user story dictionaries
        """
        tags_filter = " OR ".join([f"[System.Tags] CONTAINS '{tag}'" for tag in tags])
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.Description]
        FROM WorkItems
        WHERE [System.TeamProject] = @project
        AND [System.WorkItemType] = 'User Story'
        AND ({tags_filter})
        ORDER BY [System.Id]
        """
        
        return self._execute_wiql_query(wiql_query)
    
    def fetch_by_commit_links(self, commit_sha: str) -> List[Dict]:
        """Fetch user stories linked to a specific commit.
        
        Args:
            commit_sha: Git commit SHA
            
        Returns:
            List of user story dictionaries
        """
        # Query for work items linked to the commit
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.Description]
        FROM WorkItems
        WHERE [System.TeamProject] = @project
        AND [System.WorkItemType] = 'User Story'
        AND [System.Id] IN (
            SELECT [System.Id]
            FROM WorkItemLinks
            WHERE [Source].[System.TeamProject] = @project
            AND [Target].[System.Id] IN (
                SELECT [System.Id]
                FROM WorkItems
                WHERE [System.TeamProject] = @project
                AND [System.ExternalLinkCount] > 0
            )
        )
        ORDER BY [System.Id]
        """
        
        # Note: This is a simplified query. In practice, you'd need to
        # query the commit and get linked work items directly
        return self._execute_wiql_query(wiql_query)
    
    def fetch_recent_active(self, days: int = 7) -> List[Dict]:
        """Fetch recently active user stories.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of user story dictionaries
        """
        wiql_query = f"""
        SELECT [System.Id], [System.Title], [System.State], [System.Description]
        FROM WorkItems
        WHERE [System.TeamProject] = @project
        AND [System.WorkItemType] = 'User Story'
        AND [System.State] <> 'Closed'
        AND [System.ChangedDate] >= @today - {days}
        ORDER BY [System.ChangedDate] DESC
        """
        
        return self._execute_wiql_query(wiql_query)
    
    def _execute_wiql_query(self, wiql_query: str) -> List[Dict]:
        """Execute a WIQL query and return formatted results.
        
        Args:
            wiql_query: WIQL query string
            
        Returns:
            List of user story dictionaries
        """
        try:
            query = Wiql(query=wiql_query)
            query_results = self.work_item_client.query_by_wiql(
                wiql=query
            )
            
            if not query_results.work_items:
                return []
            
            # Get work item IDs
            work_item_ids = [wi.id for wi in query_results.work_items]
            
            # Fetch full work item details
            work_items = self.work_item_client.get_work_items(
                ids=work_item_ids,
                project=self.project,
                expand="all"
            )
            
            stories = []
            for work_item in work_items:
                if work_item.fields.get("System.WorkItemType") == "User Story":
                    stories.append(self._format_user_story(work_item))
            
            return stories
            
        except Exception as e:
            logger.error(f"Error executing WIQL query: {str(e)}")
            return []
    
    def _format_user_story(self, work_item) -> Dict:
        """Format work item into user story dictionary.
        
        Args:
            work_item: Azure DevOps work item object
            
        Returns:
            Formatted user story dictionary
        """
        fields = work_item.fields
        
        # Extract acceptance criteria
        acceptance_criteria = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
        
        return {
            "id": work_item.id,
            "title": fields.get("System.Title", ""),
            "description": fields.get("System.Description", ""),
            "acceptance_criteria": acceptance_criteria,
            "state": fields.get("System.State", ""),
            "tags": fields.get("System.Tags", "").split(";") if fields.get("System.Tags") else [],
            "iteration_path": fields.get("System.IterationPath", ""),
            "assigned_to": fields.get("System.AssignedTo", {}).get("displayName", "") if fields.get("System.AssignedTo") else "",
            "created_date": fields.get("System.CreatedDate", ""),
            "changed_date": fields.get("System.ChangedDate", ""),
            "url": work_item.url if hasattr(work_item, 'url') else ""
        }

