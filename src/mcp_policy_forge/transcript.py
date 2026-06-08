from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

from .infer import infer_actions_from_text, infer_from_arguments
from .io import load_text_file
from .models import PermissionNeed, uniq


def load_transcript(path: str) -> List[PermissionNeed]:
    return parse_transcript(load_text_file(path), source=path)


def parse_transcript(text: str, source: str = "transcript") -> List[PermissionNeed]:
    objects = parse_transcript_objects(text)
    needs_by_tool: Dict[str, PermissionNeed] = {}
    for obj in objects:
        for name, arguments in extract_tool_calls(obj):
            actions, paths, networks, reasons = infer_from_arguments(arguments)
            actions = uniq([*infer_actions_from_text(name), *actions])
            need = PermissionNeed(
                tool=name,
                actions=actions,
                paths=paths,
                networks=networks,
                reasons=reasons or ["transcript 调用了工具 %s" % name],
                source=source,
            )
            if name in needs_by_tool:
                needs_by_tool[name].merge(need)
            else:
                needs_by_tool[name] = need
    if not needs_by_tool:
        for name in extract_textual_tool_names(text):
            needs_by_tool[name] = PermissionNeed(
                tool=name,
                actions=infer_actions_from_text(name),
                reasons=["文本 transcript 提到工具 %s" % name],
                source=source,
            )
    return list(needs_by_tool.values())


def parse_transcript_objects(text: str) -> List[Any]:
    stripped = text.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        pass
    objects = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            objects.append({"text": line})
    return objects


def extract_tool_calls(obj: Any) -> Iterable[tuple]:
    if isinstance(obj, list):
        for item in obj:
            yield from extract_tool_calls(item)
        return
    if not isinstance(obj, dict):
        return
    if isinstance(obj.get("tool_calls"), list):
        for call in obj["tool_calls"]:
            yield from extract_tool_calls(call)
    function = obj.get("function")
    if isinstance(function, dict) and function.get("name"):
        yield str(function["name"]), parse_arguments(function.get("arguments"))
    if obj.get("type") in ("tool_call", "function_call") and (obj.get("name") or obj.get("tool")):
        yield str(obj.get("name") or obj.get("tool")), parse_arguments(obj.get("arguments") or obj.get("input") or obj.get("args"))
    if obj.get("tool") and isinstance(obj.get("tool"), str):
        yield str(obj["tool"]), parse_arguments(obj.get("arguments") or obj.get("input") or obj.get("args"))
    if obj.get("name") and any(key in obj for key in ("arguments", "input", "args")):
        yield str(obj["name"]), parse_arguments(obj.get("arguments") or obj.get("input") or obj.get("args"))
    for key in ("message", "messages", "events", "content"):
        value = obj.get(key)
        if isinstance(value, (dict, list)):
            yield from extract_tool_calls(value)


def parse_arguments(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            return {"value": value}
    return {"value": value}


def extract_textual_tool_names(text: str) -> List[str]:
    patterns = [
        r"\btool\s*[:=]\s*([A-Za-z0-9_.-]+)",
        r"\bcall(?:ed|ing)?\s+([A-Za-z0-9_.-]+)",
    ]
    names = []
    for pattern in patterns:
        names.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return uniq(names)

