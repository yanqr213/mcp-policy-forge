from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .infer import normalize_action, normalize_network
from .io import InputError, load_json_file
from .models import (
    ACTION_NETWORK,
    ACTION_READ,
    ACTION_WRITE,
    Finding,
    PermissionNeed,
    Policy,
    PolicyRule,
    uniq,
)


def load_policy(path: Optional[str]) -> Policy:
    if not path:
        return Policy(metadata={"generated_by": "mcp-policy-forge"})
    return parse_policy(load_json_file(path))


def parse_policy(data: Any) -> Policy:
    if not isinstance(data, dict):
        raise InputError("policy 必须是 JSON object")
    rules = []
    for item in data.get("rules", []):
        if not isinstance(item, dict):
            raise InputError("policy.rules 只能包含 object")
        rules.append(
            PolicyRule(
                effect=str(item.get("effect", "")),
                tools=listify(item.get("tools", "*")),
                actions=[normalize_action(value) for value in listify(item.get("actions", []))],
                paths=listify(item.get("paths", [])),
                networks=[normalize_network(value) for value in listify(item.get("networks", []))],
                reason=str(item.get("reason", "")),
                source=str(item.get("source", "policy")),
            ).normalized()
        )
    return Policy(
        version=str(data.get("version", "2026-06")),
        defaults=data.get("defaults") if isinstance(data.get("defaults"), dict) else {"effect": "deny"},
        rules=rules,
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
    )


def listify(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def generated_policy_from_needs(needs: List[PermissionNeed], org_policy: Optional[Policy] = None) -> Policy:
    rules = list(org_policy.rules if org_policy else [])
    for need in needs:
        rules.append(
            PolicyRule(
                effect="allow",
                tools=[need.tool],
                actions=need.actions,
                paths=need.paths,
                networks=need.networks,
                reason="由 manifest/transcript 最小权限推断生成",
                source="generated",
            ).normalized()
        )
    return Policy(
        version=(org_policy.version if org_policy else "2026-06"),
        defaults=(org_policy.defaults if org_policy else {"effect": "deny"}),
        rules=merge_rules(rules),
        metadata={"generated_by": "mcp-policy-forge", **(org_policy.metadata if org_policy else {})},
    )


def merge_rules(rules: Iterable[PolicyRule]) -> List[PolicyRule]:
    merged: Dict[tuple, PolicyRule] = {}
    for rule in rules:
        normalized = rule.normalized()
        key = (normalized.effect, tuple(normalized.tools), normalized.reason, normalized.source)
        if key not in merged:
            merged[key] = normalized
        else:
            existing = merged[key]
            existing.actions = uniq([*existing.actions, *normalized.actions])
            existing.paths = uniq([*existing.paths, *normalized.paths])
            existing.networks = uniq([*existing.networks, *normalized.networks])
    return list(merged.values())


def validate_policy(policy: Policy) -> List[Finding]:
    findings = []
    for index, rule in enumerate(policy.rules):
        if rule.effect not in ("allow", "deny"):
            findings.append(Finding("error", "POLICY_EFFECT", "规则 %s 的 effect 必须是 allow 或 deny" % index, detail={"rule": index}))
        if not rule.tools:
            findings.append(Finding("error", "POLICY_TOOLS", "规则 %s 缺少 tools" % index, detail={"rule": index}))
        if not rule.actions and not rule.paths and not rule.networks:
            findings.append(Finding("warning", "POLICY_EMPTY_SCOPE", "规则 %s 没有限定 action/path/network" % index, detail={"rule": index}))
        for action in rule.actions:
            if not normalize_action(action):
                findings.append(Finding("error", "POLICY_ACTION", "规则 %s 包含空 action" % index, detail={"rule": index}))
    return findings


def evaluate_needs(policy: Policy, needs: List[PermissionNeed], repo_root: Optional[str] = None) -> List[Finding]:
    findings: List[Finding] = []
    for need in needs:
        for action in need.actions or []:
            decision = decide(policy, need.tool, action=action)
            if decision == "deny":
                findings.append(Finding("error", "ACTION_DENIED", "工具 %s 请求被拒绝的 action: %s" % (need.tool, action), tool=need.tool, detail={"action": action}))
        for path in need.paths or []:
            if repo_root and escapes_repo(path, repo_root):
                findings.append(Finding("error", "PATH_ESCAPE", "工具 %s 访问 repo 根目录之外路径: %s" % (need.tool, path), tool=need.tool, detail={"path": path, "repo_root": repo_root}))
            decision = decide(policy, need.tool, action=ACTION_WRITE if is_write_path(need, path) else ACTION_READ, path=path)
            if decision == "deny":
                findings.append(Finding("error", "PATH_DENIED", "工具 %s 路径不在允许范围: %s" % (need.tool, path), tool=need.tool, detail={"path": path}))
        for network in need.networks or []:
            decision = decide(policy, need.tool, action=ACTION_NETWORK, network=network)
            if decision == "deny":
                findings.append(Finding("error", "NETWORK_DENIED", "工具 %s 网络目标不在允许范围: %s" % (need.tool, network), tool=need.tool, detail={"network": network}))
    return findings


def decide(policy: Policy, tool: str, action: Optional[str] = None, path: Optional[str] = None, network: Optional[str] = None) -> str:
    default = str(policy.defaults.get("effect", "deny")).lower()
    matched_allow = False
    for rule in policy.rules:
        if not matches_rule(rule, tool, action=action, path=path, network=network):
            continue
        if rule.effect == "deny":
            return "deny"
        if rule.effect == "allow":
            matched_allow = True
    return "allow" if matched_allow else default


def matches_rule(rule: PolicyRule, tool: str, action: Optional[str] = None, path: Optional[str] = None, network: Optional[str] = None) -> bool:
    if not any(fnmatch.fnmatchcase(tool, pattern) for pattern in (rule.tools or ["*"])):
        return False
    if action and rule.actions and "*" not in rule.actions and normalize_action(action) not in rule.actions:
        return False
    if path and rule.paths and not any(fnmatch.fnmatch(normalize_path(path), normalize_path(pattern)) for pattern in rule.paths):
        return False
    if network and rule.networks and not any(fnmatch.fnmatch(normalize_network(network), normalize_network(pattern)) for pattern in rule.networks):
        return False
    return True


def normalize_path(path: str) -> str:
    return str(path).replace("\\", "/")


def escapes_repo(path: str, repo_root: str) -> bool:
    if not path:
        return False
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(repo_root) / candidate
    try:
        root = Path(repo_root).resolve()
        resolved = candidate.resolve()
        return os.path.commonpath([str(root), str(resolved)]) != str(root)
    except (OSError, ValueError):
        return True


def is_write_path(need: PermissionNeed, path: str) -> bool:
    return ACTION_WRITE in need.actions and ACTION_READ not in need.actions

