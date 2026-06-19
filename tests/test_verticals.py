"""Each vertical's Service.default() wires its graph + service with the
scripted test provider (so no API key is needed in CI)."""
from __future__ import annotations

from agentgraph_compliance import ComplianceService
from agentgraph_construction import ConstructionService
from agentgraph_healthcare import HealthcareService
from agentgraph_insurance import InsuranceService
from agentgraph_llm.testing import register_test_provider
from agentgraph_recruiting import RecruitingService
from agentgraph_support_ops import SupportOpsService

_TEST_LLM = {"llm_provider": "test", "llm_model": "test-model", "storage_url": "memory://"}


def setup_module() -> None:
    register_test_provider()


def test_support_ops_default() -> None:
    svc = SupportOpsService.default(**_TEST_LLM)
    assert svc.triage.config.name == "triage_agent"


def test_compliance_default() -> None:
    svc = ComplianceService.default(**_TEST_LLM)
    assert svc.reviewer.config.name == "reviewer_agent"


def test_recruiting_default() -> None:
    svc = RecruitingService.default(**_TEST_LLM)
    assert svc.sourcer.config.name == "sourcer"


def test_insurance_default() -> None:
    svc = InsuranceService.default(**_TEST_LLM)
    assert svc.fnol.config.name == "fnol_agent"


def test_construction_default() -> None:
    svc = ConstructionService.default(**_TEST_LLM)
    assert svc.rfi.config.name == "rfi_agent"


def test_healthcare_default() -> None:
    svc = HealthcareService.default(**_TEST_LLM)
    assert svc.intake.config.name == "intake_agent"
