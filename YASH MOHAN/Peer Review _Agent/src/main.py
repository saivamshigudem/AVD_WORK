"""Main orchestrator for Peer Review Agent."""
import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import ConfigLoader
from src.azure_auth import AzureDevOpsAuth
from src.user_story_fetcher import UserStoryFetcher
from src.code_loader import CodeLoader
from src.code_analyzer import CodeAnalyzer
from src.fix_applier import FixApplier
from src.git_operations import GitOperations
from src.pr_manager import PRManager
from src.report_generator import ReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('peer_review_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class PeerReviewAgent:
    """Main orchestrator for peer review automation."""
    
    def __init__(
        self, 
        config_path: str = "config.yaml", 
        env_path: str = ".env",
        # Dependency Injection
        azure_auth: Optional[AzureDevOpsAuth] = None,
        user_story_fetcher: Optional[UserStoryFetcher] = None,
        code_analyzer: Optional[CodeAnalyzer] = None,
        git_ops: Optional[GitOperations] = None,
        report_generator: Optional[ReportGenerator] = None,
        pr_manager: Optional[PRManager] = None
    ):
        """Initialize peer review agent.
        
        Args:
            config_path: Path to configuration file
            env_path: Path to .env file
            azure_auth: Injected AzureDevOpsAuth instance
            user_story_fetcher: Injected UserStoryFetcher instance
            code_analyzer: Injected CodeAnalyzer instance
            git_ops: Injected GitOperations instance
            report_generator: Injected ReportGenerator instance
            pr_manager: Injected PRManager instance
        """
        logger.info("Initializing Peer Review Agent...")
        
        # Load configuration
        self.config_loader = ConfigLoader(config_path, env_path)
        self.config = self.config_loader.config
        self.guidelines = self.config_loader.get_guidelines()
        
        # Initialize components from DI or None
        self.workspace_path = Path.cwd()
        self.azure_auth = azure_auth
        self.user_story_fetcher = user_story_fetcher
        self.code_loader: Optional[CodeLoader] = None  # Always created locally for now
        self.code_analyzer = code_analyzer
        self.fix_applier: Optional[FixApplier] = None
        self.git_ops = git_ops
        self.pr_manager = pr_manager
        self.report_generator = report_generator
    
    def setup(self) -> bool:
        """Set up all components.
        
        Returns:
            True if setup successful
        """
        try:
            logger.info("Setting up components...")
            
            # Initialize Azure DevOps authentication (if not injected)
            if not self.azure_auth:
                org_url = self.config_loader.get("azure_devops.organization")
                pat = self.config_loader.get("azure_devops.personal_access_token")
                
                if not org_url or not pat:
                    logger.error("Azure DevOps organization URL or PAT not configured")
                    return False
                
                self.azure_auth = AzureDevOpsAuth(org_url, pat)
                if not self.azure_auth.authenticate():
                    logger.error("Failed to authenticate with Azure DevOps")
                    return False
                
                if not self.azure_auth.verify_connectivity():
                    logger.error("Failed to verify connectivity to Azure DevOps")
                    return False
            
            # Initialize user story fetcher
            if not self.user_story_fetcher:
                project = self.config_loader.get("azure_devops.project")
                if not project:
                    logger.error("Azure DevOps project not configured")
                    return False
                
                self.user_story_fetcher = UserStoryFetcher(
                    self.azure_auth.get_work_item_client(),
                    project
                )
            
            # Initialize code loader
            if not self.code_loader:
                self.code_loader = CodeLoader(self.workspace_path, self.config)
            
            # Initialize code analyzer
            if not self.code_analyzer:
                self.code_analyzer = CodeAnalyzer(self.config, self.guidelines)
            
            # Initialize fix applier
            if not self.fix_applier:
                auto_apply = self.config_loader.get("review.auto_apply_fixes", False)
                self.fix_applier = FixApplier(self.workspace_path, auto_apply)
            
            # Initialize Git operations
            if not self.git_ops:
                try:
                    self.git_ops = GitOperations(self.workspace_path)
                except Exception as e:
                    logger.warning(f"Git operations not available: {str(e)}")
            
            # Initialize PR manager (requires repository info)
            if not self.pr_manager:
                try:
                    if self.git_ops:
                        # Get repository ID from remote URL or config
                        repository_id = self.config_loader.get("azure_devops.repository_id")
                        if not repository_id:
                            # Try to extract from remote URL
                            remote_url = self.git_ops.get_remote_url()
                            if remote_url:
                                # Extract repo name from URL
                                repository_id = remote_url.split('/')[-1].replace('.git', '')
                        
                        project = self.config_loader.get("azure_devops.project")
                        if repository_id and project:
                            self.pr_manager = PRManager(
                                self.azure_auth.get_git_client(),
                                project,
                                repository_id
                            )
                except Exception as e:
                    logger.warning(f"PR manager not available: {str(e)}")
            
            # Initialize report generator
            if not self.report_generator:
                report_dir = self.config_loader.get("report.output_dir", "./reports")
                self.report_generator = ReportGenerator(Path(report_dir))
            
            logger.info("Setup completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {str(e)}")
            return False
    
    def run(self, branch_name: Optional[str] = None, auto_apply: Optional[bool] = None) -> bool:
        """Run the peer review process.
        
        Args:
            branch_name: Optional branch name (defaults to current branch)
            auto_apply: Optional override for auto-apply setting
            
        Returns:
            True if process completed successfully
        """
        try:
            logger.info("Starting peer review process...")
            
            # Get current branch if not provided
            if not branch_name and self.git_ops:
                branch_name = self.git_ops.get_current_branch()
            elif not branch_name:
                branch_name = "unknown"
            
            logger.info(f"Reviewing branch: {branch_name}")
            
            # Step 1: Fetch user stories
            logger.info("Step 1: Fetching user stories...")
            user_stories = self.user_story_fetcher.fetch_by_branch(branch_name)
            
            if not user_stories:
                logger.warning("No user stories found for this branch. Fetching recent active stories...")
                user_stories = self.user_story_fetcher.fetch_recent_active(days=7)
            
            logger.info(f"Found {len(user_stories)} user stories")
            
            # Step 2: Load code files
            logger.info("Step 2: Loading code files...")
            code_files = self.code_loader.load_changed_files()
            
            if not code_files:
                logger.warning("No changed files found. Loading all code files...")
                code_files = self.code_loader.load_all_code_files()
            
            logger.info(f"Loaded {len(code_files)} code files")
            
            if not code_files:
                logger.error("No code files to analyze")
                return False
            
            # Step 3: Analyze code
            logger.info("Step 3: Analyzing code against user stories and guidelines (Parallel)...")
            analysis_result = self.code_analyzer.analyze_code(code_files, user_stories)
            
            if analysis_result["status"] != "success":
                logger.error(f"Code analysis failed: {analysis_result.get('error', 'Unknown error')}")
                return False
            
            analysis = analysis_result.get("analysis", {})
            metrics = analysis_result.get("metrics", {})
            
            # Log metrics
            if metrics:
                logger.info(f"Metrics - Tokens Used: {metrics.get('total_tokens')}, "
                            f"Est. Cost: ${metrics.get('estimated_cost_usd', 0):.4f}")
            
            logger.info(f"Analysis complete. Found {analysis.get('summary', {}).get('total_issues', 0)} issues")
            
            # Step 4: Apply fixes
            logger.info("Step 4: Applying fixes...")
            auto_apply_setting = auto_apply if auto_apply is not None else self.config_loader.get("review.auto_apply_fixes", False)
            
            if auto_apply_setting:
                logger.info("Auto-apply enabled. Applying fixes...")
                fix_result = self.fix_applier.apply_fixes(analysis, require_confirmation=False)
                logger.info(f"Applied {fix_result.get('applied', 0)} fixes, skipped {fix_result.get('skipped', 0)}")
            else:
                logger.info("Auto-apply disabled. Fixes will be suggested but not applied.")
                fix_result = {"applied": 0, "skipped": 0}
            
            applied_fixes = self.fix_applier.get_applied_fixes()
            
            # Step 5: Generate report
            logger.info("Step 5: Generating report...")
            # Inject metrics into analysis for the report
            if metrics:
                analysis["metrics"] = metrics
                
            report_content = self.report_generator.generate_report(
                analysis,
                user_stories,
                applied_fixes,
                branch_name
            )
            
            report_path = self.report_generator.save_report(report_content)
            logger.info(f"Report saved to: {report_path}")
            
            # Step 6: Commit and push changes (if fixes were applied)
            if applied_fixes and self.git_ops:
                logger.info("Step 6: Committing and pushing changes...")
                
                # Create new branch for fixes
                fix_branch_name = f"{branch_name}-peer-review-fixes"
                if self.git_ops.create_branch(fix_branch_name):
                    # Stage changed files
                    changed_files = self.git_ops.get_changed_files()
                    if changed_files:
                        self.git_ops.stage_files()
                        
                        # Commit
                        commit_message = f"[Peer Review Agent] Applied {len(applied_fixes)} fixes"
                        if self.git_ops.commit(commit_message):
                            # Push
                            if self.git_ops.push():
                                logger.info("Changes pushed successfully")
                                
                                # Step 7: Create/update PR
                                if self.config_loader.get("review.create_pr", True) and self.pr_manager:
                                    logger.info("Step 7: Creating pull request...")
                                    
                                    pr_title = self.config_loader.get(
                                        "review.pr_title_template",
                                        "Peer Review: {branch_name}"
                                    ).format(branch_name=branch_name)
                                    
                                    pr_description = self.config_loader.get(
                                        "review.pr_description_template",
                                        "Automated peer review and fixes applied by Peer Review Agent"
                                    )
                                    
                                    pr = self.pr_manager.create_pull_request(
                                        source_branch=fix_branch_name,
                                        target_branch=branch_name,
                                        title=pr_title,
                                        description=pr_description
                                    )
                                    
                                    if pr:
                                        # Attach report to PR
                                        self.pr_manager.attach_report(
                                            pr.pull_request_id,
                                            report_content,
                                            "Peer Review Report"
                                        )
                                        logger.info(f"PR created: #{pr.pull_request_id}")
            
            logger.info("Peer review process completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Peer review process failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Peer Review Agent for Azure DevOps")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--env",
        type=str,
        default=".env",
        help="Path to .env file"
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="Branch name to review (defaults to current branch)"
    )
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Auto-apply fixes without confirmation"
    )
    parser.add_argument(
        "--no-auto-apply",
        action="store_true",
        help="Do not auto-apply fixes (override config)"
    )
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = PeerReviewAgent(args.config, args.env)
    
    # Setup
    if not agent.setup():
        logger.error("Setup failed. Please check your configuration.")
        sys.exit(1)
    
    # Determine auto-apply setting
    auto_apply = None
    if args.auto_apply:
        auto_apply = True
    elif args.no_auto_apply:
        auto_apply = False
    
    # Run
    success = agent.run(branch_name=args.branch, auto_apply=auto_apply)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
