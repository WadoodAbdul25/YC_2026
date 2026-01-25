from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .llm import LLMError, generate_json


@dataclass(frozen=True)
class PlanArtifacts:
    architecture_path: Path
    major_tasks_path: Path


ARCHITECTURE_SYSTEM = (
    "You are a senior software architect. Return a JSON object only. "
    "Use keys: app_name, overview, components, data_flow, tech_stack, risks, assumptions."
)

TASKS_SYSTEM = (
    "You are a technical program manager. Return a JSON object only. "
    "Use keys: major_tasks (array of objects with title, description, owners, dependencies, acceptance_criteria)."
)


def _fallback_architecture(prompt: str) -> dict[str, Any]:
    return {
        "app_name": "New Gryffin App",
        "overview": prompt,
        "components": [
            {
                "name": "frontend",
                "responsibility": "User interface for the MVP.",
            },
            {
                "name": "backend",
                "responsibility": "API and business logic.",
            },
            {
                "name": "data",
                "responsibility": "Persistence and storage.",
            },
        ],
        "data_flow": "User input -> API -> storage -> response.",
        "tech_stack": {
            "frontend": "TBD",
            "backend": "TBD",
            "data": "TBD",
        },
        "risks": ["Requirements unclear", "Scope creep"],
        "assumptions": ["Single-tenant MVP", "Small team"],
    }


def _fallback_tasks(prompt: str) -> dict[str, Any]:
    return {
        "major_tasks": [
            {
                "title": "Define MVP scope",
                "description": f"Clarify success criteria and scope for: {prompt}",
                "owners": ["product"],
                "dependencies": [],
                "acceptance_criteria": ["One-page scope doc approved"],
            },
            {
                "title": "Design architecture",
                "description": "Pick stack, define services, and data model.",
                "owners": ["engineering"],
                "dependencies": ["Define MVP scope"],
                "acceptance_criteria": ["Architecture approved"],
            },
            {
                "title": "Build MVP",
                "description": "Implement core user flow end-to-end.",
                "owners": ["engineering"],
                "dependencies": ["Design architecture"],
                "acceptance_criteria": ["MVP runs locally"],
            },
        ]
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=True)
        handle.write("\n")


def generate_architecture(prompt: str, codebase_insight: dict[str, Any] | None = None) -> dict[str, Any]:
    # Augment prompt with codebase insight if available
    augmented_prompt = prompt
    if codebase_insight:
        insight_context = f"""
# EXISTING CODEBASE CONTEXT

This project already has existing code. You MUST build upon it, not replace it.

Project Type: {codebase_insight.get('project_type', 'Unknown')}
Architecture: {codebase_insight.get('architecture_summary', 'N/A')}

Existing Apps/Modules: {', '.join(codebase_insight.get('existing_apps', []))}

Tech Stack:
{json.dumps(codebase_insight.get('tech_stack', {}), indent=2)}

Existing Functionality:
{chr(10).join(f'- {func}' for func in codebase_insight.get('existing_functionality', [])[:10])}

# USER REQUEST
{prompt}

# YOUR TASK
Generate architecture that EXTENDS the existing codebase. Use the same tech stack, follow existing patterns, and integrate with existing functionality. Do NOT suggest replacing or removing existing code.
"""
        augmented_prompt = insight_context

    result = generate_json(ARCHITECTURE_SYSTEM, augmented_prompt)
    if result is None:
        return _fallback_architecture(prompt)
    if not isinstance(result, dict):
        raise LLMError("Architecture response was not a JSON object")
    return result


def generate_major_tasks(prompt: str, codebase_insight: dict[str, Any] | None = None) -> dict[str, Any]:
    # Augment prompt with codebase insight if available
    augmented_prompt = prompt
    if codebase_insight:
        insight_context = f"""
# EXISTING CODEBASE CONTEXT

Existing Functionality:
{chr(10).join(f'- {func}' for func in codebase_insight.get('existing_functionality', [])[:10])}

Recommendations for extending:
- How to extend: {codebase_insight.get('recommendations', {}).get('how_to_extend', 'N/A')}
- Patterns to follow: {codebase_insight.get('recommendations', {}).get('patterns_to_follow', 'N/A')}
- Integration points: {codebase_insight.get('recommendations', {}).get('integration_points', 'N/A')}

# USER REQUEST
{prompt}

# YOUR TASK
Generate tasks that EXTEND the existing codebase. Reference existing files and components. Build upon what's already there.
"""
        augmented_prompt = insight_context

    result = generate_json(TASKS_SYSTEM, augmented_prompt)
    if result is None:
        return _fallback_tasks(prompt)
    if not isinstance(result, dict):
        raise LLMError("Major tasks response was not a JSON object")
    return result


