from __future__ import annotations

from pathlib import Path

import typer

from pipeline import run_planner, watch_prompt_file, build_context, is_action_prompt, run_action_prompt
from prompt_taker import take_prompt

app = typer.Typer(help="Gryffin CLI", invoke_without_command=True)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv, find_dotenv
    except Exception:
        return

    # Search for .env in current dir and parent dirs
    env_file = find_dotenv(usecwd=True)
    if env_file:
        load_dotenv(env_file, override=False)
        # Also try the parent project's .env (common monorepo layout)
        try:
            from pathlib import Path

            parent_env = Path(env_file).resolve().parent.parent / ".env"
            if parent_env.exists() and str(parent_env) != str(env_file):
                load_dotenv(parent_env, override=False)
        except Exception:
            pass
    else:
        load_dotenv(override=False)  # Fallback to default behavior


def _has_existing_codebase(target_dir: Path) -> bool:
    """Check if the target directory has an existing codebase."""
    source_patterns = ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.java", "*.go", "*.rs"]
    ignore_dirs = {".git", "__pycache__", "node_modules", "venv", "env", ".venv", "dist", "build"}

    for pattern in source_patterns:
        for file in target_dir.glob(f"**/{pattern}"):
            # Skip files in ignored directories
            if not any(ignored in file.parts for ignored in ignore_dirs):
                return True
    return False


@app.command("start")
def start(path: str = typer.Argument(".", help="Target directory")) -> None:
    """Capture a prompt and generate planner artifacts."""
    import json

    target_dir = Path(path).expanduser().resolve()

    # Check for existing codebase FIRST
    has_existing_code = _has_existing_codebase(target_dir)

    if has_existing_code:
        typer.echo("\n🔍 Detected existing codebase!")
        typer.echo("━" * 50)

        # Build context from existing codebase
        codebase_insight = build_context(target_dir)

        if codebase_insight:
            typer.echo("\n" + "━" * 50)
            typer.echo("\n📋 Now that I understand your codebase, let's talk about what we're building.")
            typer.echo("   I'll ensure any new features integrate with your existing code.\n")

            # Ask specifically what to build on top of existing code
            prompt_entry = take_prompt(
                target_dir,
                question="What would you like to build/add to this codebase?: "
            )

            # Convert CodebaseInsight to dict for planner
            insight_dict = json.loads(codebase_insight.raw_analysis)
        else:
            # Context building failed but there is code - proceed without insights
            typer.echo("⚠️  Could not analyze existing codebase. Proceeding without context.\n")
            prompt_entry = take_prompt(target_dir)
            insight_dict = None
    else:
        # No existing codebase - fresh project
        typer.echo("\n🆕 Starting a fresh project (no existing codebase detected)\n")
        prompt_entry = take_prompt(target_dir)
        codebase_insight = None
        insight_dict = None

    if is_action_prompt(prompt_entry.prompt):
        typer.echo("\n⚡ Action request detected — running commands now...\n")
        run_action_prompt(prompt_entry.prompt, target_dir)
        return

    typer.echo("\n🔨 Generating architecture and tasks...\n")
    run_planner(
        prompt_entry.prompt,
        target_dir,
        interactive=True,
        start_execution=True,
        codebase_insight=insight_dict,
    )

    typer.echo(f"\n✅ Session complete!")
    typer.echo(f"Prompt saved to: {prompt_entry.prompt_path}")
    if codebase_insight:
        typer.echo(f"Codebase insights saved to: {target_dir / 'codebase_insight.json'}")
    typer.echo(f"Architecture saved to: {target_dir / 'architecture.json'}")
    typer.echo(f"Major tasks saved to: {target_dir / 'majortasks.json'}")


@app.command("watch")
def watch(path: str = typer.Argument(".", help="Directory containing prompt.txt")) -> None:
    """Watch prompt.txt and run the planner on changes."""
    target_dir = Path(path).expanduser().resolve()
    prompt_path = target_dir / "prompt.txt"
    typer.echo(f"Watching {prompt_path} for changes...")
    watch_prompt_file(prompt_path, target_dir)


def _print_version() -> None:
    """Print the Gryffin CLI version and exit."""
    try:
        from importlib.metadata import version as pkg_version

        typer.echo(pkg_version("gryffin"))
    except Exception:
        typer.echo("0.1.0")
    raise typer.Exit()


@app.callback(invoke_without_command=True)
def main_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show the Gryffin CLI version and exit.",
        is_eager=True,
    )
) -> None:
    if version:
        _print_version()


def main() -> None:
    _load_env()
    app()


if __name__ == "__main__":
    main()
