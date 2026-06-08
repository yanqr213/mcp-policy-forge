from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .diff import diff_policies, diff_to_markdown
from .engine import analyze
from .io import InputError, load_json_file, write_json, write_text
from .outputs import report_to_junit, report_to_markdown
from .policy import parse_policy, validate_policy

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INVALID = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcp-policy-forge", description="生成/校验 MCP least-privilege 权限策略")
    sub = parser.add_subparsers(dest="command")

    generate = sub.add_parser("generate", help="从 manifest/transcript/org policy 生成策略与报告")
    add_common_generate_args(generate)

    check = sub.add_parser("check", help="CI 模式: 生成策略并根据发现问题/风险返回退出码")
    add_common_generate_args(check)

    validate = sub.add_parser("validate", help="校验 policy JSON 配置")
    validate.add_argument("--policy", required=True, help="策略 JSON 文件")
    validate.add_argument("--json", dest="json_out", help="输出校验结果 JSON")

    diff = sub.add_parser("diff", help="比较两个 policy JSON")
    diff.add_argument("--old", required=True, help="旧策略 JSON")
    diff.add_argument("--new", required=True, help="新策略 JSON")
    diff.add_argument("--out-json", help="输出 diff JSON")
    diff.add_argument("--out-md", help="输出 diff Markdown")
    return parser


def add_common_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True, help="MCP tool manifest JSON")
    parser.add_argument("--transcript", help="示例 transcript，支持 JSON/JSONL/文本")
    parser.add_argument("--org-policy", help="组织基线 policy JSON")
    parser.add_argument("--repo-root", help="仓库根目录，用于路径越权检查")
    parser.add_argument("--out-json", help="输出机器可读 JSON 报告")
    parser.add_argument("--out-policy", help="仅输出生成后的 policy JSON")
    parser.add_argument("--out-md", help="输出 Markdown 报告")
    parser.add_argument("--junit", help="输出 JUnit XML")
    parser.add_argument("--fail-on", choices=["never", "violations", "medium", "high", "critical"], default="violations", help="check/generate 的失败阈值")


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_INVALID
    try:
        if args.command in ("generate", "check"):
            return run_generate(args)
        if args.command == "validate":
            return run_validate(args)
        if args.command == "diff":
            return run_diff(args)
    except InputError as exc:
        print("输入错误: %s" % exc, file=sys.stderr)
        return EXIT_INVALID
    except OSError as exc:
        print("I/O 错误: %s" % exc, file=sys.stderr)
        return EXIT_INVALID
    return EXIT_INVALID


def run_generate(args: argparse.Namespace) -> int:
    report = analyze(args.manifest, transcript_path=args.transcript, org_policy_path=args.org_policy, repo_root=args.repo_root)
    if args.out_json:
        write_json(args.out_json, report.to_dict())
    if args.out_policy:
        write_json(args.out_policy, report.policy.to_dict())
    if args.out_md:
        write_text(args.out_md, report_to_markdown(report))
    if args.junit:
        write_text(args.junit, report_to_junit(report))
    if not any([args.out_json, args.out_policy, args.out_md, args.junit]):
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_FAILED if should_fail(report, args.fail_on) else EXIT_OK


def should_fail(report, threshold: str) -> bool:
    if threshold == "never":
        return False
    if threshold == "violations":
        return any(finding.severity == "error" for finding in report.findings)
    order = {"medium": 25, "high": 50, "critical": 75}
    minimum = order[threshold]
    return any(risk.score >= minimum for risk in report.risks) or any(finding.severity == "error" for finding in report.findings)


def run_validate(args: argparse.Namespace) -> int:
    policy = parse_policy(load_json_file(args.policy))
    findings = validate_policy(policy)
    payload = {"ok": not any(item.severity == "error" for item in findings), "findings": [item.to_dict() for item in findings]}
    if args.json_out:
        write_json(args.json_out, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_FAILED if not payload["ok"] else EXIT_OK


def run_diff(args: argparse.Namespace) -> int:
    result = diff_policies(load_json_file(args.old), load_json_file(args.new))
    if args.out_json:
        write_json(args.out_json, result)
    if args.out_md:
        write_text(args.out_md, diff_to_markdown(result))
    if not args.out_json and not args.out_md:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK

