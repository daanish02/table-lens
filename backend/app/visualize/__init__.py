"""The visualize agent — turns a finished query agent result into an
ECharts spec. Deliberately separate from the query agent: the query
agent finds schema and runs SQL, this agent only decides how to present
an already-finished result, so it never needs tools of its own."""

from app.visualize.agent import generate_chart
from app.visualize.chart_guard import ChartValidationError, validate_chart_spec

__all__ = ["generate_chart", "ChartValidationError", "validate_chart_spec"]
