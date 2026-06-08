from __future__ import annotations

from typing import List, Optional

from .manifest import load_manifest, needs_from_tools
from .models import AnalysisReport, PermissionNeed
from .policy import evaluate_needs, generated_policy_from_needs, load_policy, validate_policy
from .risk import score_risks
from .transcript import load_transcript


def analyze(
    manifest_path: str,
    transcript_path: Optional[str] = None,
    org_policy_path: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> AnalysisReport:
    tools = load_manifest(manifest_path)
    needs = merge_needs([*needs_from_tools(tools), *(load_transcript(transcript_path) if transcript_path else [])])
    org_policy = load_policy(org_policy_path)
    policy = generated_policy_from_needs(needs, org_policy)
    findings = [*validate_policy(policy), *evaluate_needs(policy, needs, repo_root=repo_root)]
    risks = score_risks(tools, needs)
    return AnalysisReport(policy=policy, needs=needs, risks=risks, findings=findings, tools=tools)


def merge_needs(needs: List[PermissionNeed]) -> List[PermissionNeed]:
    merged = {}
    for need in needs:
        if need.tool in merged:
            merged[need.tool].merge(need)
        else:
            merged[need.tool] = PermissionNeed(
                tool=need.tool,
                actions=list(need.actions),
                paths=list(need.paths),
                networks=list(need.networks),
                reasons=list(need.reasons),
                source=need.source,
            )
    return list(merged.values())

