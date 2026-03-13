"""
Severity Assessment Matrix — Building Defect Severity Determination

Deterministic lookup and assessment for building defect severity.
Assigns severity levels (LOW, MEDIUM, HIGH, CRITICAL) based on symptom type,
location, and extent, along with urgency guidance for remediation.

The matrix takes precedence over LLM-assigned severity when conflicts occur.
This ensures consistency and prevents underestimation of serious defects.
"""

import logging
from typing import Any, Dict

from src.graph.state import Correlation, Observation

logger = logging.getLogger(__name__)


def assess_severity(
    observation: Observation,
    correlations: list,
    checklist_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Assess severity of a defect based on type, location, and extent.
    
    Applies determination rules in order (first match wins).
    
    Args:
        observation: The Observation to assess
        correlations: List of Correlation objects (may include this observation)
        checklist_data: Optional additional context (unused for now)
        
    Returns:
        Dict with keys:
        - severity_level (str): "LOW", "MEDIUM", "HIGH", or "CRITICAL"
        - severity_score (int): 1-10 numeric score
        - urgency (str): Human-readable urgency guidance
        - reasoning (str): Explanation of the assessment
    """
    
    symptom_lower = observation.symptom.lower()
    location_lower = observation.location.lower()
    severity_base = observation.severity.lower() if observation.severity else "low"
    
    # Find correlations matching this observation
    matching_correlations = [
        c for c in correlations
        if c.symptom_location.lower() == observation.location.lower()
    ]
    
    # ========================================================================
    # CRITICAL (score 9-10): Structural or imminent safety risk
    # ========================================================================
    
    # Check for structural keywords in observation or correlations
    if any(word in symptom_lower for word in ["structural", "reinforcement", "concrete spall"]):
        return {
            "severity_level": "CRITICAL",
            "severity_score": 10,
            "urgency": "Immediate structural engineer assessment required. Do not delay.",
            "reasoning": "Symptom indicates potential structural compromise. Requires immediate expert evaluation."
        }
    
    # Check correlation root causes for structural mention
    for corr in matching_correlations:
        root_cause_lower = (corr.root_cause_type or "").lower()
        if any(word in root_cause_lower for word in ["structural", "reinforcement", "spalling", "rebar"]):
            return {
                "severity_level": "CRITICAL",
                "severity_score": 9,
                "urgency": "Immediate structural engineer assessment required. Do not delay.",
                "reasoning": f"Root cause identified as structural issue: {corr.root_cause_type}"
            }
    
    # ========================================================================
    # HIGH (score 7-8): Active leakage or significant water damage
    # ========================================================================
    
    # Parking ceiling seepage
    if "parking" in location_lower and any(
        word in symptom_lower for word in ["seepage", "leakage"]
    ):
        return {
            "severity_level": "HIGH",
            "severity_score": 8,
            "urgency": "Repair within 2-4 weeks. Active leakage can damage parked vehicles and structural slab.",
            "reasoning": "Parking ceiling seepage indicates active water ingress affecting multiple vehicles and structural integrity."
        }
    
    # Terrace waterproofing failure
    if "terrace" in location_lower or "terrace" in symptom_lower:
        return {
            "severity_level": "HIGH",
            "severity_score": 7,
            "urgency": "Schedule treatment before next monsoon season. Delay will worsen structural damage.",
            "reasoning": "Terrace waterproofing failure leads to progressive structural degradation during rain seasons."
        }
    
    # Cross-flat leakage
    for corr in matching_correlations:
        if "203" in (corr.root_cause_location or "") or "flat" in (corr.root_cause_location or "").lower():
            if any(word in symptom_lower for word in ["leakage", "dampness", "ceiling"]):
                return {
                    "severity_level": "HIGH",
                    "severity_score": 8,
                    "urgency": "Requires coordination with upper flat owner. Legal and structural implications if unaddressed.",
                    "reasoning": "Cross-flat leakage affects multiple occupants and creates legal/contractual obligations."
                }
    
    # ========================================================================
    # MEDIUM (score 4-6): Significant but manageable issues
    # ========================================================================
    
    # External wall cracks (non-structural)
    for corr in matching_correlations:
        root_cause_lower = (corr.root_cause_type or "").lower()
        if "crack" in root_cause_lower and "external" in root_cause_lower:
            return {
                "severity_level": "MEDIUM",
                "severity_score": 6,
                "urgency": "Repair within 1-2 months. Current hairline cracks will worsen with monsoon.",
                "reasoning": "External wall cracks allow water infiltration that accelerates during monsoon season."
            }
    
    # Bathroom tile joints causing skirting dampness
    for corr in matching_correlations:
        root_cause_lower = (corr.root_cause_type or "").lower()
        if "tile" in root_cause_lower and "joint" in root_cause_lower and "bathroom" in root_cause_lower:
            if any(word in symptom_lower for word in ["dampness", "skirting"]):
                return {
                    "severity_level": "MEDIUM",
                    "severity_score": 5,
                    "urgency": "Plan grouting treatment within 2-3 months. Risk of escalation to plaster and structural damage.",
                    "reasoning": "Tile joint gaps allow slow water migration that will worsen plaster and eventually affect structure."
                }
    
    # Efflorescence on walls
    if "efflorescence" in symptom_lower:
        return {
            "severity_level": "MEDIUM",
            "severity_score": 4,
            "urgency": "Cosmetic and waterproofing treatment recommended within 3-6 months.",
            "reasoning": "Efflorescence indicates moisture ingress that requires treatment but is not immediately critical."
        }
    
    # ========================================================================
    # LOW (score 1-3): Minor or manageable issues
    # ========================================================================
    
    if severity_base == "low":
        return {
            "severity_level": "LOW",
            "severity_score": 2,
            "urgency": "Monitor and plan preventive treatment in next maintenance cycle.",
            "reasoning": "Low-severity observation requires monitoring but no immediate action."
        }
    
    # ========================================================================
    # DEFAULT: MEDIUM (score 4)
    # ========================================================================
    
    return {
        "severity_level": "MEDIUM",
        "severity_score": 4,
        "urgency": "Schedule inspection and treatment planning within next 1-3 months.",
        "reasoning": "Defect requires professional assessment and remediation within reasonable timeframe."
    }
