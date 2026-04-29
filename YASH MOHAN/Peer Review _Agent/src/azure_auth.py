"""Azure DevOps authentication and client initialization."""
from azure.devops.connection import Connection
from azure.devops.v7_1.core.core_client import CoreClient
from azure.devops.v7_1.work_item_tracking.work_item_tracking_client import WorkItemTrackingClient
from azure.devops.v7_1.git.git_client import GitClient
from msrest.authentication import BasicAuthentication
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AzureDevOpsAuth:
    """Handles authentication and client initialization for Azure DevOps."""
    
    def __init__(self, organization_url: str, personal_access_token: str):
        """Initialize Azure DevOps authentication.
        
        Args:
            organization_url: Azure DevOps organization URL (e.g., "https://dev.azure.com/YourOrg")
            personal_access_token: Personal Access Token for authentication
        """
        self.organization_url = organization_url
        self.personal_access_token = personal_access_token
        self.connection: Optional[Connection] = None
        self.core_client: Optional[CoreClient] = None
        self.work_item_client: Optional[WorkItemTrackingClient] = None
        self.git_client: Optional[GitClient] = None
    
    def authenticate(self) -> bool:
        """Authenticate with Azure DevOps and initialize clients.
        
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Create credentials
            credentials = BasicAuthentication('', self.personal_access_token)
            
            # Create connection
            self.connection = Connection(
                base_url=self.organization_url,
                creds=credentials
            )
            
            # Initialize clients
            self.core_client = self.connection.clients.get_core_client()
            self.work_item_client = self.connection.clients.get_work_item_tracking_client()
            self.git_client = self.connection.clients.get_git_client()
            
            logger.info(f"Successfully authenticated with Azure DevOps: {self.organization_url}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def verify_connectivity(self) -> bool:
        """Verify connectivity to Azure DevOps.
        
        Returns:
            True if connectivity verified, False otherwise
        """
        try:
            if not self.core_client:
                logger.error("Core client not initialized. Call authenticate() first.")
                return False
            
            # Try to get projects to verify connectivity
            projects = self.core_client.get_projects()
            logger.info(f"Connectivity verified. Found {len(projects)} projects.")
            return True
            
        except Exception as e:
            logger.error(f"Connectivity verification failed: {str(e)}")
            return False
    
    def get_work_item_client(self) -> WorkItemTrackingClient:
        """Get Work Item Tracking client.
        
        Returns:
            WorkItemTrackingClient instance
        """
        if not self.work_item_client:
            raise RuntimeError("Client not initialized. Call authenticate() first.")
        return self.work_item_client
    
    def get_git_client(self) -> GitClient:
        """Get Git client.
        
        Returns:
            GitClient instance
        """
        if not self.git_client:
            raise RuntimeError("Client not initialized. Call authenticate() first.")
        return self.git_client
    
    def get_core_client(self) -> CoreClient:
        """Get Core client.
        
        Returns:
            CoreClient instance
        """
        if not self.core_client:
            raise RuntimeError("Client not initialized. Call authenticate() first.")
        return self.core_client

