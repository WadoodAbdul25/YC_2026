"""Context Builder - Analyzes existing codebase using Gemini for deep insights."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table


console = Console()

# Files/directories to ignore
IGNORE_PATTERNS = {
    ".git",
    ".gitignore",
    "__pycache__",
    "node_modules",
    "venv",
    "env",
    ".env",
    ".venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    "*.pyc",
    "*.egg-info",
    ".DS_Store",
}

# Maximum file size to include (5MB per file)
MAX_FILE_SIZE = 5 * 1024 * 1024

# Maximum total content size (50MB total - well within Gemini's 2M token limit)
MAX_TOTAL_SIZE = 50 * 1024 * 1024


@dataclass
class CodebaseInsight:
    """Structured codebase insights from Gemini."""
    project_type: str
    existing_apps: list[str]
    tech_stack: dict[str, Any]
    architecture_summary: str
    file_structure: dict[str, Any]
    existing_functionality: list[str]
    gaps_and_opportunities: list[str]
    recommendations: dict[str, Any]
    raw_analysis: str  # Full Gemini response


def _should_ignore(path: Path, base_path: Path) -> bool:
    """Check if a path should be ignored."""
    rel_path = path.relative_to(base_path)

    # Check each part of the path
    for part in rel_path.parts:
        if part in IGNORE_PATTERNS:
            return True
        if part.startswith(".") and part not in {".gitignore", ".env.example"}:
            return True

    # Check file extensions
    if path.is_file():
        if path.suffix == ".pyc":
            return True
        if path.name in IGNORE_PATTERNS:
            return True

    return False


def collect_codebase_files(target_dir: Path) -> dict[str, str]:
    """
    Collect all files from target directory.

    Returns:
        Dict mapping relative file paths to their contents
    """
    console.print("\n[bold cyan]📂 Scanning codebase...[/bold cyan]")

    files = {}
    total_size = 0
    skipped_files = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Collecting files...", total=None)

        for item in target_dir.rglob("*"):
            if _should_ignore(item, target_dir):
                continue

            if not item.is_file():
                continue

            rel_path = str(item.relative_to(target_dir))

            try:
                # Check file size
                file_size = item.stat().st_size

                if file_size > MAX_FILE_SIZE:
                    skipped_files.append(f"{rel_path} (too large: {file_size / 1024 / 1024:.1f}MB)")
                    continue

                if total_size + file_size > MAX_TOTAL_SIZE:
                    skipped_files.append(f"{rel_path} (quota exceeded)")
                    continue

                # Try to read as text
                try:
                    content = item.read_text(encoding="utf-8")
                    files[rel_path] = content
                    total_size += file_size
                    progress.update(task, description=f"Collected {len(files)} files ({total_size / 1024 / 1024:.1f}MB)")
                except UnicodeDecodeError:
                    # Skip binary files
                    skipped_files.append(f"{rel_path} (binary)")
                    continue

            except Exception as e:
                skipped_files.append(f"{rel_path} (error: {e})")
                continue

    # Display summary
    table = Table(title="Codebase Scan Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Files Collected", str(len(files)))
    table.add_row("Total Size", f"{total_size / 1024 / 1024:.2f} MB")
    table.add_row("Files Skipped", str(len(skipped_files)))

    console.print(table)

    if skipped_files and len(skipped_files) <= 10:
        console.print(f"\n[yellow]⚠️  Skipped files:[/yellow]")
        for sf in skipped_files[:10]:
            console.print(f"  • {sf}")
    elif len(skipped_files) > 10:
        console.print(f"\n[yellow]⚠️  Skipped {len(skipped_files)} files (binary, too large, or quota exceeded)[/yellow]")

    return files


def get_gemini_client() -> Any:
    """Get Gemini API client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found in environment variables")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai package not installed. "
            "Install with: pip install google-generativeai"
        )


