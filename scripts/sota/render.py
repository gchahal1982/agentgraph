"""Deterministically render the portfolio skeleton or populated portfolio index."""

from __future__ import annotations

import argparse
from pathlib import Path

from _common import read_json
from score import select_head_to_head

GAP_COLUMNS = ("Dimension", "Current State", "SOTA Target", "Gap", "Effort", "Priority")


def render_gap_table(gaps: list[dict[str, object]]) -> str:
    lines = [
        "| " + " | ".join(GAP_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in GAP_COLUMNS) + " |",
    ]
    for gap in sorted(gaps, key=lambda item: (str(item["dimension"]), str(item["gap_id"]))):
        lines.append(
            "| "
            + " | ".join(
                str(gap[key])
                for key in (
                    "dimension",
                    "current_state",
                    "sota_target",
                    "gap",
                    "effort",
                    "priority",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def render_head_to_head(
    criteria: list[str], candidates: list[dict[str, object]], cells: dict[str, dict[str, str]]
) -> str:
    selected = select_head_to_head(candidates)
    lines = [
        "| Criterion | Product | " + " | ".join(selected) + " |",
        "| --- | --- | " + " | ".join("---" for _ in selected) + " |",
    ]
    for criterion in criteria:
        row = cells.get(criterion, {})
        lines.append(
            "| "
            + criterion
            + " | "
            + row.get("product", "unknown")
            + " | "
            + " | ".join(row.get(item, "unknown") for item in selected)
            + " |"
        )
    return "\n".join(lines)


def render(root: Path) -> str:
    base = root / "docs/sota/evidence/portfolio"
    products = read_json(base / "products.json")["products"]
    config = read_json(base / "index-config.json")
    context = read_json(base / "open-studio-context.json")
    lines = [
        f"# {config['title']}",
        "",
        "This index is generated from structured evidence. Product dossiers are added by the independent Task 3 lanes; absence here is not a capability conclusion.",
        "",
        "## Methodology",
        "",
        config["methodology"],
        "",
        "Verdicts use exactly **SOTA** or **Not Yet SOTA**. **Inconclusive evidence** is reported separately and is never a third verdict.",
        "",
        "## Scored products",
        "",
        "| Product | Category | Repository | Dossier | Evidence state |",
        "| --- | --- | --- | --- | --- |",
    ]
    for product in sorted(products, key=lambda item: item["order"]):
        dossier = root / product["dossier_path"]
        state = "Task 3 evidence pending" if not dossier.exists() else "Dossier available"
        lines.append(
            f"| {product['name']} | {product['category']} | `{product['repository']}` | [{product['dossier_path']}]({product['dossier_path'].removeprefix('docs/sota/')}) | {state} |"
        )
    lines += [
        "",
        "## Gap roadmap",
        "",
        "Each product dossier renders its authoritative `gaps.json` with these minimum columns:",
        "",
        "| Dimension | Current State | SOTA Target | Gap | Effort | Priority |",
        "| --- | --- | --- | --- | --- | --- |",
        "| Task 3 product evidence pending | — | — | — | — | — |",
        "",
        "## Context only",
        "",
        f"**{context['name']}** is unscored and has no verdict. {context['role']}",
        "",
        "Competitive context is excluded from technical scoring unless a specific operational criterion and justification were frozen before measurement.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    target = root / "docs/sota/README.md"
    rendered = render(root)
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != rendered:
            print(f"generated output differs: {target}")
            return 1
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
