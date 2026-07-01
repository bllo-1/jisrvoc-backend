"""
Unit tests for RuleEngine.

Tests cover:
- Disambiguation rules (Settlement with 3 cases)
- Compliance detection (GOSI, WPS, PDPL)
- Scope keyword matching
"""

import pytest
from pathlib import Path
from app.services.rule_engine import RuleEngine


@pytest.fixture
def rule_engine():
    """Create RuleEngine instance with test config."""
    # Use production rules for testing
    return RuleEngine()


class TestDisambiguationRules:
    """Test Section 2 disambiguation rules."""

    def test_final_settlement_eos(self, rule_engine):
        """Test 'Settlement' disambiguates to Final Settlement (EOS)."""
        text = "Employee is leaving and needs final settlement calculation for end of service"
        matches = rule_engine.apply_disambiguation_rules(text, "EN")

        assert len(matches) > 0
        settlement_match = next((m for m in matches if m["term"] == "settlement"), None)
        assert settlement_match is not None
        assert settlement_match["variant"] == "Final Settlement (EOS)"
        assert settlement_match["scope"] == "Payroll"

    def test_vacation_settlement(self, rule_engine):
        """Test 'Settlement' disambiguates to Vacation Settlement."""
        text = "How do I calculate vacation settlement for unused leave balance payout?"
        matches = rule_engine.apply_disambiguation_rules(text, "EN")

        assert len(matches) > 0
        settlement_match = next((m for m in matches if m["term"] == "settlement"), None)
        assert settlement_match is not None
        assert settlement_match["variant"] == "Vacation Settlement"
        assert settlement_match["scope"] == "Payroll"
        assert settlement_match.get("cross_tag") == "Attendance & Leaves"

    def test_expense_settlement(self, rule_engine):
        """Test 'Settlement' disambiguates to Expense Settlement."""
        text = "Need help with expense settlement and reimbursement receipt processing"
        matches = rule_engine.apply_disambiguation_rules(text, "EN")

        assert len(matches) > 0
        settlement_match = next((m for m in matches if m["term"] == "settlement"), None)
        assert settlement_match is not None
        assert settlement_match["variant"] == "Expense Settlement"
        assert settlement_match["scope"] == "Finance"

    def test_leave_approval(self, rule_engine):
        """Test 'Approval' disambiguates based on context."""
        text = "Manager cannot process leave approval requests in the mobile app"
        matches = rule_engine.apply_disambiguation_rules(text, "EN")

        approval_match = next((m for m in matches if m["term"] == "approval"), None)
        assert approval_match is not None
        assert approval_match["scope"] == "Attendance & Leaves"
        assert approval_match.get("cross_tag") == "Org Management"

    def test_government_integration(self, rule_engine):
        """Test 'Integration' disambiguates to Government Integration."""
        text = "Qiwa integration is failing for contract submissions in SA"
        matches = rule_engine.apply_disambiguation_rules(text, "EN")

        integration_match = next((m for m in matches if m["term"] == "integration"), None)
        assert integration_match is not None
        assert integration_match["variant"] == "Government Integration"
        assert integration_match["scope"] == "Integrations"

    def test_gosi_file_vs_rules(self, rule_engine):
        """Test GOSI disambiguates between file and rules."""
        # GOSI File case
        text1 = "GOSI file generation is producing wrong format for submission"
        matches1 = rule_engine.apply_disambiguation_rules(text1, "EN")
        gosi_match1 = next((m for m in matches1 if m["term"] == "gosi"), None)
        assert gosi_match1 is not None
        assert gosi_match1["variant"] == "GOSI File"
        assert gosi_match1["scope"] == "Integrations"

        # GOSI Rules case
        text2 = "GOSI contribution calculation rate is incorrect for registered wage"
        matches2 = rule_engine.apply_disambiguation_rules(text2, "EN")
        gosi_match2 = next((m for m in matches2 if m["term"] == "gosi"), None)
        assert gosi_match2 is not None
        assert gosi_match2["variant"] == "GOSI Rules"
        assert gosi_match2["scope"] == "Payroll"