def analyze_with_gemini(files: dict[str, str], target_dir: Path) -> dict[str, Any]:
    """
    Send codebase to Gemini for analysis.

    Args:
        files: Dict of file paths to contents
        target_dir: Target directory path

    Returns:
        Parsed JSON response from Gemini
    """
    console.print("\n[bold cyan]🤖 Analyzing codebase with Gemini 2.0 Flash...[/bold cyan]")

    genai = get_gemini_client()

    # Build the prompt with full codebase context
    file_contents = []
    for path, content in sorted(files.items()):
        file_contents.append(f"=== FILE: {path} ===\n{content}\n")

    full_codebase = "\n".join(file_contents)

    prompt = f"""You are an expert code analyst. Analyze this entire codebase and provide comprehensive insights.

# CODEBASE CONTENTS

{full_codebase}

# YOUR TASK

Analyze this codebase deeply and return a JSON object with the following structure:

{{
  "project_type": "string - e.g., 'Django Python Backend', 'React Frontend', 'Full-stack Node.js'",
  "existing_apps": ["list of existing apps/modules/components"],
  "tech_stack": {{
    "backend": "string or null",
    "frontend": "string or null",
    "database": "string or null",
    "dependencies": ["key dependencies"],
    "frameworks": ["frameworks in use"]
  }},
  "architecture_summary": "string - 2-3 sentence overview of how the system is structured",
  "file_structure": {{
    "source_files": ["key source files"],
    "config_files": ["configuration files"],
    "test_files": ["test files"],
    "documentation": ["docs/readme files"]
  }},
  "existing_functionality": [
    "List each major feature/capability implemented",
    "Be specific about what each module/file does"
  ],
  "gaps_and_opportunities": [
    "What's missing or incomplete?",
    "What could be improved?",
    "What technical debt exists?"
  ],
  "recommendations": {{
    "how_to_extend": "How should new features be added to this codebase?",
    "patterns_to_follow": "What patterns/conventions does this code use?",
    "integration_points": "Where can new code integrate with existing code?",
    "cautions": "What should be avoided when modifying this code?"
  }},
  "key_insights": [
    "Important observations about code quality, architecture decisions, etc."
  ]
}}

IMPORTANT:
- Be thorough and specific
- Reference actual file names and code patterns you see
- Identify the primary purpose of this codebase
- Note any architectural decisions (monorepo, microservices, etc.)
- Return ONLY valid JSON, no markdown formatting
"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for Gemini response...", total=None)

        try:
            # Use Gemini 2.0 Flash (latest model with large context)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')

            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Low temperature for consistent analysis
                    "max_output_tokens": 8192,
                }
            )

            progress.update(task, description="✓ Analysis complete")

        except Exception as e:
            console.print(f"[bold red]✗ Gemini API error: {e}[/bold red]")
            raise

    # Extract and parse JSON from response
    response_text = response.text

    try:
        # Try to extract JSON if it's wrapped in markdown
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        analysis = json.loads(response_text)
        return analysis

    except json.JSONDecodeError as e:
        console.print(f"[bold red]✗ Failed to parse Gemini response as JSON[/bold red]")
        console.print(f"[yellow]Response text:[/yellow]")
        console.print(response_text[:1000])
        raise RuntimeError(f"Invalid JSON from Gemini: {e}")


def display_insights(insight: dict[str, Any]) -> None:
    """Display insights in a nice CLI format."""
    console.print("\n")
    console.print(Panel.fit(
        f"[bold green]{insight.get('project_type', 'Unknown Project')}[/bold green]",
        title="📊 Project Type",
        border_style="green"
    ))

    # Architecture Summary
    console.print("\n[bold cyan]🏗️  Architecture Summary[/bold cyan]")
    console.print(f"  {insight.get('architecture_summary', 'No summary available')}\n")

    # Tech Stack
    tech_stack = insight.get('tech_stack', {})
    if tech_stack:
        table = Table(title="💻 Tech Stack", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Technology", style="green")

        for key, value in tech_stack.items():
            if isinstance(value, list):
                value = ", ".join(value)
            if value:
                table.add_row(key.replace("_", " ").title(), str(value))

        console.print(table)

    # Existing Apps
    existing_apps = insight.get('existing_apps', [])
    if existing_apps:
        console.print("\n[bold cyan]📦 Existing Apps/Modules[/bold cyan]")
        for app in existing_apps:
            console.print(f"  • {app}")

    # Existing Functionality
    functionality = insight.get('existing_functionality', [])
    if functionality:
        console.print("\n[bold cyan]✨ Existing Functionality[/bold cyan]")
        for func in functionality[:10]:  # Show first 10
            console.print(f"  • {func}")
        if len(functionality) > 10:
            console.print(f"  ... and {len(functionality) - 10} more")

    # Gaps and Opportunities
    gaps = insight.get('gaps_and_opportunities', [])
    if gaps:
        console.print("\n[bold yellow]⚠️  Gaps & Opportunities[/bold yellow]")
        for gap in gaps[:5]:  # Show first 5
            console.print(f"  • {gap}")
        if len(gaps) > 5:
            console.print(f"  ... and {len(gaps) - 5} more")

    # Recommendations
    recommendations = insight.get('recommendations', {})
    if recommendations:
        console.print("\n[bold green]💡 Recommendations[/bold green]")
        for key, value in recommendations.items():
            console.print(f"\n  [cyan]{key.replace('_', ' ').title()}:[/cyan]")
            console.print(f"    {value}")


def build_context(target_dir: Path) -> CodebaseInsight | None:
    """
    Main entry point: Build context by analyzing existing codebase.

    Returns:
        CodebaseInsight if code exists, None otherwise
    """
    target_path = Path(target_dir)

    # Check if there's any existing code (beyond just config files)
    source_files = []
    for pattern in ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.java", "*.go", "*.rs"]:
        source_files.extend(target_path.glob(pattern))
        source_files.extend(target_path.glob(f"**/{pattern}"))
        if len(source_files) > 0:
            break

    # Filter out ignored files
    source_files = [f for f in source_files if not _should_ignore(f, target_path)]

    if not source_files:
        console.print("[yellow]ℹ️  No existing code detected. Skipping context analysis.[/yellow]")
        return None

    console.print(Panel.fit(
        "[bold cyan]Building Context from Existing Codebase[/bold cyan]",
        title="🔍 Context Builder",
        border_style="cyan"
    ))

    # Step 1: Collect all files
    files = collect_codebase_files(target_path)

    if not files:
        console.print("[yellow]⚠️  No files collected. Skipping analysis.[/yellow]")
        return None

    # Step 2: Analyze with Gemini
    try:
        analysis = analyze_with_gemini(files, target_path)
    except Exception as e:
        console.print(f"[bold red]✗ Context analysis failed: {e}[/bold red]")
        return None

    # Step 3: Display insights
    display_insights(analysis)

    # Step 4: Save to file
    insight_path = target_path / "codebase_insight.json"
    with insight_path.open("w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold green]✓ Insights saved to {insight_path}[/bold green]")

    # Create CodebaseInsight object
    return CodebaseInsight(
        project_type=analysis.get('project_type', 'Unknown'),
        existing_apps=analysis.get('existing_apps', []),
        tech_stack=analysis.get('tech_stack', {}),
        architecture_summary=analysis.get('architecture_summary', ''),
        file_structure=analysis.get('file_structure', {}),
        existing_functionality=analysis.get('existing_functionality', []),
        gaps_and_opportunities=analysis.get('gaps_and_opportunities', []),
        recommendations=analysis.get('recommendations', {}),
        raw_analysis=json.dumps(analysis, indent=2)
    )
