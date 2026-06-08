from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


ACTION_READ = "read_file"
ACTION_WRITE = "write_file"
ACTION_NETWORK = "network"
ACTION_EXECUTE = "execute_command"
ACTION_SECRET = "secret_access"
ACTION_UNKNOWN = "unknown"

KNOWN_ACTIONS = {
    ACTION_READ,
    ACTION_WRITE,
    ACTION_NETWORK,
    ACTION_EXECUTE,
    ACTION_SECRET,
    ACTION_UNKNOWN,
}


def uniq(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


@dataclass
class ToolSpec:
    name: str
    description: str = ""
    schema: Dict[str, Any] = field(default_factory=dict)
    source: str = "manifest"
    inferred_actions: List[str] = field(default_factory=list)
    inferred_paths: List[str] = field(default_factory=list)
    inferred_networks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
            "source": self.source,
            "inferred_actions": uniq(self.inferred_actions),
            "inferred_paths": uniq(self.inferred_paths),
            "inferred_networks": uniq(self.inferred_networks),
        }


@dataclass
class PermissionNeed:
    tool: str
    actions: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    source: str = "analysis"

    def merge(self, other: "PermissionNeed") -> None:
        self.actions = uniq([*self.actions, *other.actions])
        self.paths = uniq([*self.paths, *other.paths])
        self.networks = uniq([*self.networks, *other.networks])
        self.reasons = uniq([*self.reasons, *other.reasons])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "actions": uniq(self.actions),
            "paths": uniq(self.paths),
            "networks": uniq(self.networks),
            "reasons": uniq(self.reasons),
            "source": self.source,
        }


@dataclass
class PolicyRule:
    effect: str
    tools: List[str] = field(default_factory=lambda: ["*"])
    actions: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)
    reason: str = ""
    source: str = "policy"

    def normalized(self) -> "PolicyRule":
        return PolicyRule(
            effect=(self.effect or "").lower(),
            tools=uniq(self.tools or ["*"]),
            actions=uniq(self.actions),
            paths=uniq(self.paths),
            networks=uniq(self.networks),
            reason=self.reason,
            source=self.source,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect": self.effect,
            "tools": uniq(self.tools or ["*"]),
            "actions": uniq(self.actions),
            "paths": uniq(self.paths),
            "networks": uniq(self.networks),
            "reason": self.reason,
            "source": self.source,
        }


@dataclass
class Policy:
    version: str = "2026-06"
    defaults: Dict[str, Any] = field(default_factory=lambda: {"effect": "deny"})
    rules: List[PolicyRule] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "defaults": self.defaults,
            "metadata": self.metadata,
            "rules": [rule.to_dict() for rule in self.rules],
        }


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    tool: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "tool": self.tool,
            "detail": self.detail,
        }


@dataclass
class RiskResult:
    tool: str
    score: int
    level: str
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "score": self.score,
            "level": self.level,
            "reasons": uniq(self.reasons),
        }


@dataclass
class AnalysisReport:
    policy: Policy
    needs: List[PermissionNeed]
    risks: List[RiskResult]
    findings: List[Finding]
    tools: List[ToolSpec] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy": self.policy.to_dict(),
            "needs": [need.to_dict() for need in self.needs],
            "risks": [risk.to_dict() for risk in self.risks],
            "findings": [finding.to_dict() for finding in self.findings],
            "tools": [tool.to_dict() for tool in self.tools],
        }

