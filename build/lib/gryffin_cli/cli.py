from __future__ import annotations

from pathlib import Path

import typer

from pipeline import run_planner, watch_prompt_file, build_context
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
        load_dotenv(env_file)
    else:
        load_dotenv()  # Fallback to default behavior


@app.command("start")
def start(path: str = typer.Argument(".", help="Target directory")) -> None:
    """Capture a prompt and generate planner artifacts."""
    target_dir = Path(path).expanduser().resolve()
    prompt_entry = take_prompt(target_dir)

    # Build context from existing codebase (if any)
    codebase_insight = build_context(target_dir)

    # Convert CodebaseInsight to dict for planner
    insight_dict = None
    if codebase_insight:
        import json
        insight_dict = json.loads(codebase_insight.raw_analysis)

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
