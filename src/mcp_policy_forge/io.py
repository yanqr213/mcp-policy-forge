from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class InputError(ValueError):
    """Raised when a user-provided file is missing or malformed."""


def load_json_file(path: str) -> Any:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise InputError("文件不存在: %s" % path) from exc
    except json.JSONDecodeError as exc:
        raise InputError("JSON 解析失败: %s:%s %s" % (path, exc.lineno, exc.msg)) from exc


def load_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise InputError("文件不存在: %s" % path) from exc


def write_text(path: str, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def write_json(path: str, data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

