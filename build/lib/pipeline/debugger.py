"""Dedicated debugging agent for analyzing and fixing test failures."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .llm import generate_json


@dataclass
class DebugFix:
    """Result from debugging agent."""
    files_to_create: list[dict[str, str]]  # [{"path": "...", "content": "..."}]
    files_to_modify: list[dict[str, str]]  # [{"path": "...", "content": "..."}]
    files_to_delete: list[str]  # ["path/to/file"]
    commands_to_run: list[str]  # ["pip install pytest-django", ...]
    explanation: str
    confidence: str  # "high", "medium", "low"
    needs_human: bool
    human_instructions: str | None


def get_file_tree_with_contents(target_dir: Path, max_files: int = 50) -> dict[str, Any]:
    """Generate file tree snapshot with file contents."""
    tree = {
        "structure": [],
        "files": {}
    }

    # Get directory structure
    for item in target_dir.rglob("*"):
        # Skip common directories
        if any(part.startswith(".") or part in ["venv", "env", "__pycache__", "node_modules"]
               for part in item.parts):
            continue

        rel_path = item.relative_to(target_dir)
        tree["structure"].append(str(rel_path))

        # Include file contents for relevant files
        if item.is_file() and len(tree["files"]) < max_files:
            # Only include source/config files
            if item.suffix in [".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml", ".ini", ".cfg", ".toml"]:
                try:
                    content = item.read_text(encoding="utf-8")
                    tree["files"][str(rel_path)] = content[:5000]  # Limit to 5000 chars
                except Exception:
                    pass

    return tree


def analyze_and_fix_test_failure(
    error_log: str,
    file_tree: dict[str, Any],
    target_dir: Path,
    context: str = "test failure",
    readme_content: str | None = None
) -> DebugFix:
    """
    Use LLM to analyze test failure and generate comprehensive fix.

    Args:
        error_log: The test failure output
        file_tree: File tree snapshot with contents
        target_dir: Project directory
        context: Additional context about what was being tested
        readme_content: Content of README.md for project context

    Returns:
        DebugFix with all necessary changes
    """
    print(f"\n🔍 Debugging Agent: Analyzing {context}...")

    # Prepare the debugging prompt
    debug_prompt = f"""You are a senior debugging agent analyzing a test failure.

## Context
{context}

## Project README
{readme_content if readme_content else "No README available"}

## File Tree Structure
{json.dumps(file_tree["structure"][:100], indent=2)}

## Relevant File Contents
{json.dumps(file_tree["files"], indent=2)[:10000]}

## Test Failure Output
```
{error_log[:3000]}
```

## Your Task
Analyze this test failure and provide a COMPLETE, AUTONOMOUS fix.

Common issues you should fix:
1. **Django settings not configured** → Create pytest.ini or conftest.py with django.setup()
2. **Tests in wrong location** → Move tests to proper app structure
3. **Missing mocks for external services** → Add proper mocks (OpenAI, Google API, etc.)
4. **Missing Django apps** → Create Django app with startapp command
5. **Missing imports** → Add missing import statements
6. **Wrong file paths** → Fix import paths and file locations
7. **Missing test dependencies** → Install pytest-django, pytest-mock, etc.
8. **Code structure issues** → Fix class/function definitions

CRITICAL RULES:
- If Django tests are failing due to "settings not configured", create proper pytest setup files
- If files are in wrong locations (e.g., tests in root instead of in app), provide correct file structure
- If external APIs (OpenAI, etc.) are being called in tests, mock them properly
- If Django app structure is missing, include command to create it
- Only flag needs_human=true if truly impossible to fix (requires credentials, manual setup, etc.)

Return JSON with:
- files_to_create: Array of {{"path": "relative/path", "content": "full file content"}}
- files_to_modify: Array of {{"path": "relative/path", "content": "new full content"}}
- files_to_delete: Array of file paths to delete
- commands_to_run: Array of shell commands to execute (in order)
- explanation: Detailed explanation of what was wrong and how you fixed it
- confidence: "high"/"medium"/"low"
- needs_human: true only if impossible to fix autonomously
- human_instructions: (only if needs_human=true) step-by-step instructions
"""

    result = generate_json(
        "You are a world-class debugging agent who ALWAYS provides autonomous fixes. You analyze test failures deeply and generate complete, working solutions. Return only valid JSON with all required fields.",
        debug_prompt
    )

    if not result or not isinstance(result, dict):
        return DebugFix(
            files_to_create=[],
            files_to_modify=[],
            files_to_delete=[],
            commands_to_run=[],
            explanation="Could not generate debug fix",
            confidence="low",
            needs_human=True,
            human_instructions="Please manually review the test failures."
        )

    return DebugFix(
        files_to_create=result.get("files_to_create", []),
        files_to_modify=result.get("files_to_modify", []),
        files_to_delete=result.get("files_to_delete", []),
        commands_to_run=result.get("commands_to_run", []),
        explanation=result.get("explanation", "Unknown fix"),
        confidence=result.get("confidence", "low"),
        needs_human=result.get("needs_human", False),
        human_instructions=result.get("human_instructions")
    )