class TestComplianceDetection:
    """Test Section 3 compliance lexicon."""

    def test_gosi_compliance_detection(self, rule_engine):
        """Test GOSI terms trigger compliance flag."""
        text = "GOSI file submission deadline is tomorrow and social insurance rates changed"
        matches = rule_engine.detect_compliance_terms(text, "EN")

        assert len(matches) > 0
        gosi_match = next((m for m in matches if m["regulation"] == "GOSI"), None)
        assert gosi_match is not None
        assert gosi_match["country"] == "SA"
        assert gosi_match["confidence"] == "High"
        assert "GOSI" in gosi_match["matched_terms"]

    def test_wps_compliance_detection(self, rule_engine):
        """Test WPS terms trigger compliance flag."""
        text = "WPS bank file must be submitted by wage protection deadline"
        matches = rule_engine.detect_compliance_terms(text, "EN")

        assert len(matches) > 0
        wps_match = next((m for m in matches if m["regulation"] == "WPS / Wage Protection System"), None)
        assert wps_match is not None
        assert "SA, UAE" in wps_match["country"]
        assert "WPS" in wps_match["matched_terms"]

    def test_pdpl_compliance_detection(self, rule_engine):
        """Test PDPL terms trigger compliance flag."""
        text = "We need personal data protection and soft delete for PDPL Article 18 compliance"
        matches = rule_engine.detect_compliance_terms(text, "EN")

        assert len(matches) > 0
        pdpl_match = next((m for m in matches if m["regulation"] == "PDPL"), None)
        assert pdpl_match is not None
        assert pdpl_match["country"] == "SA"
        # Should match multiple terms for high confidence
        assert len(pdpl_match["matched_terms"]) >= 2

    def test_trigger_phrases(self, rule_engine):
        """Test compliance trigger phrases."""
        text = "This is mandatory by law and required for government audit to avoid fine"
        matches = rule_engine.detect_compliance_terms(text, "EN")

        assert len(matches) > 0
        # Should match trigger phrases
        trigger_match = next((m for m in matches if m["regulation"] == "Trigger Phrase"), None)
        assert trigger_match is not None

    def test_qiwa_compliance(self, rule_engine):
        """Test Qiwa platform triggers compliance."""
        text = "Qiwa contract integration is required for government compliance"
        matches = rule_engine.detect_compliance_terms(text, "EN")

        qiwa_match = next((m for m in matches if m["regulation"] == "Qiwa"), None)
        assert qiwa_match is not None
        assert "Qiwa" in qiwa_match["matched_terms"]


class TestScopeMatching:
    """Test Section 1 taxonomy scope matching."""

    def test_payroll_scope_keywords(self, rule_engine):
        """Test Payroll scope keyword matching."""
        text = "Salary calculation is wrong and payslip shows incorrect deductions"
        matches = rule_engine.match_scope_keywords(text, "EN")

        assert len(matches) > 0
        assert matches[0]["scope"] == "Payroll"
        assert matches[0]["score"] > 0
        assert any("salary" in kw.lower() for kw in matches[0]["matched_keywords"])

    def test_attendance_leaves_scope(self, rule_engine):
        """Test Attendance & Leaves scope matching."""
        text = "Clock in not working and leave balance is incorrect after vacation"
        matches = rule_engine.match_scope_keywords(text, "EN")

        attendance_match = next((m for m in matches if m["scope"] == "Attendance & Leaves"), None)
        assert attendance_match is not None
        assert attendance_match["score"] > 0

    def test_employee_lifecycle_scope(self, rule_engine):
        """Test Employee Lifecycle scope matching."""
        text = "New employee onboarding is slow and offboarding documents are missing"
        matches = rule_engine.match_scope_keywords(text, "EN")

        lifecycle_match = next((m for m in matches if m["scope"] == "Employee Lifecycle"), None)
        assert lifecycle_match is not None
        assert lifecycle_match["score"] > 0

    def test_integrations_scope(self, rule_engine):
        """Test Integrations scope matching."""
        text = "Zoho API connector is broken and NetSuite sync failing"
        matches = rule_engine.match_scope_keywords(text, "EN")

        integrations_match = next((m for m in matches if m["scope"] == "Integrations"), None)
        assert integrations_match is not None
        assert integrations_match["score"] > 0

    def test_platform_issues_scope(self, rule_engine):
        """Test Platform Issues scope matching."""
        text = "System performance is slow, SSO login timeout, and PDPL data residency concerns"
        matches = rule_engine.match_scope_keywords(text, "EN")

        platform_match = next((m for m in matches if m["scope"] == "Platform Issues"), None)
        assert platform_match is not None
        assert platform_match["score"] > 0

    def test_scope_ranking_by_score(self, rule_engine):
        """Test scopes are ranked by keyword match score."""
        text = "Payroll salary calculation and payslip generation"
        matches = rule_engine.match_scope_keywords(text, "EN")

        # Should rank Payroll first due to multiple keyword matches
        assert len(matches) > 0
        assert matches[0]["scope"] == "Payroll"
        # Scores should be descending
        if len(matches) > 1:
            assert matches[0]["score"] >= matches[1]["score"]


class TestRuleEngineUtilities:
    """Test utility methods."""

    def test_is_valid_scope(self, rule_engine):
        """Test scope name validation."""
        assert rule_engine.is_valid_scope("Payroll") is True
        assert rule_engine.is_valid_scope("Attendance & Leaves") is True
        assert rule_engine.is_valid_scope("People Management") is False  # Legacy name

    def test_invalid_scope_names(self, rule_engine):
        """Test invalid/legacy scope names."""
        invalid_names = rule_engine.get_invalid_scope_names()
        assert "People Management" in invalid_names
        assert "People Mgmt" in invalid_names
        assert "Attendance" in invalid_names  # Must be "Attendance & Leaves"

    def test_get_scope_by_name(self, rule_engine):
        """Test scope lookup by name."""
        payroll_scope = rule_engine.get_scope_by_name("Payroll")
        assert payroll_scope is not None
        assert payroll_scope["name"] == "Payroll"
        assert payroll_scope["tribe"] == "Payroll"

        invalid_scope = rule_engine.get_scope_by_name("Invalid Scope Name")
        assert invalid_scope is None

    def test_hot_reload(self, rule_engine):
        """Test rule engine hot reload."""
        # Should not raise exception
        rule_engine.reload()
        # Rules should still be loaded
        assert len(rule_engine.taxonomy.get("scopes", [])) > 0
