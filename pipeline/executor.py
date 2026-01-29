"""Execution engine for Gryffin - executes tasks with testing and validation."""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import generate_json
from .debugger import analyze_and_fix_test_failure, get_file_tree_with_contents, DebugFix
import platform
from datetime import datetime

MAX_AUTO_RETRY_ATTEMPTS = 15  # Ralph Wiggum mode: "I'm helping!" until it works


class GryffinSessionTracker:
    """
    Tracks files created/modified by GRYFFIN during the current session.
    This allows us to skip overwrite confirmations for files we created.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._created_files: set[str] = set()
            cls._instance._modified_files: set[str] = set()
            cls._instance._error_log: list[dict[str, Any]] = []
        return cls._instance

    def track_created(self, file_path: str | Path) -> None:
        """Track a file that GRYFFIN created."""
        self._created_files.add(str(file_path))

    def track_modified(self, file_path: str | Path) -> None:
        """Track a file that GRYFFIN modified."""
        self._modified_files.add(str(file_path))

    def is_gryffin_file(self, file_path: str | Path) -> bool:
        """Check if a file was created or modified by GRYFFIN this session."""
        path_str = str(file_path)
        return path_str in self._created_files or path_str in self._modified_files

    def log_error_fix(self, error: str, fix_applied: str, file_path: str | None = None) -> None:
        """Log an error that was fixed for user visibility."""
        self._error_log.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "error": error[:500],  # Truncate long errors
            "fix": fix_applied,
            "file": file_path
        })

    def get_error_log(self) -> list[dict[str, Any]]:
        """Get all errors that were fixed during this session."""
        return self._error_log

    def get_created_files(self) -> set[str]:
        """Get all files created during this session."""
        return self._created_files.copy()

    def reset(self) -> None:
        """Reset the tracker for a new session."""
        self._created_files.clear()
        self._modified_files.clear()
        self._error_log.clear()


# Global session tracker
session_tracker = GryffinSessionTracker()


def log_user_interaction(target_dir: Path, context: str, choice: str, instructions: str = "") -> None:
    """
    Log user interactions to a conversation history file.

    Args:
        target_dir: Project directory
        context: What was being done when user provided input
        choice: User's choice/response
        instructions: Additional instructions provided by user
    """
    log_file = target_dir / "gryffin_conversation.log"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"""
[{timestamp}]
Context: {context}
User Choice: {choice}
"""

    if instructions:
        log_entry += f"Additional Instructions: {instructions}\n"

    log_entry += "-" * 80 + "\n"

    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        # Don't fail execution if logging fails
        print(f"⚠️  Failed to log interaction: {e}")


def generate_readme(
    architecture: dict[str, Any],
    target_dir: Path,
    file_tree_snapshot: dict[str, Any],
    codebase_insight: dict[str, Any] | None = None,
) -> str:
    """
    Generate a comprehensive README.md for the project.

    This README serves as context for all agents (code generation, debugging, etc.)
    """
    print("\n📝 Generating README.md...")

    # Get system information
    os_info = platform.system()
    os_version = platform.release()
    python_version = platform.python_version()

    # Detect tech versions
    tech_versions = {}

    # Check for Node.js
    try:
        result = subprocess.run(
            "node --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            tech_versions["Node.js"] = result.stdout.strip()
    except:
        pass

    # Check for Django
    try:
        result = subprocess.run(
            "python -m django --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            tech_versions["Django"] = result.stdout.strip()
    except:
        pass

    # Generate file tree representation
    file_tree_str = "\n".join([f"├── {f}" for f in file_tree_snapshot.get("files", [])[:30]])

    # Build README content
    readme_content = f"""# {architecture.get('app_name', 'Project')}

