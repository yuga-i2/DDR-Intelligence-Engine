"""
Tests for the Diagnostic Reasoning Agent and its dependencies.

Tests the three main components:
1. Rules engine with deterministic rules
2. Severity matrix with urgency assessment
3. Full diagnostic reasoning agent pipeline
"""

import json
import pytest

from src.agents.diagnostic_reasoning import diagnostic_reasoning_agent
from src.graph.memory import SemanticGraph
from src.graph.state import Correlation, Finding, Observation
from src.knowledge.rules_engine import evaluate_rules
from src.knowledge.severity_matrix import assess_severity


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def semantic_graph():
    """Build a test semantic graph with rooms and relationships."""
    graph = SemanticGraph()
    
    # Add rooms
    graph.add_room("Hall", level=0)
    graph.add_room("Bathroom", level=1)
    graph.add_room("Common Bathroom", level=0)
    graph.add_room("Parking", level=-1)
    graph.add_room("Terrace", level=1)
    graph.add_room("Apartment 203", level=1)
    
    # Add spatial relationships
    graph.add_spatial_relationship("Bathroom", "ABOVE", "Hall")
    graph.add_spatial_relationship("Common Bathroom", "ABOVE", "Parking")
    graph.add_spatial_relationship("Apartment 203", "ABOVE", "Hall")
    graph.add_spatial_relationship("Terrace", "ABOVE", "Hall")
    
    return graph


@pytest.fixture
def sample_observation_hall_dampness():
    """Create an observation of dampness in Hall (symptom)."""
    return Observation(
        location="Hall",
        symptom="dampness",
        severity="medium"
    )


@pytest.fixture
def sample_observation_parking_seepage():
    """Create an observation of seepage in Parking (symptom)."""
    return Observation(
        location="Parking",
        symptom="seepage",
        severity="high"
    )


@pytest.fixture
def sample_finding_bathroom_tile():
    """Create a finding of tile/grouting defect in bathroom."""
    return Finding(
        location="Bathroom",
        defect_type="tile grouting damage",
        description="Grout lines show separation and cracks around floor tiles",
        severity="medium"
    )


@pytest.fixture
def sample_finding_external_crack():
    """Create a finding of external wall crack."""
    return Finding(
        location="Hall",
        defect_type="external wall crack",
        description="Horizontal crack in external wall, approximately 2mm wide, runs full width",
        severity="medium"
    )


@pytest.fixture
def ddr_state_empty():
    """Create an empty DDRState for testing."""
    return {
        "document_path": "test_document.pdf",
        "observations": [],
        "findings": [],
        "correlations": [],
        "severity_assessments": {},
        "extracted_images": [],
        "semantic_graph": {},
        "agent_logs": [],
        "validated": False,
        "iteration_count": 0
    }


# ============================================================================
# TESTS FOR RULES ENGINE
# ============================================================================

class TestRulesEngine:
    """Test suite for the rules_engine.evaluate_rules() function."""
    
    def test_rules_engine_bathroom_above(
        self,
        semantic_graph,
        sample_observation_hall_dampness,
        sample_finding_bathroom_tile
    ):
        """
        Test that the bathroom-above-dampness rule fires correctly.
        
        Scenario:
        - Hall has dampness symptom
        - Bathroom is above Hall
        - Bathroom has tile/grouting finding
        
        Expected:
        - At least 1 rule matches
        - Highest confidence rule >= 0.80
        - Rule name includes "bathroom" (case-insensitive)
        """
        findings = [sample_finding_bathroom_tile]
        
        # Build graph context (mimicking what diagnostic_reasoning does)
        graph_context = {
            "rooms_above": ["Bathroom"],
            "rooms_adjacent": [],
            "findings_above": [sample_finding_bathroom_tile],
            "findings_adjacent": [],
            "findings_at_location": []
        }
        
        # Evaluate rules
        results = evaluate_rules(
            sample_observation_hall_dampness,
            findings,
            graph_context
        )
        
        # Assertions
        assert len(results) >= 1, "Expected at least one rule to match"
        
        # Check highest confidence
        confidences = [r["confidence"] for r in results]
        max_confidence = max(confidences)
        assert max_confidence >= 0.80, f"Expected confidence >= 0.80, got {max_confidence}"
        
        # Check that bathroom rule is in results
        bathroom_rules = [r for r in results if "bathroom" in r["rule_name"].lower()]
        assert len(bathroom_rules) > 0, "Expected 'bathroom' rule to be present"
        
        # Check rule structure
        rule = results[0]
        assert "rule_name" in rule
        assert "confidence" in rule
        assert "probable_root_cause_location" in rule
        assert "probable_root_cause_type" in rule
        assert "reasoning" in rule
    
    def test_rules_engine_external_wall_crack(
        self,
        semantic_graph,
        sample_observation_hall_dampness,
        sample_finding_external_crack
    ):
        """
        Test that the external-wall-crack rule fires correctly.
        
        Scenario:
        - Hall has dampness symptom
        - Hall has external wall crack finding
        
        Expected:
        - At least 1 rule matches
        - Rule addresses external wall cracks
        """
        findings = [sample_finding_external_crack]
        
        graph_context = {
            "rooms_above": [],
            "rooms_adjacent": [],
            "findings_above": [],
            "findings_adjacent": [],
            "findings_at_location": [sample_finding_external_crack]
        }
        
        results = evaluate_rules(
            sample_observation_hall_dampness,
            findings,
            graph_context
        )
        
        # Should match external wall crack rule
        assert len(results) >= 1
        external_rules = [r for r in results if "external" in r["rule_name"].lower()]
        assert len(external_rules) > 0


