from __future__ import annotations

from typing import Any, Dict, List

from .policy import parse_policy


def diff_policies(old_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    old = parse_policy(old_data)
    new = parse_policy(new_data)
    old_rules = {rule_key(rule.to_dict()): rule.to_dict() for rule in old.rules}
    new_rules = {rule_key(rule.to_dict()): rule.to_dict() for rule in new.rules}
    added = [new_rules[key] for key in sorted(set(new_rules) - set(old_rules))]
    removed = [old_rules[key] for key in sorted(set(old_rules) - set(new_rules))]
    changed = []
    for key in sorted(set(old_rules) & set(new_rules)):
        if old_rules[key] != new_rules[key]:
            changed.append({"key": key, "old": old_rules[key], "new": new_rules[key]})
    return {"added": added, "removed": removed, "changed": changed}


def rule_key(rule: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(rule.get("effect", "")),
            ",".join(rule.get("tools", [])),
            ",".join(rule.get("actions", [])),
            str(rule.get("reason", "")),
        ]
    )


def diff_to_markdown(diff: Dict[str, Any]) -> str:
    lines: List[str] = ["# MCP Policy Diff", ""]
    for title, key in (("新增规则", "added"), ("删除规则", "removed"), ("变更规则", "changed")):
        lines.extend(["## %s" % title, ""])
        items = diff.get(key, [])
        if not items:
            lines.append("- 无")
        else:
            for item in items:
                if key == "changed":
                    lines.append("- `%s`" % item["key"])
                else:
                    lines.append("- `%s` `%s` actions=%s paths=%s networks=%s" % (item.get("effect"), ",".join(item.get("tools", [])), item.get("actions", []), item.get("paths", []), item.get("networks", [])))
        lines.append("")
    return "\n".join(lines)

