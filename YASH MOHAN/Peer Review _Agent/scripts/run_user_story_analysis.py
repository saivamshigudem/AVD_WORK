"""Automated workflow to fetch Azure DevOps work items, pull code, analyze it, and generate a report."""
from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime
import re
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from azure.devops.v7_1.git.models import GitVersionDescriptor  # type: ignore

from src.config_loader import ConfigLoader  # type: ignore
from src.azure_auth import AzureDevOpsAuth  # type: ignore
from src.user_story_fetcher import UserStoryFetcher  # type: ignore
from src.code_analyzer import CodeAnalyzer  # type: ignore


WORK_ITEM_IDS = [146, 147, 148]
REPOSITORY_HINTS_DEFAULT = [
    "feature/code_reviewer",
    "code_reviewer",
    "feature",
]
BRANCH_HINTS_DEFAULT = [
    "feature/code_reviewer",
]
TARGET_FILE_PATH = "feature/code_reviewer/Peer_review/test_auth.py"
REPORTS_DIR = Path("reports")
AC_KEYWORDS = ("acceptance criteria", "ac1", "ac2", "ac3", "ac4", "ac5")
STOPWORDS = {
    "the",
    "and",
    "with",
    "that",
    "this",
    "when",
    "then",
    "must",
    "should",
    "user",
    "password",
    "token",
    "account",
    "existing",
}


def progress(step: str) -> None:
    """Print progress message."""
    print(step)


