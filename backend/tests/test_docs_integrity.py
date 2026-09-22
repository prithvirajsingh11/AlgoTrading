"""
Test suite validating documentation and asset integrity for v1.0.0 release.
"""

from pathlib import Path


def test_docs_and_assets_exist():
    """Verify all required documentation and SVG assets exist."""
    root_dir = Path(__file__).resolve().parent.parent.parent

    # Core doc files
    core_docs = [
        "docs/architecture.svg",
        "docs/benchmarks.md",
        "docs/limitations.md",
        "docs/project-summary.md",
        "docs/release-checklist.md",
        "docs/technical-design.md",
        "configs/demo.json",
        "README.md",
    ]
    for doc in core_docs:
        path = root_dir / doc
        assert path.exists(), f"Missing required document: {doc}"

    # Visual mockups
    mockups = [
        "docs/assets/dashboard.svg",
        "docs/assets/backtest_lab.svg",
        "docs/assets/strategy_comparison.svg",
        "docs/assets/ml_lab.svg",
        "docs/assets/jev_lab.svg",
        "docs/assets/paper_trading.svg",
        "docs/assets/realtime_provider.svg",
        "docs/assets/experiment_details.svg",
    ]
    for mockup in mockups:
        path = root_dir / mockup
        assert path.exists(), f"Missing required visual mockup: {mockup}"
        assert path.stat().st_size > 500, f"Mockup {mockup} appears empty or truncated"


def test_benchmarks_doc_disclaimer():
    """Verify docs/benchmarks.md explicitly contains the simulation throughput disclaimer."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    benchmarks_path = root_dir / "docs" / "benchmarks.md"

    content = benchmarks_path.read_text(encoding="utf-8")
    assert "local synthetic software-performance benchmark" in content.lower()
    assert "measured on deterministic gbm datasets in the development environment" in content.lower()
    assert "zero claims of trading profitability" in content.lower()
    assert "purely computer science achievements" in content.lower()


def test_readme_contains_portfolio_sections():
    """Verify README.md contains key computer science and architecture sections."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    readme_path = root_dir / "README.md"

    content = readme_path.read_text(encoding="utf-8")
    required_phrases = [
        "One-Sentence Description",
        "Why I Built This",
        "Architecture",
        "Three Operating Modes",
        "Performance Benchmarks",
        "Security & Safety",
        "Computer Science Concepts Demonstrated",
        "Screenshot & Diagram Gallery",
        "SimulatedBroker",
    ]
    for phrase in required_phrases:
        assert phrase in content, f"README.md missing section or phrase: '{phrase}'"