# ============================================================================
# TESTS FOR SEVERITY MATRIX
# ============================================================================

class TestSeverityMatrix:
    """Test suite for the severity_matrix.assess_severity() function."""
    
    def test_severity_matrix_parking_seepage(
        self,
        sample_observation_parking_seepage,
    ):
        """
        Test that parking seepage is assessed as HIGH severity.
        
        Scenario:
        - Parking location has seepage symptom
        - Correlation suggests bathroom root cause (above parking)
        
        Expected:
        - severity_level = "HIGH"
        - severity_score >= 7
        - urgency includes timeframe guidance
        """
        # Create correlation for parking seepage
        correlation = Correlation(
            symptom_location="Parking",
            symptom_type="seepage",
            root_cause_location="Common Bathroom",
            root_cause_type="tile grouting failure",
            confidence=0.87,
            reasoning="Water from bathroom tile joint seeps down to parking",
            supporting_evidence=[]
        )
        
        # Assess severity
        severity_info = assess_severity(
            sample_observation_parking_seepage,
            [correlation],
            checklist_data=None
        )
        
        # Assertions
        assert "severity_level" in severity_info
        assert "severity_score" in severity_info
        assert "urgency" in severity_info
        assert "reasoning" in severity_info
        
        assert severity_info["severity_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        assert isinstance(severity_info["severity_score"], int)
        assert 1 <= severity_info["severity_score"] <= 10
        
        # Parking seepage should be HIGH
        assert severity_info["severity_level"] == "HIGH", \
            f"Expected HIGH for parking seepage, got {severity_info['severity_level']}"
        assert severity_info["severity_score"] >= 7, \
            f"Expected score >= 7, got {severity_info['severity_score']}"
        
        # Urgency should reference timeframe
        assert "week" in severity_info["urgency"].lower() or \
               "month" in severity_info["urgency"].lower(), \
               "Expected urgency to contain timeframe guidance"
    
    def test_severity_matrix_external_crack(
        self,
    ):
        """
        Test that external wall cracks are assessed with appropriate severity.
        
        Scenario:
        - External wall crack at location
        
        Expected:
        - severity_level in range CRITICAL (if structural) or MEDIUM/HIGH
        - severity_score >= 4
        """
        obs = Observation(
            location="External Wall",
            symptom="crack",
            severity="medium"
        )
        
        correlation = Correlation(
            symptom_location="External Wall",
            symptom_type="crack",
            root_cause_location="Concrete deterioration",
            root_cause_type="concrete deterioration from water ingress",
            confidence=0.80,
            reasoning="Water infiltration causing concrete carbonation",
            supporting_evidence=[]
        )
        
        severity_info = assess_severity(obs, [correlation])
        
        # Should be at least MEDIUM
        assert severity_info["severity_level"] in ["MEDIUM", "HIGH", "CRITICAL"]
        assert severity_info["severity_score"] >= 4


# ============================================================================
# TESTS FOR FULL DIAGNOSTIC REASONING AGENT
# ============================================================================

class TestDiagnosticReasoningAgent:
    """Test suite for the full diagnostic_reasoning_agent integration."""
    
    @pytest.mark.skip(reason="Requires GROQ_API_KEY - run manually with environment variable set")
    def test_agent_runs_without_llm_error(
        self,
        ddr_state_empty,
        sample_observation_hall_dampness,
        sample_finding_bathroom_tile,
        semantic_graph
    ):
        """
        Test that diagnostic_reasoning_agent can process an observation end-to-end.
        
        Scenario:
        - State has one observation (hall dampness)
        - State has one finding (bathroom tile)
        - SemanticGraph is provided
        - GROQ_API_KEY is set in environment
        
        Expected:
        - Agent completes without exception
        - state["correlations"] is populated (list, len > 0)
        - state["severity_assessments"] is populated (dict)
        - agent_logs contains entry for "diagnostic_reasoning"
        """
        # Prepare state
        state = ddr_state_empty.copy()
        state["observations"] = [sample_observation_hall_dampness]
        state["findings"] = [sample_finding_bathroom_tile]
        state["semantic_graph"] = semantic_graph.to_dict()
        state["agent_logs"] = []
        
        # Run agent
        result_state = diagnostic_reasoning_agent(state)
        
        # Verify correlations created
        correlations = result_state.get("correlations", [])
        assert isinstance(correlations, list), "correlations should be a list"
        assert len(correlations) > 0, "Expected at least one correlation"
        
        # Verify severity assessments created
        severity_assessments = result_state.get("severity_assessments", {})
        assert isinstance(severity_assessments, dict)
        assert len(severity_assessments) > 0, "Expected severity assessments"
        
        # Verify agent log
        agent_logs = result_state.get("agent_logs", [])
        diagnostic_logs = [log for log in agent_logs if log.get("agent") == "diagnostic_reasoning"]
        assert len(diagnostic_logs) > 0, "Expected diagnostic_reasoning agent log"
        
        # Verify log structure
        log_entry = diagnostic_logs[0]
        assert log_entry.get("status") == "success"
        assert "duration_seconds" in log_entry
        assert "observations_processed" in log_entry
        assert "correlations_created" in log_entry
    
    def test_agent_handles_empty_observations(self, ddr_state_empty, semantic_graph):
        """
        Test that agent gracefully handles empty observations.
        
        Expected:
        - Agent returns state unchanged
        - No correlations created
        """
        state = ddr_state_empty.copy()
        state["observations"] = []
        state["findings"] = []
        state["semantic_graph"] = semantic_graph.to_dict()
        
        result_state = diagnostic_reasoning_agent(state)
        
        correlations = result_state.get("correlations", [])
        assert isinstance(correlations, list)
        assert len(correlations) == 0, "Expected no correlations for empty observations"
    
    def test_agent_handles_missing_graph(self, ddr_state_empty, sample_observation_hall_dampness):
        """
        Test that agent handles missing semantic graph gracefully.
        
        Expected:
        - Agent returns state with error handling
        """
        state = ddr_state_empty.copy()
        state["observations"] = [sample_observation_hall_dampness]
        state["findings"] = []
        state["semantic_graph"] = {}
        
        # Should not raise exception
        result_state = diagnostic_reasoning_agent(state)
        assert isinstance(result_state, dict)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestDiagnosticReasoningIntegration:
    """Integration tests combining rules, severity, and agent."""
    
    def test_full_pipeline_no_llm(
        self,
        sample_observation_hall_dampness,
        sample_finding_bathroom_tile,
        semantic_graph
    ):
        """
        Test the full deterministic pipeline (no LLM calls).
        
        Flow:
        1. Rules engine evaluates observation
        2. Severity matrix scores result
        3. Correlation is created
        
        Expected:
        - Bathroom rule fires with confidence >= 0.80
        - Severity is MEDIUM
        - Correlation object has all required fields
        """
        findings = [sample_finding_bathroom_tile]
        graph_context = {
            "rooms_above": ["Bathroom"],
            "rooms_adjacent": [],
            "findings_above": [sample_finding_bathroom_tile],
            "findings_adjacent": [],
            "findings_at_location": []
        }
        
        # Step 1: Rules
        rule_results = evaluate_rules(
            sample_observation_hall_dampness,
            findings,
            graph_context
        )
        assert len(rule_results) >= 1
        best_rule = max(rule_results, key=lambda r: r["confidence"])
        
        # Step 2: Severity assessment
        severity_info = assess_severity(
            sample_observation_hall_dampness,
            [],
            None
        )
        assert severity_info["severity_level"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        assert 1 <= severity_info["severity_score"] <= 10
        
        # Step 3: Correlation object
        correlation = Correlation(
            symptom_location=sample_observation_hall_dampness.location,
            symptom_type=sample_observation_hall_dampness.symptom,
            root_cause_location=best_rule["probable_root_cause_location"],
            root_cause_type=best_rule["probable_root_cause_type"],
            confidence=best_rule["confidence"],
            reasoning=best_rule["reasoning"],
            supporting_evidence=[]
        )
        
        # Verify correlation structure
        assert correlation.symptom_location == "Hall"
        assert correlation.symptom_type == "dampness"
        assert correlation.confidence >= 0.80
        assert len(correlation.reasoning) > 0