def _review_and_approve(architecture: dict[str, Any], tasks: dict[str, Any], current_prompt: str) -> tuple[bool, str]:
    """Review the generated artifacts and get user approval or feedback."""
    print("\n" + "=" * 60)
    print("📋 ARCHITECTURE REVIEW")
    print("=" * 60)
    print(f"\nApp Name: {architecture.get('app_name', 'N/A')}")
    print(f"\nOverview: {architecture.get('overview', 'N/A')}")

    print("\nComponents:")
    components = architecture.get('components', {})
    if isinstance(components, dict):
        for name, description in components.items():
            print(f"  • {name}: {description}")
    elif isinstance(components, list):
        for comp in components:
            if isinstance(comp, dict):
                print(f"  • {comp.get('name', 'N/A')}: {comp.get('responsibility', 'N/A')}")
            else:
                print(f"  • {comp}")

    tech_stack = architecture.get('tech_stack', {})
    if isinstance(tech_stack, list):
        print("\nTech Stack:")
        for tech in tech_stack:
            print(f"  • {tech}")
    else:
        print(f"\nTech Stack: {json.dumps(tech_stack, indent=2)}")

    risks = architecture.get('risks', [])
    if risks:
        print("\nRisks:")
        for risk in risks:
            print(f"  ⚠️  {risk}")

    assumptions = architecture.get('assumptions', [])
    if assumptions:
        print("\nAssumptions:")
        for assumption in assumptions:
            print(f"  💡 {assumption}")

    print("\n" + "=" * 60)
    print("📝 MAJOR TASKS")
    print("=" * 60)
    for i, task in enumerate(tasks.get('major_tasks', []), 1):
        print(f"\n{i}. {task.get('title', 'N/A')}")
        description = task.get('description', 'N/A')
        # Format multi-line descriptions with proper indentation
        if description and len(description) > 80:
            import textwrap
            wrapped = textwrap.fill(description, width=70, initial_indent='   ', subsequent_indent='   ')
            print(f"\n{wrapped}")
        else:
            print(f"   {description}")
        dependencies = task.get('dependencies', [])
        if dependencies:
            print(f"   Dependencies: {', '.join(dependencies)}")
        acceptance = task.get('acceptance_criteria', [])
        if acceptance:
            print(f"   Acceptance Criteria:")
            for criterion in acceptance:
                print(f"     ✓ {criterion}")

    print("\n" + "=" * 60)
    print("\nOptions:")
    print("  1. Approve and start execution")
    print("  2. Request changes (provide feedback)")
    print("  3. Cancel")

    while True:
        choice = input("\nYour choice (1/2/3): ").strip()

        if choice == "1":
            return True, current_prompt
        elif choice == "2":
            feedback = input("\nWhat changes would you like? (describe your feedback): ").strip()
            if feedback:
                new_prompt = f"{current_prompt}\n\nUser feedback: {feedback}"
                print("\n🔄 Regenerating with your feedback...\n")
                return False, new_prompt
            else:
                print("No feedback provided. Please try again.")
        elif choice == "3":
            print("\n❌ Cancelled by user.")
            raise SystemExit(0)
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


def run_planner(
    prompt: str,
    target_dir: str | Path,
    interactive: bool = False,
    start_execution: bool = False,
    codebase_insight: dict[str, Any] | None = None,
) -> PlanArtifacts:
    target_path = Path(target_dir)

    current_prompt = prompt
    approved = False

    while not approved:
        architecture = generate_architecture(current_prompt, codebase_insight)
        tasks = generate_major_tasks(current_prompt, codebase_insight)

        architecture_path = target_path / "architecture.json"
        major_tasks_path = target_path / "majortasks.json"

        _write_json(architecture_path, architecture)
        _write_json(major_tasks_path, tasks)

        if not interactive:
            approved = True
        else:
            approved, current_prompt = _review_and_approve(architecture, tasks, current_prompt)

    # Start execution if approved and requested
    if approved and start_execution:
        from .executor import start_execution as execute
        execute(architecture_path, major_tasks_path, target_path, codebase_insight)

    return PlanArtifacts(
        architecture_path=architecture_path,
        major_tasks_path=major_tasks_path,
    )


def _extract_prompt_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.startswith("[") and "]" in stripped:
        _, _, remainder = stripped.partition("]")
        return remainder.strip()
    return stripped


def _latest_prompt(prompt_path: Path) -> str:
    if not prompt_path.exists():
        return ""

    with prompt_path.open("r", encoding="utf-8") as handle:
        lines = [line for line in (l.rstrip("\n") for l in handle) if line.strip()]

    if not lines:
        return ""

    return _extract_prompt_line(lines[-1])


def watch_prompt_file(prompt_path: str | Path, target_dir: str | Path) -> None:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    prompt_path = Path(prompt_path)
    target_dir = Path(target_dir)
    watch_dir = prompt_path.parent

    last_prompt = ""

    class _PromptHandler(FileSystemEventHandler):
        def on_modified(self, event) -> None:  # type: ignore[override]
            nonlocal last_prompt
            if Path(event.src_path) != prompt_path:
                return
            prompt = _latest_prompt(prompt_path)
            if not prompt or prompt == last_prompt:
                return
            last_prompt = prompt
            print(f"\n✓ Detected change in prompt.txt")
            print(f"  Prompt: {prompt}")
            print(f"  Running planner...\n")
            run_planner(prompt, target_dir)
            print(f"✓ Architecture updated: {target_dir / 'architecture.json'}")
            print(f"✓ Tasks updated: {target_dir / 'majortasks.json'}\n")

        def on_created(self, event) -> None:  # type: ignore[override]
            self.on_modified(event)

    handler = _PromptHandler()
    observer = Observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()

    try:
        observer.join()
    finally:
        observer.stop()
        observer.join()