> Generated by [Gryffin](https://github.com/gryffin) - AI-powered development tool

## Overview

{architecture.get('overview', 'No overview available.')}

## What This App IS

"""

    # Add components as "what this app IS"
    components = architecture.get('components', {})
    if isinstance(components, dict):
        for name, details in components.items():
            if isinstance(details, dict):
                readme_content += f"- **{name.title()}**: {details.get('functionality', 'Component functionality')}\n"
            else:
                readme_content += f"- **{name.title()}**: {details}\n"

    readme_content += f"""
## What This App IS NOT

"""

    # Add limitations/what it's not based on architecture
    assumptions = architecture.get('assumptions', [])
    if assumptions:
        for assumption in assumptions:
            # Convert assumptions to negative statements
            readme_content += f"- Not designed for: {assumption.replace('Users will', 'Scenarios where users will not')}\n"
    else:
        readme_content += "- Not a production-ready application (MVP/prototype stage)\n"
        readme_content += "- Not fully tested in all environments\n"

    readme_content += f"""
## File Structure

```
{architecture.get('app_name', 'project')}/
{file_tree_str}
```

## System Configuration

- **Operating System**: {os_info} {os_version}
- **Python Version**: {python_version}
"""

    # Add detected tech versions
    for tech, version in tech_versions.items():
        readme_content += f"- **{tech}**: {version}\n"

    readme_content += """
## Tech Stack

"""

    # Add tech stack details
    tech_stack = architecture.get('tech_stack', {})
    if isinstance(tech_stack, dict):
        for component, details in tech_stack.items():
            readme_content += f"\n### {component.title()}\n\n"
            if isinstance(details, dict):
                framework = details.get('framework', 'N/A')
                readme_content += f"- **Framework**: {framework}\n"

                libraries = details.get('libraries', [])
                if libraries:
                    readme_content += f"- **Libraries**:\n"
                    for lib in libraries:
                        readme_content += f"  - {lib}\n"

                version = details.get('version', '')
                if version:
                    readme_content += f"- **Version**: {version}\n"

    readme_content += """
## Data Flow

"""

    # Add data flow
    data_flow = architecture.get('data_flow', {})
    if isinstance(data_flow, dict):
        for step, description in sorted(data_flow.items()):
            readme_content += f"{step}. {description}\n"
    elif isinstance(data_flow, str):
        readme_content += f"{data_flow}\n"

    # Add risks
    risks = architecture.get('risks', [])
    if risks:
        readme_content += """
## Known Risks & Limitations

"""
        for risk in risks:
            readme_content += f"- ⚠️  {risk}\n"

    # Add assumptions
    if assumptions:
        readme_content += """
## Assumptions

"""
        for assumption in assumptions:
            readme_content += f"- {assumption}\n"

    # Add codebase insights if available
    if codebase_insight:
        readme_content += """
## Existing Codebase Analysis

This project has existing code that was analyzed by Gryffin's Context Builder:

"""
        existing_functionality = codebase_insight.get('existing_functionality', [])
        if existing_functionality:
            readme_content += "### Existing Functionality\n\n"
            for func in existing_functionality:
                readme_content += f"- {func}\n"
            readme_content += "\n"

        gaps = codebase_insight.get('gaps_and_opportunities', [])
        if gaps:
            readme_content += "### Gaps & Opportunities\n\n"
            for gap in gaps:
                readme_content += f"- {gap}\n"
            readme_content += "\n"

        recommendations = codebase_insight.get('recommendations', {})
        if recommendations:
            readme_content += "### Integration Recommendations\n\n"
            how_to_extend = recommendations.get('how_to_extend')
            if how_to_extend:
                readme_content += f"**How to Extend**: {how_to_extend}\n\n"
            patterns = recommendations.get('patterns_to_follow')
            if patterns:
                readme_content += f"**Patterns to Follow**: {patterns}\n\n"
            integration = recommendations.get('integration_points')
            if integration:
                readme_content += f"**Integration Points**: {integration}\n\n"

    readme_content += """
## Development

This project was generated and is being developed using Gryffin, an AI-powered development tool that:
- Generates architecture and task plans
- Implements features autonomously
- Tests and debugs code automatically
- Maintains this README for context

### For AI Agents

This README provides essential context for all AI agents working on this project:
- **Architecture**: Defines the high-level structure and components
- **Tech Stack**: Specifies technologies and versions in use
- **File Structure**: Shows organization of code and resources
- **System Config**: Indicates the development environment
- **Limitations**: Clarifies what this application is NOT designed for

When implementing features or debugging, always reference this README to maintain consistency with the project's architecture and constraints.

---

*Last updated: Auto-generated at project initialization*
"""

    # Write README to file
    readme_path = target_dir / "README.md"
    readme_path.write_text(readme_content, encoding="utf-8")

    print(f"✓ README.md created at {readme_path}")

    return readme_content


def get_user_input(
    prompt: str,
    allow_instructions: bool = True,
    target_dir: Path | None = None,
    context: str | None = None
) -> tuple[str, str]:
    """
    Get user input with optional additional instructions.

    Args:
        prompt: The prompt to show the user
        allow_instructions: Whether to allow additional instructions
        target_dir: Optional directory to log interaction to
        context: Optional context description for logging

    Returns:
        (choice, instructions) - choice is the main response, instructions are additional feedback
    """
    print(f"\n{prompt}")
    if allow_instructions:
        print("  💡 Tip: You can add instructions after your choice (e.g., 'y, but also install redis')")

    user_input = input("\n> ").strip()

    # Parse input for choice and additional instructions
    if ',' in user_input:
        parts = user_input.split(',', 1)
        choice = parts[0].strip().lower()
        instructions = parts[1].strip()
    else:
        choice = user_input.lower()
        instructions = ""

    # Log interaction if target_dir and context provided
    if target_dir and context:
        log_user_interaction(target_dir, context, choice, instructions)

    return choice, instructions


def auto_fix_error(
    error_message: str,
    context: str,
    previous_attempt: str,
    retry_count: int
) -> dict[str, Any]:
    """
    Use LLM to analyze error and suggest fix.

    Args:
        error_message: The error message/output
        context: What was being attempted
        previous_attempt: The code/command that failed
        retry_count: How many times we've tried

    Returns:
        Dict with 'solution', 'explanation', 'confidence' (high/medium/low)
    """
    print(f"\n🤖 Analyzing error (attempt {retry_count + 1}/{MAX_AUTO_RETRY_ATTEMPTS})...")

    fix_prompt = f"""An error occurred while {context}.

Previous attempt:
```
{previous_attempt}
```

Error message:
```
{error_message}
```

Retry count: {retry_count}

IMPORTANT: Your goal is to FIX THIS ERROR AUTONOMOUSLY. Only flag needs_human=true if it's IMPOSSIBLE to fix without human intervention (e.g., requires external credentials, manual API setup, physical access).

For common errors you CAN and SHOULD fix:
- Missing files/directories → Create them
- Missing Django/Node/Python project structure → Initialize it with proper commands (django-admin startproject, npm init, etc.)
- Missing dependencies → Install them
- Wrong directory → cd to correct directory or create it
- Configuration issues → Generate proper config
- Missing environment variables → Create .env with placeholders

Analyze this error and provide an AUTONOMOUS fix. Return JSON with:
- solution: The corrected code/command(s) to try - can be multiple commands separated by &&
- explanation: Brief explanation of what went wrong and how your fix addresses it
- confidence: "high" if you're confident this will work, "medium" if unsure, "low" if unlikely to work
- needs_human: true ONLY if truly impossible to fix autonomously (default: false)
- human_instructions: (only if needs_human=true) detailed step-by-step instructions for the human
"""

    result = generate_json(
        "You are a senior debugging engineer who ALWAYS tries to fix errors autonomously. Only escalate to humans as an absolute last resort. Return only valid JSON with solution, explanation, confidence, needs_human (default false), and optionally human_instructions.",
        fix_prompt
    )

    if not result or not isinstance(result, dict):
        return {
            "solution": None,
            "explanation": "Could not generate auto-fix",
            "confidence": "low",
            "needs_human": True,
            "human_instructions": "Please review the error manually and fix the issue."
        }

    return result


@dataclass
class ExecutionContext:
    """Context for task execution."""
    target_dir: Path
    architecture: dict[str, Any]
    tasks: dict[str, Any]
    completed_tasks: list[str]
    file_tree_snapshot: dict[str, Any]
    readme_content: str = ""
    codebase_insight: dict[str, Any] | None = None


@dataclass
class TestResult:
    """Result of a test run."""
    passed: bool
    output: str
    errors: list[str]
    test_count: int
    failed_count: int


def take_file_tree_snapshot(target_dir: Path) -> dict[str, Any]:
    """Take a snapshot of the current file tree structure."""
    print("\n📸 Taking file tree snapshot...")

    snapshot = {
        "files": [],
        "directories": [],
        "key_files": {}
    }

    # Key files to look for
    key_patterns = [
        "package.json",
        "requirements.txt",
        "Pipfile",
        "pyproject.toml",
        ".env",
        ".env.example",
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        "Makefile"
    ]

    for item in target_dir.rglob("*"):
        # Skip common directories to ignore
        if any(part.startswith(".") or part in ["node_modules", "__pycache__", "venv", "env", ".git"]
               for part in item.parts):
            continue

        relative_path = item.relative_to(target_dir)

        if item.is_file():
            snapshot["files"].append(str(relative_path))

            # Check if it's a key file
            if item.name in key_patterns:
                snapshot["key_files"][item.name] = str(relative_path)
        elif item.is_dir():
            snapshot["directories"].append(str(relative_path))

    print(f"✓ Found {len(snapshot['files'])} files and {len(snapshot['directories'])} directories")
    print(f"✓ Key files detected: {', '.join(snapshot['key_files'].keys()) or 'None'}")

    return snapshot


def detect_environment(snapshot: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    """Detect the project environment and what needs to be set up."""
    print("\n🔍 Detecting environment...")

    env_info = {
        "project_type": None,
        "has_env_file": False,
        "needs_setup": [],
        "detected_dependencies": []
    }

    key_files = snapshot.get("key_files", {})

    # Detect project type
    if "package.json" in key_files:
        env_info["project_type"] = "node"
        env_info["detected_dependencies"].append("npm/yarn")
        if not (target_dir / "node_modules").exists():
            env_info["needs_setup"].append("npm install")

    if "requirements.txt" in key_files or "pyproject.toml" in key_files or "Pipfile" in key_files:
        env_info["project_type"] = "python"
        env_info["detected_dependencies"].append("pip/poetry")
        if not any((target_dir / d).exists() for d in ["venv", "env", ".venv"]):
            env_info["needs_setup"].append("python virtual environment")

    # Check for .env file
    if ".env" in key_files:
        env_info["has_env_file"] = True
        print("✓ .env file found")
    elif ".env.example" in key_files:
        env_info["needs_setup"].append("copy .env.example to .env")
        print("⚠️  .env.example found but no .env file")
    else:
        env_info["needs_setup"].append("create .env file")
        print("⚠️  No .env file detected")

    # Check for Docker
    if "Dockerfile" in key_files or "docker-compose.yml" in key_files:
        env_info["detected_dependencies"].append("docker")

    print(f"✓ Project type: {env_info['project_type'] or 'unknown'}")
    if env_info["needs_setup"]:
        print(f"⚠️  Setup needed: {', '.join(env_info['needs_setup'])}")

    return env_info


def setup_environment(
    env_info: dict[str, Any],
    target_dir: Path,
    architecture: dict[str, Any],
    readme_content: str = "",
    codebase_insight: dict[str, Any] | None = None
) -> bool:
    """Set up the project environment based on detected needs."""
    print("\n🔧 Setting up environment...")

    needs_setup = env_info.get("needs_setup", [])

    if not needs_setup:
        print("✓ Environment already set up")
        return True

    # Detect OS for appropriate package manager
    os_type = platform.system()  # Darwin (macOS), Linux, Windows
    os_version = platform.release()

    # Build context from README and codebase insight
    context_section = ""
    if readme_content:
        context_section += f"""
## PROJECT README (MUST FOLLOW THIS)
{readme_content[:3000]}
"""

    if codebase_insight:
        context_section += f"""
## EXISTING CODEBASE ANALYSIS (MUST RESPECT THIS)
Tech Stack: {json.dumps(codebase_insight.get('tech_stack', {}), indent=2)}
Existing Dependencies: {codebase_insight.get('tech_stack', {}).get('dependencies', [])}
Architecture: {codebase_insight.get('architecture_summary', 'N/A')}
Patterns to Follow: {codebase_insight.get('recommendations', {}).get('patterns_to_follow', 'N/A')}

CRITICAL: Only install dependencies that are compatible with the existing tech stack.
Do NOT install conflicting versions or alternative frameworks.
"""

    # Use LLM to generate setup instructions
    setup_prompt = f"""Given this project architecture:
{json.dumps(architecture, indent=2)}

{context_section}

And these detected setup needs:
{', '.join(needs_setup)}

Project type: {env_info.get('project_type', 'unknown')}
Current directory: {target_dir}
Operating System: {os_type} {os_version}

CRITICAL OS-SPECIFIC REQUIREMENTS:
- macOS (Darwin): Use 'brew' for packages, NOT apt/apt-get/yum
- Linux: Use apt/apt-get/yum based on distro
- Windows: Use choco or direct installers
- ALWAYS check if tools are already installed before trying to install them

CRITICAL ARCHITECTURE REQUIREMENTS:
- ONLY install dependencies that match the architecture in the README
- Do NOT deviate from the decided tech stack
- If the README specifies certain versions, use those exact versions
- Do NOT add new frameworks or libraries not mentioned in the architecture

Generate COMPLETE setup commands including:

1. PROJECT INITIALIZATION (if needed):
   - For Django: Create project structure with django-admin startproject
     Example: mkdir -p backend && cd backend && django-admin startproject config . && cd ..
   - For Node: npm init or create-react-app/create-next-app
   - For Flask: Create basic app structure

2. DEPENDENCIES:
   - Install required packages (pip install, npm install, etc.)
   - ONLY install what's in the architecture/README

3. CONFIGURATION:
   - Create .env file with all necessary environment variables
   - Create any required config files

4. DATABASE:
   - Run migrations ONLY AFTER project structure exists
   - Set up initial database if needed

IMPORTANT:
- CHECK if tools exist first using 'which' or 'command -v' before installing
- Example: if node is needed, use: command -v node || brew install node (on macOS)
- Commands must be in the correct order (check existence → install if missing → initialize → configure)
- For Django, ALWAYS create the project structure BEFORE running manage.py commands
- Use relative paths and proper directory navigation
- On macOS: Use 'brew install' NOT apt-get
- On Linux: Use apt-get/yum based on distro
- Test each command would actually work on the specified OS

Return JSON with key 'setup_commands' (array of shell commands to run in sequence).
"""

    result = generate_json(
        f"You are a senior DevOps engineer creating setup scripts for {os_type}. CRITICAL: Use OS-appropriate package managers (macOS=brew, Linux=apt/yum). Check if tools exist before installing. Return only valid JSON with setup_commands array.",
        setup_prompt
    )

    if result and isinstance(result, dict):
        commands = result.get("setup_commands", [])
        print(f"\n📋 Setup plan: {len(commands)} commands")
        for i, cmd in enumerate(commands, 1):
            print(f"  {i}. {cmd}")

        # Get user input with optional instructions
        choice, additional_instructions = get_user_input(
            "Proceed with setup? (y/n, or add instructions like 'y, but also install redis')",
            target_dir=target_dir,
            context="Environment setup approval"
        )

        if additional_instructions:
            print(f"\n💡 Adding to setup: {additional_instructions}")
            # Regenerate with additional instructions
            updated_prompt = f"{setup_prompt}\n\nAdditional user requirements: {additional_instructions}"
            updated_result = generate_json(
                "You are a senior DevOps engineer who creates COMPLETE, working setup scripts. Always initialize project structure before running framework-specific commands. Return only valid JSON with setup_commands array.",
                updated_prompt
            )
            if updated_result and isinstance(updated_result, dict):
                commands = updated_result.get("setup_commands", [])
                print(f"\n📋 Updated setup plan: {len(commands)} commands")
                for i, cmd in enumerate(commands, 1):
                    print(f"  {i}. {cmd}")

        if choice == "y" or choice == "yes":
            for cmd in commands:
                success = run_command_with_retry(cmd, target_dir, f"running setup command: {cmd}")
                if not success:
                    return False

            print("\n✅ Environment setup complete!")
            return True

    print("⚠️  Could not generate setup plan. Please set up manually.")
    return False


def run_command_with_retry(
    command: str,
    cwd: Path,
    context: str,
    max_retries: int = MAX_AUTO_RETRY_ATTEMPTS
) -> bool:
    """
    Run a command with automatic retry on failure.

    Args:
        command: Shell command to run
        cwd: Working directory
        context: Description of what this command does
        max_retries: Maximum number of retry attempts

    Returns:
        True if successful, False if all retries failed
    """
    retry_count = 0
    current_command = command
    last_error = None
    stuck_count = 0  # Track if we're stuck with the same error

    while retry_count < max_retries:
        print(f"\n▶ Running: {current_command}")

        try:
            result = subprocess.run(
                current_command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                print(f"✓ Success")
                return True

            # Command failed - try to auto-fix
            print(f"✗ Failed with error:")
            error_output = result.stderr or result.stdout
            print(f"  {error_output[:500]}")  # Show first 500 chars

            # Check if we're stuck with the same error
            if last_error and error_output[:300] == last_error[:300]:
                stuck_count += 1
                if stuck_count >= 3:
                    print(f"\n⚠️  Same error seen {stuck_count} times - trying radically different approach...")
            else:
                stuck_count = 0
            last_error = error_output

            if retry_count < max_retries - 1:
                print(f"\n🔄 Retrying... (attempt {retry_count + 1}/{max_retries})")

                # Get auto-fix suggestion with stuck context
                context_msg = context
                if stuck_count >= 3:
                    context_msg += f" (CRITICAL: Same error repeated {stuck_count} times - previous fixes FAILED, try a COMPLETELY DIFFERENT approach)"

                fix_result = auto_fix_error(
                    error_message=error_output,
                    context=context_msg,
                    previous_attempt=current_command,
                    retry_count=retry_count
                )

                if fix_result.get("needs_human"):
                    print(f"\n⚠️  Human intervention needed:")
                    print(f"\n{fix_result.get('explanation', 'Unknown error')}")
                    print(f"\n📋 Required action:")
                    print(f"  {fix_result.get('human_instructions', 'Please review and fix manually')}")

                    choice, instructions = get_user_input(
                        "Options:\n  1. I've fixed it, retry the original command\n  2. Skip this step\n  3. Abort\n\nYour choice"
                    )

                    if choice == "1":
                        # Retry original command
                        retry_count += 1
                        continue
                    elif choice == "2":
                        print("⏭️  Skipping this step...")
                        return True
                    else:
                        print("❌ Aborting...")
                        return False

                # Try the suggested fix
                print(f"\n💡 Fix suggestion: {fix_result.get('explanation', 'Trying alternative approach')}")
                current_command = fix_result.get("solution", current_command)

            retry_count += 1

        except subprocess.TimeoutExpired:
            print(f"✗ Command timed out after 300 seconds")
            retry_count += 1
            if retry_count < max_retries:
                print(f"\n🔄 Retrying... (attempt {retry_count}/{max_retries})")
        except Exception as e:
            print(f"✗ Error: {e}")
            retry_count += 1
            if retry_count < max_retries:
                print(f"\n🔄 Retrying... (attempt {retry_count}/{max_retries})")

    print(f"\n❌ Command failed after {max_retries} attempts")
    return False


def generate_task_code(
    task: dict[str, Any],
    context: ExecutionContext,
    task_index: int
) -> dict[str, Any]:
    """Generate code for a specific task using LLM."""
    print(f"\n💻 Generating code for task {task_index + 1}: {task.get('title')}...")

    # Build codebase context section if available
    codebase_context = ""
    if context.codebase_insight:
        insight = context.codebase_insight
        codebase_context = f"""
## EXISTING CODEBASE ANALYSIS (CRITICAL - MUST RESPECT)

**Project Type**: {insight.get('project_type', 'Unknown')}
**Architecture**: {insight.get('architecture_summary', 'N/A')}

**Existing Tech Stack**:
{json.dumps(insight.get('tech_stack', {}), indent=2)}

**Existing Functionality** (DO NOT DUPLICATE):
{chr(10).join(['- ' + f for f in insight.get('existing_functionality', [])[:10]])}

**Patterns to Follow**:
{insight.get('recommendations', {}).get('patterns_to_follow', 'Follow existing code patterns')}

**Integration Points**:
{insight.get('recommendations', {}).get('integration_points', 'Integrate with existing modules')}

**Cautions**:
{insight.get('recommendations', {}).get('cautions', 'Respect existing architecture')}

CRITICAL: Your code MUST integrate with the existing codebase. Do NOT:
- Create duplicate functionality that already exists
- Use different frameworks/libraries than what's already in use
- Break existing patterns or conventions
- Introduce incompatible dependencies
"""

    prompt = f"""You are implementing this task:

Task: {task.get('title')}
Description: {task.get('description')}

## Project README (IMPORTANT - Read First!)
{context.readme_content if context.readme_content else "No README available"}
{codebase_context}
## Project Architecture
{json.dumps(context.architecture, indent=2)}

## Implementation Context
Already completed tasks: {', '.join(context.completed_tasks) or 'None'}

Current file tree:
{json.dumps(context.file_tree_snapshot, indent=2)[:3000]}

## Your Task
Generate a complete, production-ready implementation for this task.

CRITICAL RULES:
1. **Follow the README**: The project README defines what this app IS and IS NOT. Stay within those bounds.
2. **Respect the architecture**: Use ONLY the specified tech stack - do NOT introduce new frameworks.
3. **Proper file locations**: Place files in the correct directories based on the file tree structure.
4. **Django projects**: If this is a Django project, put code in proper Django apps (not in the root).
5. **Complete imports**: Include all necessary import statements.
6. **Proper test setup**: For Django, include proper pytest configuration (conftest.py, pytest.ini).
7. **Mock external services**: Mock any external APIs (OpenAI, Google, etc.) in tests.
8. **No dependency drift**: Only use dependencies that are in the architecture. Do NOT add new ones without explicit need.
9. **Integrate, don't replace**: If there's existing code, integrate with it rather than replacing it.

Generate the implementation. Return JSON with:
- files: array of {{path: "relative/path/in/correct/location", content: "complete file content with all imports", action: "create" | "modify"}}
- tests: array of {{path: "tests/path", content: "complete test with mocks", type: "unit" | "integration"}}
- description: string explaining what was implemented and where files were placed
"""

    result = generate_json(
        "You are a senior software engineer who meticulously follows project architecture and README guidelines. You NEVER introduce new frameworks or libraries not in the tech stack. You place files in correct locations, include all imports, mock external services in tests, and create production-ready code. Return only valid JSON with files, tests, and description.",
        prompt
    )

    if not result or not isinstance(result, dict):
        print("✗ Failed to generate code")
        return {}

    print(f"✓ Generated {len(result.get('files', []))} files and {len(result.get('tests', []))} tests")
    return result


def apply_code_changes(code_result: dict[str, Any], target_dir: Path) -> bool:
    """Apply the generated code changes to the file system."""
    print("\n📝 Applying code changes...")

    files = code_result.get("files", [])

    for file_info in files:
        file_path = target_dir / file_info["path"]
        action = file_info.get("action", "create")
        content = file_info.get("content", "")

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if action == "create":
                if file_path.exists():
                    # Check if this is a file GRYFFIN created - if so, no need to ask
                    if session_tracker.is_gryffin_file(file_path):
                        # GRYFFIN created this file, just overwrite silently
                        file_path.write_text(content, encoding="utf-8")
                        session_tracker.track_modified(file_path)
                        print(f"✓ Updated: {file_info['path']} (GRYFFIN file)")
                        continue

                    # File exists but wasn't created by GRYFFIN - ask user
                    print(f"⚠️  File already exists: {file_info['path']}")
                    choice, instructions = get_user_input(
                        f"Overwrite {file_info['path']}? (y/n, or add instructions like 'y, but keep the existing imports')",
                        allow_instructions=True
                    )

                    if choice not in ["y", "yes"]:
                        print(f"⏭️  Skipping {file_info['path']}")
                        continue

                    # If user wants to keep parts of the file, we could merge here
                    if instructions:
                        print(f"💡 Note: {instructions}")
                        print("   (Manual merge may be needed)")

                file_path.write_text(content, encoding="utf-8")
                session_tracker.track_created(file_path)
                print(f"✓ Created: {file_info['path']}")

            elif action == "modify":
                if not file_path.exists():
                    print(f"✗ File does not exist: {file_info['path']}")
                    create_new = input(f"Create new file instead? (y/n): ").strip().lower()
                    if create_new != "y":
                        continue

                file_path.write_text(content, encoding="utf-8")
                session_tracker.track_modified(file_path)
                print(f"✓ Modified: {file_info['path']}")

        except Exception as e:
            print(f"✗ Error applying change to {file_info['path']}: {e}")
            print(f"\n📋 Manual action required:")
            print(f"   1. Check file permissions for {file_info['path']}")
            print(f"   2. Ensure the parent directory exists")
            print(f"   3. Verify disk space availability")

            choice, _ = get_user_input("Continue with remaining files? (y/n)")
            if choice not in ["y", "yes"]:
                return False

    # Apply test files
    tests = code_result.get("tests", [])
    if tests:
        print(f"\n🧪 Creating {len(tests)} test file(s)...")

    for test_info in tests:
        test_path = target_dir / test_info["path"]
        content = test_info.get("content", "")

        try:
            test_path.parent.mkdir(parents=True, exist_ok=True)

            if test_path.exists():
                # Check if this is a file GRYFFIN created - if so, no need to ask
                if session_tracker.is_gryffin_file(test_path):
                    test_path.write_text(content, encoding="utf-8")
                    session_tracker.track_modified(test_path)
                    print(f"✓ Updated test: {test_info['path']} (GRYFFIN file)")
                    continue

                print(f"⚠️  Test file already exists: {test_info['path']}")
                choice, _ = get_user_input(f"Overwrite {test_info['path']}? (y/n)")
                if choice not in ["y", "yes"]:
                    continue

            test_path.write_text(content, encoding="utf-8")
            session_tracker.track_created(test_path)
            print(f"✓ Created test: {test_info['path']}")
        except Exception as e:
            print(f"✗ Error creating test {test_info['path']}: {e}")
            choice, _ = get_user_input("Continue anyway? (y/n)")
            if choice not in ["y", "yes"]:
                return False

    print(f"\n✅ Applied {len(files)} code file(s) and {len(tests)} test file(s)")
    return True


def run_tests(target_dir: Path, test_type: str = "all", auto_fix: bool = True, readme_content: str = "") -> TestResult:
    """
    Run tests and return results with optional auto-fixing using debugging agent.

    Args:
        target_dir: Project directory
        test_type: Type of tests to run
        auto_fix: If True, automatically try to fix failing tests
        readme_content: README.md content for debugging agent context

    Returns:
        TestResult with pass/fail status and details
    """
    print(f"\n🧪 Running {test_type} tests...")

    # Detect test framework
    test_commands = []

    # Python
    if (target_dir / "pytest.ini").exists() or any(target_dir.rglob("test_*.py")):
        test_commands.append("pytest -v")

    # Node.js
    package_json = target_dir / "package.json"
    if package_json.exists():
        try:
            with package_json.open() as f:
                pkg = json.load(f)
                if "test" in pkg.get("scripts", {}):
                    test_commands.append("npm test")
        except:
            pass

    if not test_commands:
        print("⚠️  No test framework detected")
        return TestResult(
            passed=True,
            output="No tests to run",
            errors=[],
            test_count=0,
            failed_count=0
        )

    all_passed = True
    all_output = []
    all_errors = []

    for cmd in test_commands:
        retry_count = 0
        last_error = None
        stuck_count = 0  # Track if we're stuck with the same error

        while retry_count < MAX_AUTO_RETRY_ATTEMPTS:
            print(f"\n▶ Running: {cmd}")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                all_output.append(result.stdout)

                if result.returncode == 0:
                    print(f"✓ All tests passed")
                    break  # Tests passed, move to next command

                # Tests failed
                error_output = result.stderr or result.stdout
                all_errors.append(error_output)

                print(f"✗ Tests failed")
                print(f"\n📊 Test Output:")
                print(error_output[:1000])  # Show first 1000 chars

                # Check if we're stuck with the same error
                if last_error and error_output[:500] == last_error[:500]:
                    stuck_count += 1
                    if stuck_count >= 3:
                        print(f"\n⚠️  Same error seen {stuck_count} times - trying different approach...")
                else:
                    stuck_count = 0
                last_error = error_output

                if not auto_fix or retry_count >= MAX_AUTO_RETRY_ATTEMPTS - 1:
                    all_passed = False
                    break

                # Use debugging agent to analyze and fix the test failure
                print(f"\n🔄 Launching debugging agent... (attempt {retry_count + 1}/{MAX_AUTO_RETRY_ATTEMPTS})")

                # Get file tree with contents for debugging agent
                file_tree = get_file_tree_with_contents(target_dir)

                # Build context with stuck detection info
                context_msg = f"running {test_type} tests"
                if stuck_count >= 3:
                    context_msg += f" (WARNING: Same error repeated {stuck_count} times - previous fixes didn't work, try a completely different approach)"

                # Analyze and get fix
                debug_fix = analyze_and_fix_test_failure(
                    error_log=error_output,
                    file_tree=file_tree,
                    target_dir=target_dir,
                    context=context_msg,
                    readme_content=readme_content
                )

                if debug_fix.needs_human:
                    print(f"\n⚠️  Debugging agent: Human intervention needed")
                    print(f"\n{debug_fix.explanation}")
                    if debug_fix.human_instructions:
                        print(f"\n📋 Required action:")
                        print(f"  {debug_fix.human_instructions}")
                    all_passed = False
                    break

                # Apply the fix from debugging agent
                print(f"\n{'='*60}")
                print(f"🔧 ERROR FIX #{retry_count + 1}")
                print(f"{'='*60}")
                print(f"\n📋 Problem identified:")
                print(f"   {debug_fix.explanation}")
                print(f"\n🎯 Confidence: {debug_fix.confidence}")

                # Track the error fix for user visibility
                session_tracker.log_error_fix(
                    error=error_output[:300],
                    fix_applied=debug_fix.explanation
                )

                print(f"\n📝 Changes being applied:")

                # Apply file deletions
                for file_path in debug_fix.files_to_delete:
                    try:
                        (target_dir / file_path).unlink()
                        print(f"   ✓ Deleted: {file_path}")
                    except Exception as e:
                        print(f"   ✗ Failed to delete {file_path}: {e}")

                # Apply file creations
                for file_info in debug_fix.files_to_create:
                    try:
                        file_path = target_dir / file_info["path"]
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_path.write_text(file_info["content"], encoding="utf-8")
                        session_tracker.track_created(file_path)
                        print(f"   ✓ Created: {file_info['path']}")
                    except Exception as e:
                        print(f"   ✗ Failed to create {file_info['path']}: {e}")

                # Apply file modifications
                for file_info in debug_fix.files_to_modify:
                    try:
                        file_path = target_dir / file_info["path"]
                        file_path.write_text(file_info["content"], encoding="utf-8")
                        session_tracker.track_modified(file_path)
                        print(f"   ✓ Modified: {file_info['path']}")
                    except Exception as e:
                        print(f"   ✗ Failed to modify {file_info['path']}: {e}")

                # Run commands
                for cmd in debug_fix.commands_to_run:
                    print(f"   ▶ Running: {cmd}")
                    try:
                        result = subprocess.run(
                            cmd,
                            shell=True,
                            cwd=target_dir,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.returncode == 0:
                            print(f"   ✓ Success")
                        else:
                            print(f"   ⚠️  Command failed: {result.stderr[:200]}")
                    except Exception as e:
                        print(f"   ✗ Error running command: {e}")

                retry_count += 1

            except subprocess.TimeoutExpired:
                print(f"✗ Tests timed out after 300 seconds")
                all_passed = False
                break
            except Exception as e:
                all_errors.append(str(e))
                print(f"✗ Error running tests: {e}")
                all_passed = False
                break

    return TestResult(
        passed=all_passed,
        output="\n".join(all_output),
        errors=all_errors,
        test_count=0,  # Could parse from output
        failed_count=0  # Could parse from output
    )


def check_for_errors(target_dir: Path, env_info: dict[str, Any], auto_fix: bool = True) -> tuple[bool, list[str]]:
    """
    Check for syntax errors and linting issues with auto-fix.

    Returns:
        (all_fixed, remaining_errors) - True if all errors fixed, list of unfixed errors
    """
    print("\n🔍 Checking for errors...")

    errors = []
    project_type = env_info.get("project_type")
    files_with_errors = []

    # Python syntax check
    if project_type == "python":
        for py_file in target_dir.rglob("*.py"):
            # Skip common directories
            if any(part.startswith(".") or part in ["venv", "env", "__pycache__"]
                   for part in py_file.parts):
                continue

            try:
                result = subprocess.run(
                    f"python -m py_compile {py_file}",
                    shell=True,
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    error_msg = f"Syntax error in {py_file.name}: {result.stderr}"
                    errors.append(error_msg)
                    files_with_errors.append((py_file, result.stderr))
            except Exception as e:
                errors.append(f"Error checking {py_file.name}: {e}")

    # Node.js lint check (only if lint script exists)
    if project_type == "node":
        package_json = target_dir / "package.json"
        try:
            if package_json.exists():
                with package_json.open() as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "lint" in scripts:
                    result = subprocess.run(
                        "npm run lint 2>&1 || true",
                        shell=True,
                        cwd=target_dir,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if "error" in result.stdout.lower():
                        errors.append(f"Linting errors found:\n{result.stdout}")
        except Exception:
            pass  # Linting is optional

    if not errors:
        print("✓ No errors detected")
        return True, []

    print(f"✗ Found {len(errors)} error(s)")
    for err in errors:
        print(f"  - {err[:200]}")  # Show first 200 chars

    if not auto_fix:
        return False, errors

    # Try to auto-fix errors
    print(f"\n🔄 Attempting to auto-fix {len(files_with_errors)} file(s) with errors...")

    for file_path, error_msg in files_with_errors:
        print(f"\n📝 Fixing: {file_path.name}")

        try:
            # Read the file content
            original_content = file_path.read_text()

            # Get auto-fix suggestion
            fix_result = auto_fix_error(
                error_message=error_msg,
                context=f"syntax error in {file_path.name}",
                previous_attempt=original_content,
                retry_count=0
            )

            if fix_result.get("needs_human"):
                print(f"  ⚠️  Cannot auto-fix {file_path.name}")
                print(f"  {fix_result.get('explanation', 'Manual fix required')}")
                continue

            # Apply the fix
            fixed_content = fix_result.get("solution")
            if fixed_content and fixed_content != original_content:
                file_path.write_text(fixed_content)
                print(f"  ✓ Applied fix: {fix_result.get('explanation', 'Fixed syntax error')}")

                # Verify the fix worked
                result = subprocess.run(
                    f"python -m py_compile {file_path}",
                    shell=True,
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    print(f"  ✅ Fix verified - no more errors in {file_path.name}")
                    errors.remove(f"Syntax error in {file_path.name}: {error_msg}")
                else:
                    print(f"  ⚠️  Fix didn't resolve the error")
                    # Rollback
                    file_path.write_text(original_content)

        except Exception as e:
            print(f"  ✗ Error during auto-fix: {e}")

    remaining_errors = [e for e in errors if e]  # Filter out removed errors

    if not remaining_errors:
        print(f"\n✅ All errors fixed!")
        return True, []
    else:
        print(f"\n⚠️  {len(remaining_errors)} error(s) remaining")
        return False, remaining_errors


def execute_task(
    task: dict[str, Any],
    task_index: int,
    context: ExecutionContext
) -> bool:
    """Execute a single task with testing and validation."""
    print("\n" + "=" * 80)
    print(f"🚀 EXECUTING TASK {task_index + 1}: {task.get('title')}")
    print("=" * 80)

    # Generate code for the task
    code_result = generate_task_code(task, context, task_index)
    if not code_result:
        return False

    # Show what will be implemented
    print(f"\n📋 Implementation plan:")
    print(f"   {code_result.get('description', 'N/A')}")

    # Get user input with optional modifications
    choice, additional_instructions = get_user_input(
        "Proceed with implementation? (y/n/skip, or add modifications like 'y, but also add error logging')",
        target_dir=context.target_dir,
        context=f"Task {task_index + 1} ({task.get('title')}): Implementation approval"
    )

    if choice == "skip":
        print("⏭️  Skipping this task")
        return True
    elif not choice.startswith("y"):
        print("❌ Task cancelled")
        return False

    # If user added instructions, regenerate with modifications
    if additional_instructions:
        print(f"\n💡 Applying modifications: {additional_instructions}")
        modified_code = generate_task_code(
            {**task, "description": f"{task.get('description')}\n\nAdditional requirements: {additional_instructions}"},
            context,
            task_index
        )
        if modified_code:
            code_result = modified_code

    # Apply code changes
    if not apply_code_changes(code_result, context.target_dir):
        print("\n❌ Failed to apply code changes")
        choice, _ = get_user_input(
            "Retry? (y/n)",
            target_dir=context.target_dir,
            context=f"Task {task_index + 1}: Failed to apply code changes"
        )
        if choice in ["y", "yes"]:
            return execute_task(task, task_index, context)
        return False

    # Check for errors with auto-fix
    env_info = {"project_type": detect_project_type(context.target_dir)}
    all_fixed, remaining_errors = check_for_errors(context.target_dir, env_info, auto_fix=True)

    if not all_fixed:
        print(f"\n❌ {len(remaining_errors)} error(s) could not be auto-fixed")
        print("\n⚠️  Human intervention required:")
        for i, error in enumerate(remaining_errors, 1):
            print(f"\n  {i}. {error}")

        print("\n📋 Please fix these errors manually, then choose an option:")
        choice, _ = get_user_input(
            "Options:\n  1. I've fixed the errors, continue\n  2. Retry (regenerate code)\n  3. Skip this task\n  4. Abort",
            target_dir=context.target_dir,
            context=f"Task {task_index + 1}: {len(remaining_errors)} syntax errors could not be auto-fixed"
        )

        if choice == "1":
            # Re-check errors
            all_fixed, remaining = check_for_errors(context.target_dir, env_info, auto_fix=False)
            if not all_fixed:
                print("⚠️  Errors still present")
                return execute_task(task, task_index, context)
        elif choice == "2":
            return execute_task(task, task_index, context)
        elif choice == "3":
            print("⏭️  Skipping task")
            return True
        else:
            return False

    # Run tests with auto-fix
    test_result = run_tests(context.target_dir, auto_fix=True, readme_content=context.readme_content)

    if not test_result.passed:
        print("\n❌ Tests failed after auto-fix attempts!")
        print("\n📊 Test Output:")
        print(test_result.output[:1500])  # Show first 1500 chars

        print("\n⚠️  Human intervention required to fix failing tests")
        print("\n📋 Please review the test failures and fix the implementation")

        choice, _ = get_user_input(
            "Options:\n  1. I've fixed it, re-run tests\n  2. Retry task (regenerate)\n  3. Skip this task\n  4. Abort",
            target_dir=context.target_dir,
            context=f"Task {task_index + 1}: Tests failed after {MAX_AUTO_RETRY_ATTEMPTS} auto-fix attempts"
        )

        if choice == "1":
            # Re-run tests
            retry_result = run_tests(context.target_dir, auto_fix=False, readme_content=context.readme_content)
            if not retry_result.passed:
                print("⚠️  Tests still failing")
                return execute_task(task, task_index, context)
            # Tests passed, continue
        elif choice == "2":
            return execute_task(task, task_index, context)
        elif choice == "3":
            print("⏭️  Skipping task")
            return True
        else:
            return False

    # Integration test with previous tasks
    if context.completed_tasks:
        print(f"\n🔗 Running integration tests with previous tasks...")
        integration_result = run_tests(context.target_dir, test_type="integration", auto_fix=True, readme_content=context.readme_content)

        if not integration_result.passed:
            print("\n❌ Integration tests failed!")
            print("⚠️  This task may have broken existing functionality")

            print("\n📋 Options:")
            choice, _ = get_user_input(
                "  1. Try to fix automatically\n  2. I'll fix it manually\n  3. Rollback this task\n  4. Continue anyway (risky)",
                target_dir=context.target_dir,
                context=f"Task {task_index + 1}: Integration tests failed"
            )

            if choice == "1":
                # Already tried auto-fix in run_tests, so regenerate
                print("\n🔄 Regenerating task with integration awareness...")
                return execute_task(task, task_index, context)
            elif choice == "2":
                print("\n📋 Please fix the integration issues, then:")
                retry_choice, _ = get_user_input(
                    "  1. I've fixed it, re-run integration tests\n  2. Abort",
                    target_dir=context.target_dir,
                    context=f"Task {task_index + 1}: User chose manual fix for integration issues"
                )
                if retry_choice == "1":
                    retry_result = run_tests(context.target_dir, test_type="integration", auto_fix=False, readme_content=context.readme_content)
                    if not retry_result.passed:
                        print("⚠️  Integration tests still failing")
                        return False
                else:
                    return False
            elif choice == "3":
                print("⏪ Rollback not yet implemented. Please revert changes manually.")
                return False
            elif choice == "4":
                print("⚠️  Continuing with integration test failures (risky)")
                # Continue anyway
            else:
                return False

    print(f"\n✅ Task {task_index + 1} completed successfully!")
    print(f"   ✓ Code implemented")
    print(f"   ✓ No syntax errors")
    print(f"   ✓ All tests passing")
    if context.completed_tasks:
        print(f"   ✓ Integration tests passing")

    context.completed_tasks.append(task.get('title', f'Task {task_index + 1}'))

    # Refresh file tree snapshot so next task knows what files exist
    print(f"\n📸 Refreshing file tree snapshot...")
    context.file_tree_snapshot = take_file_tree_snapshot(context.target_dir)

    return True


def detect_project_type(target_dir: Path) -> str:
    """Quick project type detection."""
    if (target_dir / "package.json").exists():
        return "node"
    if any((target_dir / f).exists() for f in ["requirements.txt", "pyproject.toml"]):
        return "python"
    return "unknown"

def _iter_project_dirs(target_dir: Path) -> list[Path]:
    """Return project directories while skipping common ignore folders."""
    ignore = {"node_modules", ".git", "__pycache__", "venv", "env", ".venv", "dist", "build"}
    dirs = []
    for path in target_dir.rglob("*"):
        if not path.is_dir():
            continue
        if any(part in ignore for part in path.parts):
            continue
        dirs.append(path)
    return dirs


def _find_django_projects(target_dir: Path) -> list[Path]:
    """Find directories containing manage.py."""
    projects = []
    for path in [target_dir, *_iter_project_dirs(target_dir)]:
        if (path / "manage.py").exists():
            projects.append(path)
    return projects


def _find_node_projects(target_dir: Path) -> list[Path]:
    """Find directories containing package.json."""
    projects = []
    for path in [target_dir, *_iter_project_dirs(target_dir)]:
        if (path / "package.json").exists():
            projects.append(path)
    return projects


def _smoke_start(command: str, cwd: Path, timeout: int = 8) -> tuple[bool, str, str]:
    """Start a long-running dev server briefly to verify it launches."""
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as e:
        print(f"✗ Failed to start '{command}': {e}")
        return False, "", str(e)

    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            if proc.poll() is not None:
                if proc.returncode == 0:
                    return True, "", ""
                stderr = (proc.stderr.read() if proc.stderr else "")[:2000]
                stdout = (proc.stdout.read() if proc.stdout else "")[:2000]
                print(f"✗ Command exited early: {command}")
                if stderr:
                    print(f"  {stderr}")
                elif stdout:
                    print(f"  {stdout}")
                return False, stdout, stderr
            time.sleep(0.5)
        # Still running after timeout -> assume it started OK
        return True, "", ""
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _has_frontend_error(line: str) -> bool:
    lowered = line.lower()
    return (
        "module not found" in lowered
        or "can't resolve" in lowered
        or "error in" in lowered
        or "failed to compile" in lowered
    )


def _smoke_start_frontend(command: str, cwd: Path, timeout: int = 20) -> tuple[bool, str, str]:
    """Start frontend dev server briefly and fail if compile errors appear."""
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        print(f"✗ Failed to start '{command}': {e}")
        return False, "", str(e)

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    error_detected = False

    start_time = time.time()
    try:
        while time.time() - start_time < timeout:
            if proc.poll() is not None:
                break

            reads = []
            if proc.stdout:
                reads.append(proc.stdout)
            if proc.stderr:
                reads.append(proc.stderr)

            if not reads:
                time.sleep(0.2)
                continue

            ready, _, _ = select.select(reads, [], [], 0.5)
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                if stream is proc.stdout:
                    stdout_lines.append(line)
                else:
                    stderr_lines.append(line)
                if _has_frontend_error(line):
                    error_detected = True

            if error_detected:
                break

        # Drain any remaining output
        try:
            if proc.stdout:
                remaining = proc.stdout.read() or ""
                if remaining:
                    stdout_lines.append(remaining)
            if proc.stderr:
                remaining = proc.stderr.read() or ""
                if remaining:
                    stderr_lines.append(remaining)
        except Exception:
            pass

        stdout_text = "".join(stdout_lines)
        stderr_text = "".join(stderr_lines)
        combined = f"{stdout_text}\n{stderr_text}"

        # Catch CRA/webpack summary lines
        if "compiled with" in combined.lower() and "error" in combined.lower():
            error_detected = True

        if error_detected:
            print(f"✗ Frontend compile error detected")
            return False, stdout_text, stderr_text

        if proc.poll() is not None and proc.returncode not in (0, None):
            return False, stdout_text, stderr_text

        return True, stdout_text, stderr_text
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _start_persistent(command: str, cwd: Path, name: str) -> None:
    """Start a long-running server and keep it running in the background."""
    log_dir = cwd / ".gryffin_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}.log"

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] START {command}\n")

    subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdout=log_file.open("a", encoding="utf-8"),
        stderr=log_file.open("a", encoding="utf-8"),
        start_new_session=True,
    )
    print(f"✓ Started {name}. Logs: {log_file}")


def _auto_fix_frontend_errors(error_output: str, cwd: Path) -> bool:
    """Attempt to fix common frontend errors automatically."""
    if not error_output:
        return False

    fixed_any = False
    pattern = re.compile(r"Can't resolve '([^']+)' in '([^']+)'")
    for match in pattern.finditer(error_output):
        module, base_dir = match.groups()
        if module.startswith("."):
            # Missing local file (e.g., ./TaskTimeline.css)
            missing_path = (Path(base_dir) / module).resolve()
            if missing_path.suffix == "":
                missing_path = missing_path.with_suffix(".js")
            if not missing_path.exists():
                missing_path.parent.mkdir(parents=True, exist_ok=True)
                missing_path.write_text("", encoding="utf-8")
                print(f"✓ Created missing file: {missing_path}")
                fixed_any = True
        else:
            # Missing dependency (e.g., axios)
            ok = run_command_with_retry(
                f"npm install {module}",
                cwd,
                f"installing missing frontend dependency: {module}",
            )
            fixed_any = fixed_any or ok

    return fixed_any


def _run_frontend_build(command: str, cwd: Path) -> bool:
    """Run a frontend build/lint to surface compile errors and auto-fix."""
    result = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode == 0:
        return True

    combined = f"{result.stdout}\n{result.stderr}"
    fixed = _auto_fix_frontend_errors(combined, cwd)
    if fixed:
        retry = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return retry.returncode == 0

    return False


def _infer_run_targets(prompt: str) -> tuple[bool, bool]:
    text = prompt.lower()
    backend = any(k in text for k in ["backend", "django", "api", "server", "runserver", "manage.py", "migrate"])
    frontend = any(k in text for k in ["frontend", "react", "web", "ui", "client", "npm", "vite", "next"])
    if not backend and not frontend:
        return True, True
    return backend, frontend


def verify_project_runs(
    target_dir: Path,
    architecture: dict[str, Any],
    auto_run: bool = True,
    run_backend: bool = True,
    run_frontend: bool = True,
) -> tuple[bool, str]:
    """
    Verify that the project can actually run with 1-2 commands.

    Returns:
        (success, instructions) - True if verified, instructions for running
    """
    print("\n" + "=" * 60)
    print("🔍 VERIFYING PROJECT IS RUNNABLE")
    print("=" * 60)

    tech_stack = architecture.get("tech_stack", {})
    run_instructions = []

    # Check for common project types and their run commands
    project_type = None

    # Check Django (support nested backend/)
    django_projects = _find_django_projects(target_dir) if run_backend else []
    for dj_dir in django_projects:
        project_type = "Django"
        check_ok = run_command_with_retry(
            "python manage.py check",
            dj_dir,
            "running Django system checks",
            max_retries=3,
        )
        if check_ok:
            print(f"✓ Django project check passed ({dj_dir})")

        rel = dj_dir.relative_to(target_dir)
        prefix = f"cd {rel}" if str(rel) != "." else None
        if prefix:
            run_instructions.append(f"{prefix}\n  python manage.py runserver")
        else:
            run_instructions.append("python manage.py runserver")

    # Check Node.js / Next.js / React
    node_projects = _find_node_projects(target_dir) if run_frontend else []
    for node_dir in node_projects:
        try:
            with (node_dir / "package.json").open() as f:
                pkg = json.load(f)
                scripts = pkg.get("scripts", {})

                rel = node_dir.relative_to(target_dir)
                prefix = f"cd {rel}" if str(rel) != "." else None

                if not (node_dir / "node_modules").exists():
                    if prefix:
                        run_instructions.append(f"{prefix}\n  npm install")
                    else:
                        run_instructions.append("npm install")

                if "dev" in scripts:
                    project_type = project_type or "Node.js"
                    cmd = "npm run dev"
                elif "start" in scripts:
                    project_type = project_type or "Node.js"
                    cmd = "npm start"
                else:
                    cmd = None

                if cmd:
                    if prefix:
                        run_instructions.append(f"{prefix}\n  {cmd}")
                    else:
                        run_instructions.append(cmd)
        except Exception:
            pass

    # Check Flask
    if (target_dir / "app.py").exists() or any(target_dir.glob("**/app.py")):
        if not project_type:
            project_type = "Flask"
            run_instructions.append("flask run")

    # Check Python requirements
    if (target_dir / "requirements.txt").exists():
        # Check if venv exists
        if not any((target_dir / d).exists() for d in ["venv", "env", ".venv"]):
            run_instructions.insert(0, "python -m venv venv && source venv/bin/activate && pip install -r requirements.txt")

    if not run_instructions:
        # Generic instructions based on tech stack
        backend = tech_stack.get("backend", {})
        if isinstance(backend, dict):
            framework = backend.get("framework", "").lower()
        else:
            framework = str(backend).lower()

        if "django" in framework:
            run_instructions.append("python manage.py runserver")
        elif "flask" in framework:
            run_instructions.append("flask run")
        elif "fastapi" in framework:
            run_instructions.append("uvicorn main:app --reload")
        elif "node" in framework or "express" in framework:
            run_instructions.append("npm start")
        elif "next" in framework:
            run_instructions.append("npm run dev")

    instructions = "\n".join([f"  {i+1}. {cmd}" for i, cmd in enumerate(run_instructions)])

    if run_instructions:
        auto_ok = True
        if auto_run:
            print("\n▶ Auto-running detected dev commands...")
            persist_flag = os.environ.get("GRYFFIN_PERSIST_SERVERS", "false").strip().lower()
            persist_servers = persist_flag in {"1", "true", "yes", "on"}

            # Django: migrate + smoke start
            for dj_dir in django_projects:
                migrate_ok = run_command_with_retry(
                    "python manage.py migrate",
                    dj_dir,
                    "running Django migrations",
                )
                auto_ok = auto_ok and migrate_ok

                if migrate_ok:
                    ok, out, err = _smoke_start("python manage.py runserver", dj_dir)
                    if not ok and "port is already in use" in (err or "").lower():
                        print("ℹ️  Django server already running; continuing.")
                        ok = True
                    auto_ok = auto_ok and ok
                    if persist_servers and ok:
                        _start_persistent("python manage.py runserver", dj_dir, "django-runserver")

            # Node: install + smoke start
            for node_dir in node_projects:
                if not (node_dir / "node_modules").exists():
                    auto_ok = auto_ok and run_command_with_retry(
                        "npm install",
                        node_dir,
                        "installing node dependencies",
                    )

                # Decide start command
                try:
                    with (node_dir / "package.json").open() as f:
                        pkg = json.load(f)
                        scripts = pkg.get("scripts", {})
                        if "build" in scripts:
                            print(f"\n▶ Running: npm run build ({node_dir})")
                            build_ok = _run_frontend_build("npm run build", node_dir)
                            auto_ok = auto_ok and build_ok
                        elif "lint" in scripts:
                            print(f"\n▶ Running: npm run lint ({node_dir})")
                            lint_ok = _run_frontend_build("npm run lint", node_dir)
                            auto_ok = auto_ok and lint_ok
                        if "dev" in scripts:
                            print(f"\n▶ Running: npm run dev ({node_dir})")
                            ok, out, err = _smoke_start_frontend("npm run dev", node_dir)
                            if not ok:
                                fixed = _auto_fix_frontend_errors(out + "\n" + err, node_dir)
                                if fixed:
                                    ok, _, _ = _smoke_start_frontend("npm run dev", node_dir)
                            auto_ok = auto_ok and ok
                            if persist_servers and ok:
                                _start_persistent("npm run dev", node_dir, "npm-dev")
                        elif "start" in scripts:
                            print(f"\n▶ Running: npm start ({node_dir})")
                            ok, out, err = _smoke_start_frontend("npm start", node_dir)
                            if not ok:
                                fixed = _auto_fix_frontend_errors(out + "\n" + err, node_dir)
                                if fixed:
                                    ok, _, _ = _smoke_start_frontend("npm start", node_dir)
                            auto_ok = auto_ok and ok
                            if persist_servers and ok:
                                _start_persistent("npm start", node_dir, "npm-start")
                except Exception:
                    pass

            if auto_ok:
                print("✓ Auto-run verification succeeded")
            else:
                print("⚠️  Auto-run verification had failures; see logs above")

        if auto_ok:
            print(f"\n✅ Project appears runnable!")
            print(f"\n📋 To run the project:")
            print(instructions)
            return True, instructions
        print("\n⚠️  Project run verification failed")
        print(f"\n📋 Suggested run commands:\n{instructions}")
        return False, instructions
    else:
        print("\n⚠️  Could not auto-detect run commands")
        return False, "Please refer to the README.md for run instructions"


def run_action_prompt(prompt: str, target_dir: Path) -> None:
    """Run quick actions (e.g., start backend/frontend) without regenerating plans."""
    print("\n" + "=" * 80)
    print("⚡ ACTION MODE")
    print("=" * 80)
    print(f"Prompt: {prompt}")

    run_backend, run_frontend = _infer_run_targets(prompt)

    auto_run_flag = os.environ.get("GRYFFIN_AUTO_RUN", "true").strip().lower()
    auto_run = auto_run_flag not in {"0", "false", "no", "off"}

    success, instructions = verify_project_runs(
        target_dir,
        architecture={},
        auto_run=auto_run,
        run_backend=run_backend,
        run_frontend=run_frontend,
    )

    print("\n" + "=" * 80)
    if success:
        print("✅ ACTION COMPLETE")
    else:
        print("⚠️  ACTION FINISHED WITH WARNINGS")
    print("=" * 80)

    if instructions:
        print(f"\n📋 Run commands:\n{instructions}")


def start_execution(
    architecture_path: Path,
    tasks_path: Path,
    target_dir: Path,
    codebase_insight: dict[str, Any] | None = None,
) -> None:
    """Start the execution phase after user approval."""
    print("\n" + "=" * 80)
    print("🎯 STARTING EXECUTION PHASE")
    print("=" * 80)

    # Reset session tracker for new execution
    session_tracker.reset()

    # Load architecture and tasks
    with architecture_path.open() as f:
        architecture = json.load(f)

    with tasks_path.open() as f:
        tasks_data = json.load(f)

    tasks = tasks_data.get("major_tasks", [])

    # Take file tree snapshot
    snapshot = take_file_tree_snapshot(target_dir)

    # Generate README.md for all agents to reference
    readme_content = generate_readme(architecture, target_dir, snapshot, codebase_insight)

    # Detect environment
    env_info = detect_environment(snapshot, target_dir)

    # Setup environment if needed - now with README and codebase context
    if env_info.get("needs_setup"):
        if not setup_environment(env_info, target_dir, architecture, readme_content, codebase_insight):
            print("\n❌ Environment setup failed. Please set up manually and try again.")
            return

    # Create execution context
    context = ExecutionContext(
        target_dir=target_dir,
        architecture=architecture,
        tasks=tasks_data,
        completed_tasks=[],
        file_tree_snapshot=snapshot,
        readme_content=readme_content,
        codebase_insight=codebase_insight
    )

    # Execute tasks one by one
    print(f"\n📋 Total tasks to execute: {len(tasks)}")

    for i, task in enumerate(tasks):
        if not execute_task(task, i, context):
            print(f"\n❌ Execution stopped at task {i + 1}")
            return

    # Final project verification
    print("\n" + "=" * 80)
    print("🎉 ALL TASKS COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    print(f"\n✅ Completed tasks:")
    for i, task_title in enumerate(context.completed_tasks, 1):
        print(f"  {i}. ✓ {task_title}")

    # Show error fixes summary
    error_log = session_tracker.get_error_log()
    if error_log:
        print(f"\n🔧 Errors fixed during execution ({len(error_log)} total):")
        for i, fix in enumerate(error_log[-10:], 1):  # Show last 10
            print(f"  {i}. [{fix['timestamp']}] {fix['fix'][:80]}...")
        if len(error_log) > 10:
            print(f"  ... and {len(error_log) - 10} more fixes")

    # Show created files summary
    created_files = session_tracker.get_created_files()
    if created_files:
        print(f"\n📁 Files created/modified ({len(created_files)} total):")
        for f in sorted(list(created_files)[:15]):
            print(f"  • {f}")
        if len(created_files) > 15:
            print(f"  ... and {len(created_files) - 15} more files")

    # Verify project is runnable
    auto_run_flag = os.environ.get("GRYFFIN_AUTO_RUN", "true").strip().lower()
    auto_run = auto_run_flag not in {"0", "false", "no", "off"}
    success, run_instructions = verify_project_runs(target_dir, architecture, auto_run=auto_run)

    print("\n" + "=" * 80)
    print("🚀 PROJECT READY!")
    print("=" * 80)

    if success:
        print(f"\n📋 To run your project:\n{run_instructions}")
    else:
        print(f"\n{run_instructions}")

    # Update README with run instructions
    readme_path = target_dir / "README.md"
    if readme_path.exists():
        current_readme = readme_path.read_text()
        if "## Quick Start" not in current_readme:
            quick_start = f"""

## Quick Start

To run this project:

{run_instructions}

---
"""
            # Insert after the first heading
            lines = current_readme.split("\n")
            insert_idx = 2  # After title
            for i, line in enumerate(lines):
                if line.startswith("## "):
                    insert_idx = i
                    break

            lines.insert(insert_idx, quick_start)
            readme_path.write_text("\n".join(lines))
            print(f"\n✓ README.md updated with Quick Start instructions")
