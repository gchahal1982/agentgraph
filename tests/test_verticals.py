"""Other verticals: verify each Service.default() wires its graph + service."""
from __future__ import annotations

from agentgraph_compliance import ComplianceService
from agentgraph_construction import ConstructionService
from agentgraph_healthcare import HealthcareService
from agentgraph_insurance import InsuranceService
from agentgraph_recruiting import RecruitingService
from agentgraph_support_ops import SupportOpsService


def test_support_ops_default() -> None:
    svc = SupportOpsService.default()
    assert svc.triage.config.name == "triage_agent"


def test_compliance_default() -> None:
    svc = ComplianceService.default()
    assert svc.reviewer.config.name == "reviewer_agent"


def test_recruiting_default() -> None:
    svc = RecruitingService.default()
    assert svc.sourcer.config.name == "sourcer"


def test_insurance_default() -> None:
    svc = InsuranceService.default()
    assert svc.fnol.config.name == "fnol_agent"


def test_construction_default() -> None:
    svc = ConstructionService.default()
    assert svc.rfi.config.name == "rfi_agent"


def test_healthcare_default() -> None:
    svc = HealthcareService.default()
    assert svc.intake.config.name == "intake_agent"
