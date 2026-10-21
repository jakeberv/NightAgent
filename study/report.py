"""Offline report entrypoints; loading, aggregation, and rendering stay separate."""
from pathlib import Path

from .report_data import build_report_data
from .report_rendering import render_report

__all__ = ["build_report_data", "generate_report"]


def generate_report(root: Path, *, destination: Path | None = None) -> Path:
    """Write portable offline artifacts; a destination preserves the source report."""
    return render_report(build_report_data(root), Path(destination) if destination is not None else Path(root))
