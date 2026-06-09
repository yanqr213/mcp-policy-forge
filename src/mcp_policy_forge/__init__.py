"""Least-privilege policy generator and validator for MCP tools."""

from .engine import analyze
from .models import AnalysisReport, Finding, Policy, PolicyRule, ToolSpec

__all__ = [
    "AnalysisReport",
    "Finding",
    "Policy",
    "PolicyRule",
    "ToolSpec",
    "analyze",
]

__version__ = "0.2.0"