def clean_html(text: str) -> str:
    """Strip simple HTML tags and decode entities."""
    import re
    from html import unescape

    cleaned = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    cleaned = re.sub(r"</(div|p|li)>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = unescape(cleaned)
    return cleaned


def extract_acceptance_criteria(description: Optional[str]) -> List[str]:
    """Extract acceptance criteria lines (AC1, AC2, etc.) from description."""
    if not description:
        return []

    text = clean_html(description.replace("\r", ""))
    lines = [line.strip() for line in text.split("\n")]

    ac_lines: List[str] = []
    for line in lines:
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("ac") and ":" in line:
            ac_lines.append(line)
            continue
        if lower.startswith("- ac") and ":" in line:
            ac_lines.append(line.lstrip("- ").strip())

    if ac_lines:
        return ac_lines

    capturing = False
    for line in lines:
        if not line:
            if capturing:
                break
            continue
        lower = line.lower()
        if not capturing and any(keyword in lower for keyword in AC_KEYWORDS):
            capturing = True
            parts = line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                ac_lines.append(parts[1].strip())
            continue
        if capturing:
            ac_lines.append(line)

    return ac_lines


def tokenize_for_match(text: str) -> List[str]:
    tokens = [
        tok
        for tok in re.split(r"[^a-z0-9]+", text.lower())
        if tok and tok not in STOPWORDS
    ]
    return tokens


def determine_ac_status(ac_line: str, compliance_entry: Optional[Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """Determine if an acceptance criterion is flagged as missing."""
    if not compliance_entry:
        return "Not evaluated", None

    missing_entries = compliance_entry.get("missing_criteria") or []
    ac_tokens = set(tokenize_for_match(ac_line))
    for miss in missing_entries:
        miss_tokens = tokenize_for_match(miss or "")
        if not miss_tokens:
            continue
        overlap = len(ac_tokens.intersection(miss_tokens))
        if overlap >= max(1, len(set(miss_tokens)) // 2):
            return "Missing", miss
    return "Addressed", None


def get_repository_candidates(git_client, project: str, preferred_hint: Optional[str]) -> List[Any]:
    """Return repositories ordered by hints."""
    repositories = git_client.get_repositories(project=project)
    if not repositories:
        raise RuntimeError("No repositories found in the project.")

    hints: List[str] = []
    if preferred_hint:
        hints.append(preferred_hint)
    hints.extend(REPOSITORY_HINTS_DEFAULT)

    ordered: List[Any] = []
    for hint in hints:
        for repo in repositories:
            if repo.name.lower() == hint.lower():
                if repo not in ordered:
                    ordered.append(repo)

    for repo in repositories:
        if repo not in ordered:
            ordered.append(repo)

    return ordered


def build_path_candidates(path: str) -> List[str]:
    """Generate candidate paths by progressively trimming leading segments."""
    candidates = [path]
    segments = path.split("/")
    for idx in range(1, len(segments)):
        candidate = "/".join(segments[idx:])
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return candidates


def fetch_file_content(
    git_client,
    project: str,
    repository_candidates: List[Any],
    branch_candidates: List[str],
    path_candidates: List[str],
) -> tuple[str, str, str, str]:
    """Fetch file content, returning content plus repo/branch/path used."""
    attempts = []

    def attempt_fetch(repo, path, branch):
        descriptor = GitVersionDescriptor(
            version=branch,
            version_type="branch",
        )
        stream = git_client.get_item_content(
            repository_id=repo.id,
            path=path,
            project=project,
            version_descriptor=descriptor,
        )
        content_bytes = b"".join(stream)
        return content_bytes.decode("utf-8", errors="ignore")

    for repo in repository_candidates:
        repo_paths = path_candidates.copy()
        # Attempt to discover file path dynamically if needed
        discovered_path = discover_file_path(git_client, project, repo, Path(path_candidates[-1]).name)
        if discovered_path and discovered_path not in repo_paths:
            repo_paths.append(discovered_path)

        for path in repo_paths:
            for branch in branch_candidates:
                try:
                    content = attempt_fetch(repo, path, branch)
                    return content, repo.name, branch, path
                except Exception as err:
                    attempts.append(f"{repo.name}:{branch}:{path} -> {err}")
                    continue

    error_msg = "; ".join(attempts) if attempts else "Unknown error"
    raise RuntimeError(f"Failed to fetch file from repositories. Attempts: {error_msg}")


def discover_file_path(git_client, project: str, repository, target_filename: str) -> Optional[str]:
    """Attempt to discover the path of a file by name."""
    try:
        items = git_client.get_items(
            repository_id=repository.id,
            project=project,
            recursion_level="Full",
        )
    except Exception:
        return None

    target_lower = target_filename.lower()
    for item in items:
        if not getattr(item, "path", None):
            continue
        path_lower = item.path.lower()
        if path_lower.endswith(f"/{target_lower}") or path_lower.endswith(target_lower):
            return item.path.lstrip("/")
    return None


def build_report(
    work_items: List[Dict[str, Any]],
    code_path: str,
    analysis: Dict[str, Any],
    file_preview: str,
    metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """Build a well-formatted markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append("# User Story & Code Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {timestamp}")
    lines.append(f"**Code File:** `{code_path}`")
    
    if metrics:
        lines.append("")
        lines.append(f"**Tokens Used:** {metrics.get('total_tokens', 'N/A')}")
        lines.append(f"**Estimated Cost:** ${metrics.get('estimated_cost_usd', 0):.4f}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. Work items table
    lines.append("## 1. Work Items")
    lines.append("")
    if work_items:
        lines.append("| ID  | Title | State |")
        lines.append("| --- | ----- | ----- |")
        for item in work_items:
            lines.append(
                f"| {item['id']} "
                f"| {item.get('title', 'Untitled')} "
                f"| {item.get('state', 'N/A')} |"
            )
        lines.append("")

    else:
        lines.append("_No work items were retrieved._")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 2. Acceptance coverage
    lines.append("## 2. Acceptance Criteria Coverage")
    lines.append("")
    if work_items:
        compliance_map = {
            entry.get("story_id"): entry for entry in analysis.get("user_story_compliance", [])
        }
        rows = []
        for item in work_items:
            story_id = item.get("id")
            parsed = item.get("parsed_acceptance") or []
            entry = compliance_map.get(story_id)
            if not parsed:
                rows.append((story_id, item.get("title", "Untitled"), "(No explicit acceptance criteria found)", "Not available", ""))
                continue
            for crit in parsed:
                status, detail = determine_ac_status(crit, entry)
                rows.append((story_id, item.get("title", "Untitled"), crit, status, detail or ""))
        if rows:
            lines.append("| Story | Acceptance Criterion | Status | Notes |")
            lines.append("| ----- | -------------------- | ------ | ----- |")
            for row in rows:
                lines.append(f"| {row[0]} | {row[2]} | {row[3]} | {row[4]} |")
            lines.append("")
        else:
            lines.append("_No acceptance criteria detected in the work items._")
    else:
        lines.append("_Acceptance coverage unavailable (no work items)._")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 3. Code snapshot
    lines.append("## 3. Code Snapshot (first 20 lines)")
    lines.append("")
    lines.append("```python")
    lines.append(file_preview.strip() or "# (file empty)")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 4. Analysis summary
    lines.append("## 4. Analysis Summary")
    lines.append("")
    summary = analysis.get("summary", {})
    lines.append("| Metric               | Value                |")
    lines.append("| -------------------- | -------------------- |")
    lines.append(f"| Total issues         | {summary.get('total_issues', 'N/A')} |")
    lines.append(f"| Critical             | {summary.get('critical', 'N/A')} |")
    lines.append(f"| High                 | {summary.get('high', 'N/A')} |")
    lines.append(f"| Medium               | {summary.get('medium', 'N/A')} |")
    lines.append(f"| {summary.get('low', 'N/A')} |")
    lines.append(f"| User story alignment | {summary.get('user_story_alignment', 'unknown')} |")
    lines.append("")

    # Agent Thought Process (Chain of Thought)
    if "thought_process" in analysis:
        tp = analysis["thought_process"]
        lines.append("## 4.0 Agent Thought Process")
        lines.append("")
        if tp.get("understanding"):
            lines.append(f"### Understanding\n{tp.get('understanding')}\n")
        if tp.get("user_story_mapping"):
            lines.append(f"### User Story Mapping\n{tp.get('user_story_mapping')}\n")
        if tp.get("gap_analysis"):
            lines.append(f"### Gap Analysis\n{tp.get('gap_analysis')}\n")
        if tp.get("security_review"):
            lines.append(f"### Security Review\n{tp.get('security_review')}\n")
        if tp.get("impact_assessment"):
            lines.append(f"### Impact Assessment\n{tp.get('impact_assessment')}\n")
        lines.append("---")
        lines.append("")

    # Present coding requirements (positive findings)
    lines.append("### 4.1 Present Coding Requirements")
    present_items: List[str] = []
    if summary.get("total_issues", 0) == 0:
        present_items.append("All reviewed guidelines satisfied.")
    else:
        if summary.get("user_story_alignment") in {"aligned", "partially_aligned"}:
            present_items.append("User stories have partial alignment with implementation.")
        if summary.get("low", 0) >= 0:
            present_items.append("Basic code structure analyzed successfully.")
    if not present_items:
        present_items.append(
            "No explicit positive findings captured. Review code for additional alignment manually."
        )
    for item in present_items:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("---")
    lines.append("")

    issues = analysis.get("issues", [])
    user_story_issues: List[Dict[str, Any]] = []
    guideline_issues: List[Dict[str, Any]] = []
    industry_issues: List[Dict[str, Any]] = []
    other_issues: List[Dict[str, Any]] = []

    for issue in issues:
        issue_type = (issue.get("type") or "").lower()
        if "story" in issue_type or "functionality" in issue_type or "gap" in issue_type:
            user_story_issues.append(issue)
        elif "guideline" in issue_type or "documentation" in issue_type or "coding" in issue_type:
            guideline_issues.append(issue)
        elif any(keyword in issue_type for keyword in ("security", "performance", "industry")):
            industry_issues.append(issue)
        else:
            other_issues.append(issue)

    def append_issue_block(section_number: int, title: str, subset: List[Dict[str, Any]]) -> None:
        lines.append(f"## {section_number}. {title}")
        lines.append("")
        if not subset:
            lines.append("_No issues in this category._")
            lines.append("")
            lines.append("---")
            lines.append("")
            return

        lines.append(
            "> Each entry lists the issue type, location, severity, current behavior, "
            "suggested fix, and rationale."
        )
        lines.append("")

        for idx, issue in enumerate(subset, start=1):
            lines.append(
                f"### {idx}) {issue.get('type', 'issue').replace('_', ' ').title()} "
                f"— {issue.get('file', 'Unknown file')}"
            )
            if issue.get("line"):
                lines.append(f"- **Line:** {issue['line']}")
            lines.append(f"- **Severity:** {issue.get('severity', 'N/A')}")
            lines.append(f"- **Description:** {issue.get('description', 'No description')}")

            if issue.get("current_code"):
                lines.append("- **Current code:**")
                lines.append("```")
                lines.append(issue["current_code"])
                lines.append("```")

            if issue.get("suggested_fix"):
                lines.append("- **Suggested fix:**")
                lines.append("```")
                lines.append(issue["suggested_fix"])
                lines.append("```")

            if issue.get("explanation"):
                lines.append(f"- **Explanation:** {issue['explanation']}")

            lines.append("")

        lines.append("---")
        lines.append("")

    append_issue_block(5, "User Story Analysis", user_story_issues)
    append_issue_block(6, "Guideline & Best Practice Compliance", guideline_issues)
    append_issue_block(7, "Industry & Security Compliance", industry_issues + other_issues)

    # 8. User story compliance
    lines.append("## 8. User Story Compliance")
    lines.append("")
    compliance = analysis.get("user_story_compliance", [])
    if compliance:
        lines.append("| Story | Status              | Missing Criteria |")
        lines.append("| ----- | ------------------- | ---------------- |")
        for item in compliance:
            story_id = item.get("story_id", "N/A")
            status = item.get("status", "unknown")
            missing = item.get("missing_criteria") or []
            missing_str = "; ".join(missing) if missing else ""
            lines.append(f"| {story_id} | {status} | {missing_str} |")

        lines.append("")
        for item in compliance:
            lines.append(f"- **Story #{item.get('story_id', 'N/A')}**")
            if item.get("missing_criteria"):
                lines.append("  - Missing criteria:")
                for crit in item["missing_criteria"]:
                    lines.append(f"    - {crit}")
            if item.get("notes"):
                lines.append(f"  - Notes: {item['notes']}")
            lines.append("")
    else:
        lines.append("_No compliance details returned by the analyzer._")

    return "\n".join(lines)


def main() -> None:
    progress("[1/7] Loading configuration...")
    config_loader = ConfigLoader()
    config = config_loader.config
    guidelines = config_loader.get_guidelines()

    org_url = config_loader.get("azure_devops.organization")
    pat = config_loader.get("azure_devops.personal_access_token")
    project = config_loader.get("azure_devops.project")
    repo_hint = (
        config_loader.get("azure_devops.repository_id")
        or config_loader.get("azure_devops.repository_name")
    )

    default_branch = config_loader.get("git.default_branch", "main")
    branch_hints = BRANCH_HINTS_DEFAULT.copy()
    if default_branch and default_branch not in branch_hints:
        branch_hints.append(default_branch)
    for fallback in ("main", "master"):
        if fallback not in branch_hints:
            branch_hints.append(fallback)

    progress("[2/7] Authenticating with Azure DevOps...")
    print(f"  Organization: {org_url}")
    print(f"  Project: {project}")
    auth = AzureDevOpsAuth(org_url, pat)
    if not auth.authenticate():
        raise RuntimeError("Authentication with Azure DevOps failed.")
    if not auth.verify_connectivity():
        raise RuntimeError("Connectivity test with Azure DevOps failed.")
    print("  Authentication successful.")

    progress("[3/7] Fetching user stories...")
    fetcher = UserStoryFetcher(auth.get_work_item_client(), project)
    work_items: List[Dict[str, Any]] = []
    for wi_id in WORK_ITEM_IDS:
        story = fetcher.fetch_by_id(wi_id)
        if story:
            story["parsed_acceptance"] = extract_acceptance_criteria(
                story.get("acceptance_criteria") or story.get("description")
            )
            work_items.append(story)
            print(f"  Retrieved work item #{wi_id}: {story.get('title', 'Untitled')} ({story.get('state', 'N/A')})")
        else:
            print(f"  Work item #{wi_id} not found or not an allowed type.")
    if not work_items:
        progress("  Warning: No user stories found for requested IDs.")

    progress("[4/7] Downloading code file from repository...")
    git_client = auth.get_git_client()
    repository_candidates = get_repository_candidates(git_client, project, repo_hint)
    print("  Repository priority list:")
    for repo in repository_candidates[:5]:
        print(f"    - {repo.name}")
    path_candidates = build_path_candidates(TARGET_FILE_PATH)
    print("  Branch candidates:", ", ".join(branch_hints))
    print("  Path candidates:", ", ".join(path_candidates))
    file_content, repo_used, branch_used, path_used = fetch_file_content(
        git_client,
        project,
        repository_candidates,
        branch_hints,
        path_candidates,
    )
    print(f"  Downloaded from repo '{repo_used}', branch '{branch_used}', path '{path_used}'")
    code_preview = "\n".join(file_content.strip().splitlines()[:20])

    progress("[5/7] Running code analysis...")
    analyzer = CodeAnalyzer(config, guidelines)
    code_files = [
        {
            "path": path_used,
            "content": file_content,
        }
    ]
    analysis_result = analyzer.analyze_code(code_files, work_items)
    if analysis_result.get("status") != "success":
        raise RuntimeError(f"Analysis failed: {analysis_result.get('error')}")
    analysis = analysis_result.get("analysis", {})
    metrics = analysis_result.get("metrics", {})
    print(f"  Code analysis finished. Cost: ${metrics.get('estimated_cost_usd', 0):.4f}")

    progress("[6/7] Generating report...")
    report_content = build_report(
        work_items,
        path_used,
        analysis,
        code_preview,
        metrics,
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"user_story_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report_content, encoding="utf-8")

    progress(f"[7/7] Completed. Report saved to {report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")

