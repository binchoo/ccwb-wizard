"""Integration-test fixtures.

Centralises the opt-in gate, AWS profile resolution, and the hard cost-budget
guard described in design.md (≤ ``$5`` per execution by default).

Environment variables:

- ``AWS_INTEGRATION_TEST=1``       — required to run any test in this folder.
- ``AWS_PROFILE``                  — boto3 profile to use (defaults to ``ccwb-dev-us-east-1``).
- ``AWS_INTEGRATION_TEST_BUDGET``  — max USD cost allowed before tests start
                                     (default ``5``). Tests abort if MTD spend
                                     already exceeds the budget.
- ``CCWB_DEPLOYMENT_NAME``         — CloudFormation stack name prefix used by
                                     `ccwb deploy` (default ``ccwb-dev``).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pytest


_OPT_IN_VAR = "AWS_INTEGRATION_TEST"


def _opt_in_enabled() -> bool:
    return os.environ.get(_OPT_IN_VAR, "").strip() == "1"


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def]
    """Skip every item under tests/integration/ unless opt-in flag is set.

    Using this hook (rather than an autouse fixture) avoids surprises when
    tests/integration/ is collected alongside sibling directories — the
    fixture-based ``pytest.skip(allow_module_level=True)`` only fires when
    integration is the sole rootdir.
    """
    if _opt_in_enabled():
        return
    skip_marker = pytest.mark.skip(
        reason=f"Integration tests skipped. Set {_OPT_IN_VAR}=1 to opt in."
    )
    for item in items:
        if "tests/integration" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def aws_profile() -> str:
    return os.environ.get("AWS_PROFILE", "ccwb-dev-us-east-1")


@pytest.fixture(scope="session")
def aws_region() -> str:
    return os.environ.get("AWS_REGION", "us-east-1")


@pytest.fixture(scope="session")
def deployment_name() -> str:
    return os.environ.get("CCWB_DEPLOYMENT_NAME", "ccwb-dev")


@pytest.fixture(scope="session")
def boto3_session(aws_profile: str, aws_region: str):  # type: ignore[no-untyped-def]
    boto3 = pytest.importorskip("boto3")
    return boto3.Session(profile_name=aws_profile, region_name=aws_region)


@pytest.fixture(scope="session", autouse=True)
def _enforce_budget() -> None:
    """Abort the run if the linked account is already over the test budget.

    Uses Cost Explorer's ``MONTHLY`` MTD value. We do not project; we only
    block obviously runaway accounts so a dev cannot blow the budget by
    accident. ``ce:GetCostAndUsage`` may be denied in some sandboxes — in
    that case we warn and continue.
    """

    if not _opt_in_enabled():
        return
    boto3 = pytest.importorskip("boto3")
    profile = os.environ.get("AWS_PROFILE", "ccwb-dev-us-east-1")
    region = os.environ.get("AWS_REGION", "us-east-1")
    session = boto3.Session(profile_name=profile, region_name=region)
    budget_usd = float(os.environ.get("AWS_INTEGRATION_TEST_BUDGET", "5"))
    try:
        ce = session.client("ce", region_name="us-east-1")
        today = dt.date.today()
        first = today.replace(day=1).isoformat()
        end = (today + dt.timedelta(days=1)).isoformat()
        resp = ce.get_cost_and_usage(
            TimePeriod={"Start": first, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
        )
        amount = float(
            resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]
        )
    except Exception as exc:  # noqa: BLE001 — best-effort guard
        # We do not want IAM noise to block opt-in suites. Print and proceed.
        print(f"[budget-guard] unable to read Cost Explorer ({exc}); continuing")
        return

    if amount > budget_usd:
        pytest.exit(
            f"Integration tests aborted: account MTD spend ${amount:.2f} "
            f"exceeds AWS_INTEGRATION_TEST_BUDGET=${budget_usd:.2f}.",
            returncode=2,
        )
