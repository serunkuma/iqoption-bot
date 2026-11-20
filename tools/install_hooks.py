"""Install the repository git hooks.

The hooks live in ``.githooks/`` so they are versioned with the code. Installing
them only points ``core.hooksPath`` at that directory; nothing is copied into
``.git/hooks``.

    python tools/install_hooks.py
    python tools/install_hooks.py --status

The hook itself is POSIX ``sh`` because Git for Windows runs hooks through its
bundled shell.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HOOKS_DIR = ".githooks"
HOOK_NAMES = ("pre-commit",)


class HookError(RuntimeError):
    """Raised when the hooks cannot be installed."""


def _git(repo: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # git is not installed
        raise HookError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise HookError(f"git {' '.join(arguments)} failed: {detail}") from exc
    return completed.stdout.strip()


def configured_hooks_path(repo: Path | str = ".") -> str | None:
    """Return the repository-local ``core.hooksPath`` value, or ``None``."""

    repo = Path(repo).resolve()
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), "config", "--local", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HookError("git executable not found on PATH") from exc
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def install_hooks(repo: Path | str = ".") -> list[str]:
    """Point ``core.hooksPath`` at the versioned hooks and mark them executable.

    Returns human-readable status lines. Raises :class:`HookError` when the
    directory, a hook file, or git itself is missing.
    """

    repo = Path(repo).resolve()
    hooks_dir = repo / HOOKS_DIR
    if not hooks_dir.is_dir():
        raise HookError(f"hooks directory not found: {hooks_dir}")

    for name in HOOK_NAMES:
        hook = hooks_dir / name
        if not hook.is_file():
            raise HookError(f"hook file not found: {hook}")
        try:
            hook.chmod(hook.stat().st_mode | 0o111)
        except OSError:
            # Windows filesystems may ignore the executable bit; Git for Windows
            # runs the hook through sh regardless.
            pass

    _git(repo, "config", "--local", "core.hooksPath", HOOKS_DIR)
    return [f"core.hooksPath = {HOOKS_DIR}", f"hooks installed: {', '.join(HOOK_NAMES)}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install_hooks.py",
        description="Install the versioned git hooks in .githooks/.",
    )
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument(
        "--status",
        action="store_true",
        help="print the current core.hooksPath instead of installing",
    )
    args = parser.parse_args(argv)

    try:
        if args.status:
            current = configured_hooks_path(args.repo)
            if current is None:
                print("core.hooksPath: unset (hooks are not installed)")
                return 1
            print(f"core.hooksPath: {current}")
            return 0

        for line in install_hooks(args.repo):
            print(line)
        print("Bypass a single commit with: git commit --no-verify")
        return 0
    except HookError as exc:
        print(f"hook install error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
