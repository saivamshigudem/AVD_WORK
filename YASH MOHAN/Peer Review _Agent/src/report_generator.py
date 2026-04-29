"""Generate markdown reports for peer review results."""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates markdown reports for peer review results."""
    
    def __init__(self, output_dir: Path = Path("./reports")):
        """Initialize report generator.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        analysis: Dict[str, Any],
        user_stories: List[Dict],
        applied_fixes: List[Dict[str, Any]],
        branch_name: str,
        timestamp: Optional[datetime] = None
    ) -> str:
        """Generate markdown report.
        
        Args:
            analysis: Analysis results dictionary
            user_stories: List of user story dictionaries
            applied_fixes: List of applied fixes
            branch_name: Branch name
            timestamp: Report timestamp (defaults to now)
            
        Returns:
            Markdown report content
        """
        timestamp = timestamp or datetime.now()
        
        report = []
        report.append("# Peer Review Report\n")
        report.append(f"**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**Branch:** {branch_name}\n\n")
        
        # Add Metrics if present
        if "metrics" in analysis:
            metrics = analysis["metrics"]
            if metrics.get("total_tokens"):
                report.append(f"**Tokens Used:** {metrics.get('total_tokens')}\n")
            if metrics.get("estimated_cost_usd"):
                report.append(f"**Estimated Cost:** ${metrics.get('estimated_cost_usd'):.4f}\n")
        
        report.append("---\n\n")
        
        # Summary
        report.append("## Summary\n\n")
        if "summary" in analysis:
            summary = analysis["summary"]
            report.append(f"- **Total Issues:** {summary.get('total_issues', 0)}\n")
            report.append(f"- **Critical:** {summary.get('critical', 0)}\n")
            report.append(f"- **High:** {summary.get('high', 0)}\n")
            report.append(f"- **Medium:** {summary.get('medium', 0)}\n")
            report.append(f"- **Low:** {summary.get('low', 0)}\n")
            report.append(f"- **User Story Alignment:** {summary.get('user_story_alignment', 'unknown')}\n")
        report.append("\n")
        
        # Agent Thought Process (Chain of Thought)
        if "thought_process" in analysis:
            tp = analysis["thought_process"]
            report.append("## Agent Thought Process\n\n")
            if tp.get("understanding"):
                report.append(f"### Understanding\n{tp.get('understanding')}\n\n")
            if tp.get("user_story_mapping"):
                report.append(f"### User Story Mapping\n{tp.get('user_story_mapping')}\n\n")
            if tp.get("gap_analysis"):
                report.append(f"### Gap Analysis\n{tp.get('gap_analysis')}\n\n")
            if tp.get("security_review"):
                report.append(f"### Security Review\n{tp.get('security_review')}\n\n")
            if tp.get("impact_assessment"):
                report.append(f"### Impact Assessment\n{tp.get('impact_assessment')}\n\n")
            report.append("---\n\n")
        
        # User Stories
        report.append("## User Stories Reviewed\n\n")
        if user_stories:
            for story in user_stories:
                report.append(f"### Story #{story.get('id', 'N/A')}: {story.get('title', 'N/A')}\n")
                report.append(f"- **State:** {story.get('state', 'N/A')}\n")
                report.append(f"- **Description:** {story.get('description', 'N/A')[:200]}...\n")
                report.append(f"- **Acceptance Criteria:** {story.get('acceptance_criteria', 'N/A')[:200]}...\n")
                report.append("\n")
        else:
            report.append("No user stories found.\n\n")
        
        # User Story Compliance
        if "user_story_compliance" in analysis and analysis["user_story_compliance"]:
            report.append("## User Story Compliance\n\n")
            for compliance in analysis["user_story_compliance"]:
                story_id = compliance.get('story_id', 'N/A')
                # Skip invalid story IDs
                if str(story_id).upper() in ["N/A", "NONE", "NULL", ""]:
                    continue
                    
                report.append(f"### Story #{story_id}\n")
                report.append(f"- **Status:** {compliance.get('status', 'N/A')}\n")
                if compliance.get("missing_criteria"):
                    report.append("- **Missing Criteria:**\n")
                    for criterion in compliance["missing_criteria"]:
                        report.append(f"  - {criterion}\n")
                if compliance.get("notes"):
                    report.append(f"- **Notes:** {compliance.get('notes')}\n")
                report.append("\n")
        
        # Issues
        report.append("## Issues Found\n\n")
        if "issues" in analysis and analysis["issues"]:
            # Group by severity
            issues_by_severity = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": []
            }
            
            for issue in analysis["issues"]:
                severity = issue.get("severity", "medium").lower()
                if severity in issues_by_severity:
                    issues_by_severity[severity].append(issue)
            
            for severity in ["critical", "high", "medium", "low"]:
                if issues_by_severity[severity]:
                    report.append(f"### {severity.capitalize()} Severity\n\n")
                    for issue in issues_by_severity[severity]:
                        report.append(f"#### {issue.get('type', 'Unknown')} - {issue.get('file', 'Unknown')}\n")
                        if issue.get("line"):
                            report.append(f"- **Line:** {issue.get('line')}\n")
                        report.append(f"- **Description:** {issue.get('description', 'N/A')}\n")
                        if issue.get("current_code"):
                            report.append(f"- **Current Code:**\n```\n{issue.get('current_code')}\n```\n")
                        if issue.get("suggested_fix"):
                            report.append(f"- **Suggested Fix:**\n```\n{issue.get('suggested_fix')}\n```\n")
                        if issue.get("explanation"):
                            report.append(f"- **Explanation:** {issue.get('explanation')}\n")
                        report.append("\n")
        else:
            report.append("No issues found.\n\n")
        
        # Applied Fixes
        if applied_fixes:
            report.append("## Applied Fixes\n\n")
            report.append(f"Total fixes applied: {len(applied_fixes)}\n\n")
            
            # Group by file
            fixes_by_file = {}
            for fix in applied_fixes:
                file_path = fix.get("file", "unknown")
                if file_path not in fixes_by_file:
                    fixes_by_file[file_path] = []
                fixes_by_file[file_path].append(fix)
            
            for file_path, fixes in fixes_by_file.items():
                report.append(f"### {file_path}\n\n")
                for fix in fixes:
                    report.append(f"- **Line {fix.get('line', 'N/A')}** ({fix.get('severity', 'medium')} - {fix.get('issue_type', 'unknown')})\n")
                    if fix.get("original"):
                        report.append(f"  - Original: `{fix.get('original')[:100]}...`\n")
                    if fix.get("fixed"):
                        report.append(f"  - Fixed: `{fix.get('fixed')[:100]}...`\n")
                report.append("\n")
        
        # Recommendations
        report.append("## Recommendations\n\n")
        if "summary" in analysis:
            summary = analysis["summary"]
            if summary.get("total_issues", 0) > 0:
                report.append("1. Review all identified issues before merging\n")
                report.append("2. Ensure user story acceptance criteria are fully met\n")
                report.append("3. Run tests to verify fixes don't break existing functionality\n")
                report.append("4. Consider adding unit tests for new or changed code\n")
            else:
                report.append("✅ No issues found. Code appears to be compliant with guidelines and user stories.\n")
        
        report.append("\n---\n")
        report.append(f"*Report generated by Peer Review Agent*\n")
        
        return "\n".join(report)
    
    def save_report(self, report_content: str, filename: Optional[str] = None) -> Path:
        """Save report to file.
        
        Args:
            report_content: Report content
            filename: Optional filename (defaults to timestamp-based)
            
        Returns:
            Path to saved report file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"peer_review_report_{timestamp}.md"
        
        file_path = self.output_dir / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"Report saved to: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving report: {str(e)}")
            raise

