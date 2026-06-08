from __future__ import annotations

import html
from typing import List

from .models import AnalysisReport, Finding, RiskResult


def report_to_markdown(report: AnalysisReport) -> str:
    lines: List[str] = [
        "# MCP Policy Forge Report",
        "",
        "## 摘要",
        "",
        "- 工具数量: %s" % len(report.tools),
        "- 权限需求: %s" % len(report.needs),
        "- 风险项: %s" % len(report.risks),
        "- 发现问题: %s" % len(report.findings),
        "",
        "## 高风险工具",
        "",
    ]
    high = [risk for risk in report.risks if risk.level in ("high", "critical")]
    if not high:
        lines.append("- 无")
    for risk in high:
        lines.append("- `%s`: %s/%s，%s" % (risk.tool, risk.score, risk.level, "; ".join(risk.reasons) or "无额外说明"))
    lines.extend(["", "## 权限需求", ""])
    for need in report.needs:
        lines.append("- `%s`: actions=%s paths=%s networks=%s" % (need.tool, need.actions or [], need.paths or [], need.networks or []))
    lines.extend(["", "## 发现问题", ""])
    if not report.findings:
        lines.append("- 无")
    for finding in report.findings:
        lines.append("- [%s] `%s` %s" % (finding.severity, finding.code, finding.message))
    lines.extend(["", "## 生成策略", "", "```json"])
    import json

    lines.append(json.dumps(report.policy.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    return "\n".join(lines) + "\n"


def report_to_junit(report: AnalysisReport, suite_name: str = "mcp-policy-forge") -> str:
    failures = [finding for finding in report.findings if finding.severity == "error"]
    tests = max(1, len(report.findings) + len(report.risks))
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<testsuite name="%s" tests="%s" failures="%s">' % (html.escape(suite_name), tests, len(failures)),
    ]
    if not report.findings and not report.risks:
        lines.append('  <testcase classname="mcp_policy_forge" name="no_findings" />')
    for risk in report.risks:
        lines.extend(risk_case(risk))
    for finding in report.findings:
        lines.extend(finding_case(finding))
    lines.append("</testsuite>")
    return "\n".join(lines) + "\n"


def risk_case(risk: RiskResult) -> List[str]:
    name = "risk.%s.%s" % (risk.level, risk.tool)
    return ['  <testcase classname="mcp_policy_forge.risk" name="%s" />' % html.escape(name)]


def finding_case(finding: Finding) -> List[str]:
    name = "%s.%s.%s" % (finding.severity, finding.code, finding.tool or "global")
    if finding.severity == "error":
        return [
            '  <testcase classname="mcp_policy_forge.policy" name="%s">' % html.escape(name),
            '    <failure message="%s">%s</failure>' % (html.escape(finding.message), html.escape(str(finding.detail))),
            "  </testcase>",
        ]
    return ['  <testcase classname="mcp_policy_forge.policy" name="%s" />' % html.escape(name)]

