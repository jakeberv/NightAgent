"""Offline report entrypoints; loading, aggregation, and rendering stay separate."""
from pathlib import Path

from .report_data import build_report_data
from .report_rendering import render_report

__all__ = ["build_report_data", "generate_report"]


def generate_report(root: Path) -> Path:
    """Write portable report artifacts from frozen evidence without API calls."""
    return render_report(build_report_data(root), Path(root))
