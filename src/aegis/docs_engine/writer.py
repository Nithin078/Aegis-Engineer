"""Write documentation files (proposed vs apply)."""

from __future__ import annotations

from pathlib import Path

from aegis.docs_engine.models import DocAction, DocActionKind, DocReport


def write_actions(
    workspace: Path,
    report: DocReport,
    actions: list[DocAction],
    *,
    apply: bool,
    proposed_dir: str = "docs/_proposed",
) -> DocReport:
    """Write action contents to real paths or docs/_proposed/."""
    root = workspace.resolve()
    written: list[str] = []
    proposed: list[str] = []

    for action in actions:
        if not action.content:
            continue
        if apply:
            dest = root / action.target_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            is_changelog_update = (
                action.topic == "changelog"
                and dest.is_file()
                and action.kind is DocActionKind.UPDATE
            )
            if is_changelog_update:
                existing = dest.read_text(encoding="utf-8")
                if action.content.strip() not in existing:
                    # prepend after title if present
                    if existing.lstrip().startswith("#"):
                        lines = existing.splitlines(keepends=True)
                        # insert after first line
                        new = lines[0] + "\n" + action.content + "\n" + "".join(lines[1:])
                        dest.write_text(new, encoding="utf-8")
                    else:
                        dest.write_text(action.content + "\n" + existing, encoding="utf-8")
                written.append(action.target_path)
            else:
                if action.topic == "changelog" and not dest.is_file():
                    header = "# Aegis documentation changelog\n\n"
                    dest.write_text(header + action.content, encoding="utf-8")
                else:
                    dest.write_text(action.content, encoding="utf-8")
                written.append(action.target_path)
        else:
            # proposed path mirrors target under docs/_proposed
            rel = action.target_path
            if rel.startswith("docs/"):
                prop = root / proposed_dir / rel[len("docs/") :]
            else:
                prop = root / proposed_dir / Path(rel).name
            prop.parent.mkdir(parents=True, exist_ok=True)
            prop.write_text(action.content, encoding="utf-8")
            proposed.append(str(prop.relative_to(root).as_posix()))

    report.written_files = written
    report.proposed_files = proposed
    report.applied = apply
    report.actions = actions
    return report
