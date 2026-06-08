from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

from .models import (
    ACTION_EXECUTE,
    ACTION_NETWORK,
    ACTION_READ,
    ACTION_SECRET,
    ACTION_UNKNOWN,
    ACTION_WRITE,
    uniq,
)

READ_WORDS = ("read", "list", "grep", "search", "scan", "open", "load", "cat", "stat")
WRITE_WORDS = ("write", "edit", "create", "delete", "remove", "move", "rename", "patch", "save")
NETWORK_WORDS = ("http", "url", "fetch", "request", "browser", "download", "upload", "api", "web")
EXEC_WORDS = ("exec", "shell", "command", "terminal", "process", "spawn", "run")
SECRET_WORDS = ("token", "secret", "password", "credential", "apikey", "api_key", "key")
FILE_EXTENSIONS = ("py", "js", "ts", "json", "md", "txt", "yaml", "yml", "toml", "sh", "ps1")

PATH_KEYS = ("path", "file", "dir", "directory", "cwd", "workspace", "root")
NETWORK_KEYS = ("url", "uri", "host", "hostname", "domain", "endpoint", "base_url")


def normalize_action(action: str) -> str:
    action = (action or "").strip().lower().replace("-", "_")
    aliases = {
        "read": ACTION_READ,
        "file_read": ACTION_READ,
        "write": ACTION_WRITE,
        "file_write": ACTION_WRITE,
        "network_access": ACTION_NETWORK,
        "http": ACTION_NETWORK,
        "exec": ACTION_EXECUTE,
        "execute": ACTION_EXECUTE,
        "command": ACTION_EXECUTE,
        "secret": ACTION_SECRET,
    }
    return aliases.get(action, action)


def infer_actions_from_text(*parts: str) -> List[str]:
    text = " ".join(part or "" for part in parts).lower()
    actions = []
    if any(word in text for word in READ_WORDS):
        actions.append(ACTION_READ)
    if any(word in text for word in WRITE_WORDS):
        actions.append(ACTION_WRITE)
    if any(word in text for word in NETWORK_WORDS):
        actions.append(ACTION_NETWORK)
    if any(word in text for word in EXEC_WORDS):
        actions.append(ACTION_EXECUTE)
    if any(word in text for word in SECRET_WORDS):
        actions.append(ACTION_SECRET)
    return uniq(actions or [ACTION_UNKNOWN])


def walk_schema(schema: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(schema, dict):
        for key, value in schema.items():
            name = "%s.%s" % (prefix, key) if prefix else key
            yield name, value
            yield from walk_schema(value, name)
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            name = "%s[%s]" % (prefix, index)
            yield name, value
            yield from walk_schema(value, name)


def infer_from_schema(schema: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[str]]:
    actions = []
    paths = []
    networks = []
    reasons = []
    for dotted, value in walk_schema(schema):
        key = dotted.split(".")[-1].lower()
        if isinstance(value, str):
            actions.extend(infer_actions_from_text(key, value))
            if looks_like_path(value):
                paths.append(value)
            if looks_like_network(value):
                networks.append(normalize_network(value))
        if any(item in key for item in PATH_KEYS):
            actions.append(ACTION_READ)
            reasons.append("schema 字段 %s 看起来包含路径" % dotted)
            paths.extend(schema_literals(value))
        if any(item in key for item in NETWORK_KEYS):
            actions.append(ACTION_NETWORK)
            reasons.append("schema 字段 %s 看起来包含网络目标" % dotted)
            networks.extend(normalize_network(item) for item in schema_literals(value))
        if any(item in key for item in SECRET_WORDS):
            actions.append(ACTION_SECRET)
            reasons.append("schema 字段 %s 看起来包含密钥" % dotted)
    return clean_actions(actions), uniq(paths), uniq(networks), uniq(reasons)


def schema_literals(value: Any) -> List[str]:
    results = []
    if isinstance(value, dict):
        for key in ("const", "default", "example"):
            if key in value and isinstance(value[key], str):
                results.append(value[key])
        enum = value.get("enum")
        if isinstance(enum, list):
            results.extend(str(item) for item in enum if isinstance(item, str))
        examples = value.get("examples")
        if isinstance(examples, list):
            results.extend(str(item) for item in examples if isinstance(item, str))
    elif isinstance(value, str):
        results.append(value)
    return uniq(results)


def looks_like_path(value: str) -> bool:
    if not value:
        return False
    if looks_like_network(value):
        return False
    return bool(
        re.search(r"(^[A-Za-z]:\\|^/|^\./|^\.\./|\\|/)", value)
        or re.search(r"\.(%s)$" % "|".join(FILE_EXTENSIONS), value, flags=re.IGNORECASE)
    )


def looks_like_network(value: str) -> bool:
    parsed = urlparse(value)
    if not parsed.scheme and re.search(r"\.(%s)$" % "|".join(FILE_EXTENSIONS), value, flags=re.IGNORECASE):
        return False
    return parsed.scheme in ("http", "https", "ws", "wss") or bool(re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(:\d+)?$", value))


def normalize_network(value: str) -> str:
    if not value:
        return value
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        return parsed.netloc.lower()
    return value.lower().strip("/")


def infer_from_arguments(arguments: Dict[str, Any]) -> Tuple[List[str], List[str], List[str], List[str]]:
    actions = []
    paths = []
    networks = []
    reasons = []
    for dotted, value in walk_schema(arguments):
        key = dotted.split(".")[-1].lower()
        if isinstance(value, str):
            if looks_like_path(value):
                paths.append(value)
                actions.append(ACTION_WRITE if any(word in key for word in ("out", "write", "dest", "target")) else ACTION_READ)
                reasons.append("transcript 参数 %s 使用路径 %s" % (dotted, value))
            if looks_like_network(value):
                networks.append(normalize_network(value))
                actions.append(ACTION_NETWORK)
                reasons.append("transcript 参数 %s 使用网络目标 %s" % (dotted, value))
            actions.extend(infer_actions_from_text(key, value))
        elif any(item in key for item in PATH_KEYS):
            actions.append(ACTION_READ)
            reasons.append("transcript 参数 %s 看起来是路径字段" % dotted)
        elif any(item in key for item in NETWORK_KEYS):
            actions.append(ACTION_NETWORK)
            reasons.append("transcript 参数 %s 看起来是网络字段" % dotted)
        elif any(item in key for item in SECRET_WORDS):
            actions.append(ACTION_SECRET)
            reasons.append("transcript 参数 %s 看起来是密钥字段" % dotted)
    return clean_actions(actions), uniq(paths), uniq(networks), uniq(reasons)


def clean_actions(actions: Iterable[str]) -> List[str]:
    normalized = uniq(normalize_action(action) for action in actions)
    if len(normalized) > 1 and ACTION_UNKNOWN in normalized:
        normalized = [action for action in normalized if action != ACTION_UNKNOWN]
    return normalized
