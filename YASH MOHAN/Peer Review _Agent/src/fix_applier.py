"""Apply fixes to code based on analysis suggestions."""
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import re
import difflib


logger = logging.getLogger(__name__)


class FixApplier:
    """Applies fixes to code files based on analysis suggestions."""
    
    def __init__(self, workspace_path: Path, auto_apply: bool = False):
        """Initialize fix applier.
        
        Args:
            workspace_path: Path to workspace root
            auto_apply: Whether to auto-apply fixes (requires confirmation)
        """
        self.workspace_path = Path(workspace_path)
        self.auto_apply = auto_apply
        self.applied_fixes: List[Dict[str, Any]] = []
    
    def apply_fixes(self, analysis: Dict[str, Any], require_confirmation: bool = True) -> Dict[str, Any]:
        """Apply fixes from analysis results.
        
        Args:
            analysis: Analysis results dictionary
            require_confirmation: Whether to require user confirmation
            
        Returns:
            Dictionary with applied fixes summary
        """
        if "issues" not in analysis:
            logger.warning("No issues found in analysis")
            return {"status": "no_issues", "applied": 0, "skipped": 0}
        
        issues = analysis["issues"]
        applied = 0
        skipped = 0
        errors = []
        
        # Group issues by file
        issues_by_file = {}
        for issue in issues:
            file_path = issue.get("file", "")
            if file_path:
                if file_path not in issues_by_file:
                    issues_by_file[file_path] = []
                issues_by_file[file_path].append(issue)
        
        # Apply fixes per file
        for file_path, file_issues in issues_by_file.items():
            try:
                result = self._apply_fixes_to_file(file_path, file_issues, require_confirmation)
                applied += result["applied"]
                skipped += result["skipped"]
                if result.get("errors"):
                    errors.extend(result["errors"])
            except Exception as e:
                logger.error(f"Error applying fixes to {file_path}: {str(e)}")
                errors.append({"file": file_path, "error": str(e)})
        
        return {
            "status": "completed",
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
            "total_issues": len(issues)
        }
    
    def _apply_fixes_to_file(
        self,
        file_path: str,
        issues: List[Dict],
        require_confirmation: bool
    ) -> Dict[str, Any]:
        """Apply fixes to a specific file.
        
        Args:
            file_path: Relative path to file
            issues: List of issues for this file
            require_confirmation: Whether to require confirmation
            
        Returns:
            Dictionary with results
        """
        full_path = self.workspace_path / file_path
        
        if not full_path.exists():
            logger.warning(f"File not found: {full_path}")
            return {"applied": 0, "skipped": len(issues), "errors": [{"file": file_path, "error": "File not found"}]}
        
        # Read file content
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {full_path}: {str(e)}")
            return {"applied": 0, "skipped": len(issues), "errors": [{"file": file_path, "error": str(e)}]}
        
        # Sort issues by line number (descending) to avoid offset issues
        issues_sorted = sorted(issues, key=lambda x: x.get("line", 0), reverse=True)
        
        applied = 0
        skipped = 0
        errors = []
        lines = content.split('\n')
        
        for issue in issues_sorted:
            try:
                # Check if fix should be applied
                if require_confirmation and not self.auto_apply:
                    # In interactive mode, would prompt user here
                    # For now, skip if auto_apply is False
                    skipped += 1
                    continue
                
                line_num = issue.get("line", 0)
                current_code = issue.get("current_code", "").strip()
                suggested_fix = issue.get("suggested_fix", "").strip()
                
                if not suggested_fix:
                    skipped += 1
                    continue
                
                # Apply fix
                if line_num > 0 and line_num <= len(lines):
                    # Line-specific fix
                    line_idx = line_num - 1
                    original_line = lines[line_idx]
                    
                    # Try to match current code in the line
                    if current_code in original_line or self._code_matches(original_line, current_code):
                        # Replace with suggested fix
                        lines[line_idx] = suggested_fix
                        applied += 1
                        
                        self.applied_fixes.append({
                            "file": file_path,
                            "line": line_num,
                            "issue_type": issue.get("type", "unknown"),
                            "severity": issue.get("severity", "medium"),
                            "original": original_line,
                            "fixed": suggested_fix
                        })
                    else:
                        # Try multi-line replacement
                        if self._apply_multiline_fix(lines, line_idx, current_code, suggested_fix):
                            applied += 1
                            self.applied_fixes.append({
                                "file": file_path,
                                "line": line_num,
                                "issue_type": issue.get("type", "unknown"),
                                "severity": issue.get("severity", "medium"),
                                "original": current_code,
                                "fixed": suggested_fix
                            })
                        else:
                            # Try fuzzy matching in the search range
                            if self._apply_fuzzy_fix(lines, line_idx, current_code, suggested_fix):
                                applied += 1
                                self.applied_fixes.append({
                                    "file": file_path,
                                    "line": line_num,
                                    "issue_type": issue.get("type", "unknown"),
                                    "severity": issue.get("severity", "medium"),
                                    "original": current_code,
                                    "fixed": suggested_fix,
                                    "method": "fuzzy"
                                })
                            else:
                                skipped += 1
                                errors.append({
                                    "file": file_path,
                                    "line": line_num,
                                    "error": "Could not match current code (even with fuzzy match)"
                                })
                else:
                    # Try to find and replace in entire file
                    if current_code in content:
                        content = content.replace(current_code, suggested_fix, 1)
                        applied += 1
                        self.applied_fixes.append({
                            "file": file_path,
                            "line": 0,
                            "issue_type": issue.get("type", "unknown"),
                            "severity": issue.get("severity", "medium"),
                            "original": current_code,
                            "fixed": suggested_fix
                        })
                    else:
                        skipped += 1
                        
            except Exception as e:
                logger.error(f"Error applying fix for issue: {str(e)}")
                errors.append({"file": file_path, "line": issue.get("line", 0), "error": str(e)})
                skipped += 1
        
        # Write updated content
        if applied > 0:
            try:
                new_content = '\n'.join(lines) if isinstance(lines, list) else content
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                logger.info(f"Applied {applied} fixes to {file_path}")
            except Exception as e:
                logger.error(f"Error writing file {full_path}: {str(e)}")
                errors.append({"file": file_path, "error": f"Write error: {str(e)}"})
        
        return {"applied": applied, "skipped": skipped, "errors": errors}
    
    def _code_matches(self, line: str, code_snippet: str) -> bool:
        """Check if code snippet matches line (with normalization).
        
        Args:
            line: Line from file
            code_snippet: Code snippet to match
            
        Returns:
            True if matches
        """
        # Normalize whitespace
        line_normalized = ' '.join(line.split())
        snippet_normalized = ' '.join(code_snippet.split())
        
        return snippet_normalized in line_normalized or line_normalized in snippet_normalized
    
    def _apply_multiline_fix(
        self,
        lines: List[str],
        start_line: int,
        current_code: str,
        suggested_fix: str
    ) -> bool:
        """Apply multiline fix.
        
        Args:
            lines: List of file lines
            start_line: Starting line index
            current_code: Current code to replace
            suggested_fix: Suggested replacement
            
        Returns:
            True if fix was applied
        """
        # Try to find current_code in lines around start_line
        search_range = 10  # Look 10 lines before and after
        start_idx = max(0, start_line - search_range)
        end_idx = min(len(lines), start_line + search_range)
        
        search_text = '\n'.join(lines[start_idx:end_idx])
        
        if current_code.strip() in search_text:
            # Replace in the search range
            new_text = search_text.replace(current_code.strip(), suggested_fix.strip(), 1)
            new_lines = new_text.split('\n')
            lines[start_idx:end_idx] = new_lines
            return True
        
        return False
    
    def _apply_fuzzy_fix(
        self,
        lines: List[str],
        start_line: int,
        current_code: str,
        suggested_fix: str
    ) -> bool:
        """Apply fix using fuzzy matching.
        
        Args:
            lines: List of file lines
            start_line: Starting line index
            current_code: Current code to replace
            suggested_fix: Suggested replacement
            
        Returns:
            True if fix was applied
        """
        # Look in a window around the start line
        window_size = 20
        start_idx = max(0, start_line - window_size)
        end_idx = min(len(lines), start_line + window_size)
        
        window_text = '\n'.join(lines[start_idx:end_idx])
        
        # Use SequenceMatcher to find the best match
        # matcher = difflib.SequenceMatcher(None, window_text, current_code)
        # match = matcher.find_longest_match(0, len(window_text), 0, len(current_code))
        
        # If we found a substantial match (e.g., > 80% of the code snippet)
        # if match.size > len(current_code) * 0.8:
        
        # We'll skip the strict block match and go straight to line-by-line search
        # because LLMs often mess up whitespace or small details that break contiguous matches
        
        # Split current code into lines
        code_lines = current_code.strip().split('\n')
        if not code_lines:
            return False
            
        # Try to find the first line of the code snippet
        first_line = code_lines[0].strip()
        best_score = 0
        best_idx = -1
        
        for i in range(start_idx, end_idx):
            # Calculate similarity ratio
            score = difflib.SequenceMatcher(None, lines[i].strip(), first_line).ratio()
            
            # Threshold of 0.7 (70% match)
            if score > 0.7 and score > best_score:
                best_score = score
                best_idx = i
        
        if best_idx != -1:
            # We found a potential start.
            # Ideally we should verify subsequent lines if it's a multi-line block
            # But for now, we'll assume if the first line matches well enough in this context, it's the one.
            
            # If it's a multi-line replacement, we need to handle that
            if len(code_lines) > 1:
                # Check if we have enough lines
                if best_idx + len(code_lines) <= len(lines):
                    # Replace the block
                    lines[best_idx:best_idx + len(code_lines)] = suggested_fix.split('\n')
                    return True
            else:
                # Single line replacement
                lines[best_idx] = suggested_fix
                return True
                
        return False
                
        return False
    
    def get_applied_fixes(self) -> List[Dict[str, Any]]:
        """Get list of applied fixes.
        
        Returns:
            List of applied fix dictionaries
        """
        return self.applied_fixes

