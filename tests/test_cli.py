"""
Tests for the CLI interface commands.
"""

from click.testing import CliRunner
from agent_restaking_avs.cli import main


def test_cli_status_table():
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "operator-alpha" in result.output
    assert "Total Blended Economic Security" in result.output


def test_cli_status_json():
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--json-out"])
    assert result.exit_code == 0
    assert "total_security_usd" in result.output
    assert "operator-alpha" in result.output


def test_cli_verify_consensus_approved():
    runner = CliRunner()
    result = runner.invoke(main, ["verify-consensus", "operator-alpha", "operator-beta"])
    assert result.exit_code == 0
    assert "CONSENSUS APPROVED" in result.output


def test_cli_verify_consensus_rejected():
    runner = CliRunner()
    # operator-gamma alone is only 20% stake, below 66.67%
    result = runner.invoke(main, ["verify-consensus", "operator-gamma"])
    assert result.exit_code == 1
    assert "CONSENSUS REJECTED" in result.output


def test_cli_audit():
    runner = CliRunner()
    result = runner.invoke(main, ["audit"])
    assert result.exit_code == 0
    assert "Invariant Passed" in result.output
    assert "Total Slashed == Bounty + Insurance + Burn" in result.output
