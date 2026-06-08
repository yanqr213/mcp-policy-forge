from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .infer import infer_actions_from_text, infer_from_schema
from .io import InputError, load_json_file
from .models import PermissionNeed, ToolSpec, uniq


def load_manifest(path: str) -> List[ToolSpec]:
    return parse_manifest(load_json_file(path), source=path)


def parse_manifest(data: Any, source: str = "manifest") -> List[ToolSpec]:
    tools = []
    for item in iter_tool_entries(data):
        name = str(item.get("name") or item.get("tool") or "").strip()
        if not name:
            continue
        description = str(item.get("description") or item.get("title") or "")
        schema = item.get("inputSchema") or item.get("input_schema") or item.get("schema") or item.get("json_schema") or {}
        if not isinstance(schema, dict):
            schema = {}
        actions, paths, networks, _ = infer_from_schema(schema)
        actions = uniq([*infer_actions_from_text(name, description), *actions])
        tools.append(
            ToolSpec(
                name=name,
                description=description,
                schema=schema,
                source=source,
                inferred_actions=actions,
                inferred_paths=paths,
                inferred_networks=networks,
            )
        )
    if not tools:
        raise InputError("manifest 中没有找到 MCP tools")
    return tools


def iter_tool_entries(data: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(data, dict):
        return
    candidates = []
    for key in ("tools", "tool_manifest"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    servers = data.get("mcpServers") or data.get("servers")
    if isinstance(servers, dict):
        for server_name, server in servers.items():
            if isinstance(server, dict) and isinstance(server.get("tools"), list):
                for item in server["tools"]:
                    if isinstance(item, dict):
                        merged = dict(item)
                        merged.setdefault("server", server_name)
                        candidates.append(merged)
    for item in candidates:
        if isinstance(item, dict):
            yield item


def needs_from_tools(tools: List[ToolSpec]) -> List[PermissionNeed]:
    needs = []
    for tool in tools:
        reasons = ["manifest 推断: %s" % ", ".join(tool.inferred_actions or ["unknown"])]
        needs.append(
            PermissionNeed(
                tool=tool.name,
                actions=tool.inferred_actions,
                paths=tool.inferred_paths,
                networks=tool.inferred_networks,
                reasons=reasons,
                source=tool.source,
            )
        )
    return needs

