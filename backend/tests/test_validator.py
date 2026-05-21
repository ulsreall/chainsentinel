"""Tests for contract validator utilities."""

from app.utils.contract_validator import (
    estimate_token_usage,
    extract_contract_name,
    validate_solidity,
)


def test_validate_empty():
    assert validate_solidity("")["valid"] is False
    assert validate_solidity("   ")["valid"] is False


def test_validate_missing_pragma():
    code = "contract Foo {}"
    assert validate_solidity(code)["valid"] is False


def test_validate_missing_contract():
    code = "pragma solidity ^0.8.19;"
    assert validate_solidity(code)["valid"] is False


def test_validate_unbalanced_braces():
    code = "pragma solidity ^0.8.19; contract Foo { function bar() {}"
    result = validate_solidity(code)
    assert result["valid"] is False
    assert "Unbalanced" in result["error"]


def test_validate_valid_contract():
    code = "pragma solidity ^0.8.19; contract Foo {}"
    assert validate_solidity(code)["valid"] is True


def test_validate_interface_and_library():
    assert validate_solidity("pragma solidity ^0.8.19; interface IFoo {}")["valid"] is True
    assert validate_solidity("pragma solidity ^0.8.19; library LibFoo {}")["valid"] is True


def test_extract_contract_name():
    assert extract_contract_name("contract MyVault {}") == "MyVault"
    assert extract_contract_name("interface IERC20 {}") == "IERC20"
    assert extract_contract_name("library SafeMath {}") == "SafeMath"
    assert extract_contract_name("// nothing here") == "UnknownContract"


def test_estimate_token_usage():
    code = "pragma solidity ^0.8.19;\ncontract A {\n  uint256 x;\n}\n"
    est = estimate_token_usage(code)
    assert est["lines_of_code"] == 4
    assert est["agents_required"] == 4
    assert est["estimated_total_tokens"] > 0
