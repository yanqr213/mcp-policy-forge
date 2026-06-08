from __future__ import annotations

from typing import Dict, List

from .models import (
    ACTION_EXECUTE,
    ACTION_NETWORK,
    ACTION_SECRET,
    ACTION_WRITE,
    PermissionNeed,
    RiskResult,
    ToolSpec,
    uniq,
)

ACTION_WEIGHTS = {
    ACTION_EXECUTE: 45,
    ACTION_WRITE: 25,
    ACTION_NETWORK: 20,
    ACTION_SECRET: 35,
}


def score_risks(tools: List[ToolSpec], needs: List[PermissionNeed]) -> List[RiskResult]:
    by_tool: Dict[str, PermissionNeed] = {need.tool: need for need in needs}
    results = []
    for tool in tools:
        need = by_tool.get(tool.name, PermissionNeed(tool=tool.name, actions=tool.inferred_actions))
        score = 0
        reasons = []
        for action in need.actions:
            weight = ACTION_WEIGHTS.get(action, 5)
            score += weight
            if weight >= 20:
                reasons.append("包含高影响 action: %s" % action)
        if need.paths:
            score += min(20, 5 * len(need.paths))
            reasons.append("涉及路径范围: %s" % ", ".join(need.paths[:3]))
        if need.networks:
            score += min(20, 5 * len(need.networks))
            reasons.append("涉及网络目标: %s" % ", ".join(need.networks[:3]))
        if "*" in need.paths or any(path in ("/", "C:/", "C:\\") for path in need.paths):
            score += 30
            reasons.append("路径范围过宽")
        score = min(score, 100)
        results.append(RiskResult(tool=tool.name, score=score, level=risk_level(score), reasons=uniq(reasons)))
    return sorted(results, key=lambda item: (-item.score, item.tool))


def risk_level(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"

