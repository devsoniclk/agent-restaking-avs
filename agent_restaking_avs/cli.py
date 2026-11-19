"""
Command-line interface for the Agent Restaking AVS protocol.
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .arbitration import ArbitrationTribunal
from .models import (
    DisputeType,
    FraudClaim,
    OperatorStatus,
    StakePoolConfig,
    TaskReceipt,
)
from .staking import StakingManager
from .waterfall import SlashingWaterfallEngine

console = Console()


def create_demo_network() -> tuple[StakingManager, SlashingWaterfallEngine, ArbitrationTribunal]:
    """Initialize a demo AVS network populated with foundational test operators."""
    config = StakePoolConfig()
    staking = StakingManager(config)
    waterfall = SlashingWaterfallEngine(staking)
    tribunal = ArbitrationTribunal(staking, waterfall)

    staking.register_operator(
        operator_id="operator-alpha",
        did="did:agent:eth:0x1111111111111111111111111111111111111111",
        public_key="0xpubkey_alpha",
        native_stake=50000.0,
        restaked_eth=50.0,
    )
    staking.register_operator(
        operator_id="operator-beta",
        did="did:agent:eth:0x2222222222222222222222222222222222222222",
        public_key="0xpubkey_beta",
        native_stake=30000.0,
        restaked_eth=35.0,
    )
    staking.register_operator(
        operator_id="operator-gamma",
        did="did:agent:eth:0x3333333333333333333333333333333333333333",
        public_key="0xpubkey_gamma",
        native_stake=20000.0,
        restaked_eth=25.0,
    )

    return staking, waterfall, tribunal


@click.group()
@click.version_option(version="0.1.0", prog_name="agent-restaking-avs")
def main() -> None:
    """Agent Restaking AVS: Dual-Quorum Security & SLA Arbitration."""
    pass


@main.command(name="status")
@click.option("--json-out", is_flag=True, help="Output status in raw JSON format.")
def status_cmd(json_out: bool) -> None:
    """Display active operators, restaked collateral pools, and total security in USD."""
    staking, _, _ = create_demo_network()

    if json_out:
        data = {
            "total_security_usd": staking.total_economic_security_usd(),
            "operators": [
                {
                    "operator_id": op.operator_id,
                    "did": op.did,
                    "native_stake": op.native_stake,
                    "restaked_eth": op.restaked_eth,
                    "status": op.status.value,
                    "tasks_completed": op.tasks_completed,
                }
                for op in staking.list_operators()
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    table = Table(title="AVS Operator Registry & Dual-Quorum Collateral")
    table.add_column("Operator ID", style="cyan", no_wrap=True)
    table.add_column("W3C DID", style="dim")
    table.add_column("Native Stake (Tokens)", justify="right")
    table.add_column("Restaked ETH", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Completed", justify="right")

    for op in staking.list_operators():
        status_color = "green" if op.status == OperatorStatus.ACTIVE else "red"
        table.add_row(
            op.operator_id,
            op.did[:26] + "...",
            f"{op.native_stake:,.1f}",
            f"{op.restaked_eth:,.2f} ETH",
            f"[{status_color}]{op.status.value}[/{status_color}]",
            str(op.tasks_completed),
        )

    console.print(table)
    total_sec = staking.total_economic_security_usd()
    console.print(
        Panel(
            f"[bold green]Total Blended Economic Security:[/] [bold white]${total_sec:,.2f} USD[/]\n"
            f"[dim]Quorum 1 (Native @ $2.50) + Quorum 2 (ETH @ $3,200.00)[/]",
            title="AVS Economic Metrics",
        )
    )


@main.command(name="verify-consensus")
@click.argument("signers", nargs=-1, required=True)
def verify_consensus_cmd(signers: tuple[str, ...]) -> None:
    """Evaluate dual-quorum supermajority threshold for a set of signing operators."""
    staking, _, _ = create_demo_network()
    res = staking.verify_dual_quorum(list(signers))

    console.print(f"[bold]Evaluating Dual-Quorum Consensus for Signers:[/] {list(signers)}")
    console.print(f" • Native Stake: [cyan]{res.native_pct:.2%}[/] (Weight: {res.native_weight:,.1f} / {res.native_total:,.1f})")
    console.print(f" • Restaked ETH: [cyan]{res.eth_pct:.2%}[/] (Weight: {res.eth_weight:,.2f} / {res.eth_total:,.2f})")
    console.print(f" • Required Threshold: [yellow]{res.threshold:.2%}[/]")

    if res.approved:
        console.print("[bold green]✔ CONSENSUS APPROVED: Supermajority reached across both quorums.[/]")
    else:
        console.print(f"[bold red]✖ CONSENSUS REJECTED:[/] {res.rejection_reason}")
        sys.exit(1)


@main.command(name="audit")
def audit_cmd() -> None:
    """Perform formal invariant audit of the AVS pool and slashing waterfall."""
    staking, waterfall, tribunal = create_demo_network()

    # Run a test task and dispute simulation
    receipt = TaskReceipt(
        task_id="task-audit-001",
        operator_id="operator-gamma",
        escrow_usd=500.0,
        deadline=1000.0,
        expected_schema_hash="hash-expected",
        actual_output_hash="hash-mismatched",
        allowed_tools=["search", "calculate"],
        executed_tools=["search", "calculate", "rm_rf"],
        state_root="0xstate001",
        submitted_at=1050.0,
    )
    tribunal.record_receipt(receipt)

    claim = FraudClaim(
        claim_id="claim-audit-001",
        challenger_did="did:agent:eth:0xchallenger",
        operator_id="operator-gamma",
        task_id="task-audit-001",
        dispute_type=DisputeType.UNAUTHORIZED_TOOL_EXECUTION,
        bond_usd=100.0,
        evidence={"allowed_tools": ["search"], "executed_tools": ["search", "rm_rf"]},
    )
    tribunal.file_dispute(claim)
    guilty, resolved_type, slashing = tribunal.adjudicate("claim-audit-001")

    table = Table(title="AVS Slashing Waterfall Audit Ledger")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Operator", slashing.operator_id if slashing else "N/A")
    table.add_row("Violation", resolved_type.value)
    table.add_row("Total Slashed", f"${slashing.total_slashed_usd:,.2f} USD" if slashing else "N/A")
    table.add_row("Challenger Bounty (25%)", f"${slashing.challenger_bounty_usd:,.2f} USD" if slashing else "N/A")
    table.add_row("Insurance Reserve (45%)", f"${slashing.insurance_reserve_usd:,.2f} USD" if slashing else "N/A")
    table.add_row("Burned (30%)", f"${slashing.burn_usd:,.2f} USD" if slashing else "N/A")
    table.add_row("User Escrow Refund (100%)", f"${slashing.user_refund_usd:,.2f} USD" if slashing else "N/A")

    console.print(table)
    # Conservation check
    if slashing:
        sum_allocations = round(slashing.challenger_bounty_usd + slashing.insurance_reserve_usd + slashing.burn_usd, 2)
        conserved = abs(sum_allocations - slashing.total_slashed_usd) < 0.01
        if conserved:
            console.print("[bold green]✔ Invariant Passed:[/] Total Slashed == Bounty + Insurance + Burn.")
        else:
            console.print("[bold red]✖ Conservation Invariant Violated![/]")
            sys.exit(1)


if __name__ == "__main__":
    main()
