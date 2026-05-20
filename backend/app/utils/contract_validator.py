"""Solidity contract validation utilities."""

import re


def validate_solidity(code: str) -> dict:
    """Basic validation of Solidity source code."""
    code = code.strip()

    if not code:
        return {"valid": False, "error": "Empty code"}

    # Check for pragma
    if "pragma solidity" not in code and "pragma" not in code:
        return {"valid": False, "error": "Missing pragma directive"}

    # Check for contract/interface/library
    if not re.search(r"\b(contract|interface|library)\s+\w+", code):
        return {"valid": False, "error": "No contract, interface, or library found"}

    # Check for balanced braces
    opens = code.count("{")
    closes = code.count("}")
    if opens != closes:
        return {"valid": False, "error": f"Unbalanced braces: {opens} opening vs {closes} closing"}

    return {"valid": True, "error": None}


def extract_contract_name(code: str) -> str:
    """Extract the primary contract name from Solidity code."""
    match = re.search(r"\bcontract\s+(\w+)", code)
    if match:
        return match.group(1)

    match = re.search(r"\binterface\s+(\w+)", code)
    if match:
        return match.group(1)

    match = re.search(r"\blibrary\s+(\w+)", code)
    if match:
        return match.group(1)

    return "UnknownContract"


def estimate_token_usage(code: str) -> dict:
    """Estimate how many tokens an analysis will consume."""
    lines = code.split("\n")
    loc = len([l for l in lines if l.strip()])

    # Rough estimation: ~1 token per 3 chars of code, plus agent overhead
    code_tokens = len(code) // 3
    agent_overhead = 2000  # System prompts, instructions
    report_overhead = 1500  # Report generation context

    # 3 analysis agents + 1 report agent
    estimated_total = (code_tokens + agent_overhead) * 3 + (code_tokens * 2 + report_overhead)

    return {
        "lines_of_code": loc,
        "estimated_code_tokens": code_tokens,
        "estimated_total_tokens": estimated_total,
        "agents_required": 4,
        "estimated_cost_usd": round(estimated_total * 0.000002, 4),  # ~$2/M tokens
    }
