from __future__ import annotations

from pathlib import Path

from render import render, render_head_to_head

ROOT = Path(__file__).parents[1]


def test_portfolio_exactly_six_and_open_studio_unscored():
    import json

    products = json.loads((ROOT / "docs/sota/evidence/portfolio/products.json").read_text())[
        "products"
    ]
    context = json.loads(
        (ROOT / "docs/sota/evidence/portfolio/open-studio-context.json").read_text()
    )
    assert len(products) == 6 and all(x["scored"] for x in products)
    assert context["scored"] is False and context["verdict"] is None


def test_render_is_deterministic_and_checked_in():
    first = render(ROOT)
    second = render(ROOT)
    assert first == second == (ROOT / "docs/sota/README.md").read_text()


def test_head_to_head_top_three_to_five_all_criteria_unknowns():
    candidates = [
        {
            "product_id": x,
            "top_dimension_count": n,
            "weighted_criterion_coverage": n,
            "workflow_relevance": 1,
            "evidence_freshness": 1,
        }
        for x, n in [("a", 5), ("b", 4), ("c", 3), ("d", 2), ("e", 1), ("f", 0)]
    ]
    text = render_head_to_head(
        ["quality", "security"],
        candidates,
        {
            "quality": {"product": "90", "a": "tie", "b": "unknown"},
            "security": {"product": "pass", "a": "lead"},
        },
    )
    assert (
        "| Criterion | Product | a | b | c | d | e |" in text
        and text.count("unknown") >= 6
        and "f" not in text
    )
