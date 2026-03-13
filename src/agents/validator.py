"""
Validator Agent (Self-Critic).

Validates every factual claim against the extracted source documents.
Detects hallucinations, logical inconsistencies, and missing data.
Drives self-correction loop by returning structured feedback when retries are needed.

Responsible for:
- Hallucination detection via grounding checks
- Root cause verification against extracted findings
- Confidence-severity consistency validation
- Coverage validation across observations
- Spatial plausibility verification
- Refinement feedback construction for retries
"""

import logging
import os
from datetime import datetime, timezone
from typing import List

from src.graph.memory import SemanticGraph
from src.graph.state import Correlation, DDRState

logger = logging.getLogger(__name__)

# Constants
MAX_CORRECTION_ITERATIONS = int(os.getenv("MAX_CORRECTION_ITERATIONS", "3"))


def validator_agent(state: DDRState) -> DDRState:
    """
    Validate all correlations and claims against source documents.
    
    Performs five validation checks:
    1. Hallucination detection: root causes grounded in observations/findings
    2. Root cause grounding: each cause supported by at least one finding
    3. Confidence-severity consistency: high severity requires confidence >= 0.60
    4. Coverage check: at least 75% of observations have correlations
    5. Spatial plausibility: root cause location is upstream/external from symptom
    
    If validation fails and iteration_count < MAX_CORRECTION_ITERATIONS,
    constructs refinement_feedback for diagnostic_reasoning retry.
    
    If validation fails and iteration_count >= MAX_CORRECTION_ITERATIONS,
    marks unresolved errors for report warnings.
    
    Args:
        state: DDRState with observations, findings, correlations, severity_assessments
        
    Returns:
        Updated DDRState with validation results
    """
    logger.info("=" * 80)
    logger.info("VALIDATOR AGENT START")
    logger.info("=" * 80)
    
    start_time = datetime.now(timezone.utc).isoformat()
    
    try:
        # Extract data
        observations = state.get("observations", [])
        findings = state.get("findings", [])
        correlations_raw = state.get("correlations", [])
        severity_assessments = state.get("severity_assessments", {})
        semantic_graph: SemanticGraph = state.get("semantic_graph")
        iteration_count = state.get("iteration_count", 0)
        
        # Convert dict correlations back to Correlation objects if needed
        correlations = []
        for corr in correlations_raw:
            if isinstance(corr, dict):
                correlations.append(Correlation(**corr))
            else:
                correlations.append(corr)
        
        validation_failures = []
        
        logger.info(f"Validating {len(correlations)} correlations against {len(findings)} findings")
        
        # ====================================================================
        # CHECK 1 — Hallucination Detection
        # ====================================================================
        logger.info("CHECK 1: Hallucination detection...")
        
        observation_locations = {obs.location for obs in observations}
        finding_locations = {f.location for f in findings}
        graph_nodes = set()
        
        if semantic_graph:
            graph_nodes = set(semantic_graph.graph.nodes())
        
        all_locations = observation_locations | finding_locations | graph_nodes
        
        for corr in correlations:
            if corr.root_cause_location not in all_locations:
                failure = (
                    f"Correlation for '{corr.symptom_location}' claims root cause at "
                    f"'{corr.root_cause_location}' which does not appear in any extracted "
                    f"observation or finding. Remove or correct this correlation."
                )
                validation_failures.append(failure)
                logger.warning(f"  Hallucination: {failure}")
        
        # ====================================================================
        # CHECK 2 — Root Cause Grounding
        # ====================================================================
        logger.info("CHECK 2: Root cause grounding...")
        
        for corr in correlations:
            # Check if there's a finding at the root cause location
            matching_findings = [
                f for f in findings 
                if f.location.lower() == corr.root_cause_location.lower()
            ]
            
            if not matching_findings:
                # Also check if root cause is adjacent to any finding
                nearby_findings = [
                    f for f in findings
                    if corr.root_cause_location.lower() in f.location.lower() or
                       f.location.lower() in corr.root_cause_location.lower()
                ]
                
                if not nearby_findings:
                    failure = (
                        f"Correlation for '{corr.symptom_location}' lacks a supporting Finding "
                        f"at root cause location '{corr.root_cause_location}'. "
                        f"Every root cause must be supported by at least one observed finding."
                    )
                    validation_failures.append(failure)
                    logger.warning(f"  Missing root cause: {failure}")
        
        # ====================================================================
        # CHECK 3 — Confidence-Severity Consistency
        # ====================================================================
        logger.info("CHECK 3: Confidence-severity consistency...")
        
        for corr in correlations:
            # Find severity assessment for this correlation's symptom location
            severity_info = severity_assessments.get(corr.symptom_location)
            
            if severity_info:
                severity_level = severity_info.get("severity_level", "MEDIUM")
                
                if severity_level in ("HIGH", "CRITICAL") and corr.confidence < 0.60:
                    failure = (
                        f"Location '{corr.symptom_location}' is assessed as {severity_level} "
                        f"severity but correlation confidence is only {corr.confidence:.2f}. "
                        f"High severity findings require confidence >= 0.60. Review causal reasoning."
                    )
                    validation_failures.append(failure)
                    logger.warning(f"  Low confidence for high severity: {failure}")
        
        # ====================================================================
        # CHECK 4 — Coverage Check (Missing Observations)
        # ====================================================================
        logger.info("CHECK 4: Coverage check...")
        
        if len(observations) > 0:
            coverage = len(correlations) / len(observations)
            
            if coverage < 0.75:
                unmatched_obs = [
                    obs.location for obs in observations
                    if not any(c.symptom_location == obs.location for c in correlations)
                ]
                
                failure = (
                    f"Only {len(correlations)} correlations were generated for "
                    f"{len(observations)} observations (coverage: {coverage:.0%}). "
                    f"Minimum required coverage is 75%. "
                    f"The following observations have no correlation: {unmatched_obs}"
                )
                validation_failures.append(failure)
                logger.warning(f"  Low coverage: {failure}")
        
        # ====================================================================
        # CHECK 5 — Spatial Plausibility
        # ====================================================================
        logger.info("CHECK 5: Spatial plausibility...")
        
        for corr in correlations:
            # Check if root cause location == symptom location
            if corr.root_cause_location.lower() == corr.symptom_location.lower():
                # This is only acceptable for external wall or plumbing
                is_acceptable = any(
                    word in corr.root_cause_type.lower()
                    for word in ["external wall", "plumbing", "pipe"]
                )
                
                if not is_acceptable:
                    failure = (
                        f"Correlation for '{corr.symptom_location}' has identical "
                        f"symptom and root cause location. Root cause should be in a "
                        f"spatially upstream location (above, adjacent, or external)."
                    )
                    validation_failures.append(failure)
                    logger.warning(f"  Implausible spatial relationship: {failure}")
        
        # ====================================================================
        # DETERMINE VALIDATION OUTCOME
        # ====================================================================
        
        if not validation_failures:
            # VALIDATION PASSED
            logger.info("Validation PASSED — all 5 checks passed")
            state["validation_passed"] = True
            state["validation_errors"] = []
            state["refinement_feedback"] = None
        
        elif iteration_count < MAX_CORRECTION_ITERATIONS:
            # VALIDATION FAILED — construct feedback for retry
            logger.info(f"Validation FAILED — {len(validation_failures)} issues found. Routing for refinement (iteration {iteration_count + 1})")
            
            state["validation_passed"] = False
            state["validation_errors"] = validation_failures
            
            # Build refinement feedback
            refinement_feedback = (
                "VALIDATION FAILED. The following issues must be addressed in your revised analysis:\n\n"
                + "\n\n".join(validation_failures)
            )
            state["refinement_feedback"] = refinement_feedback
            
            # Increment iteration counter
            state["iteration_count"] = iteration_count + 1
        
        else:
            # VALIDATION FAILED after max iterations — proceed with warnings
            logger.warning(
                f"Validation FAILED after {MAX_CORRECTION_ITERATIONS} iterations. "
                "Proceeding to report synthesis with warnings."
            )
            
            state["validation_passed"] = False
            state["validation_errors"] = validation_failures
            
            # Add warnings for final report
            warning_text = (
                f"WARNING: This report was generated after {iteration_count} correction attempts. "
                f"The following validation issues were NOT fully resolved: "
                f"{'; '.join([f[:100] + '...' if len(f) > 100 else f for f in validation_failures])}"
            )
            state["report_warnings"] = state.get("report_warnings", []) + [warning_text]
            state["refinement_feedback"] = None  # No further retries
        
        # ====================================================================
        # WRITE AGENT LOG
        # ====================================================================
        end_time = datetime.now(timezone.utc).isoformat()
        duration = (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()
        
        agent_log = {
            "agent": "validator",
            "status": "success",
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "correlations_checked": len(correlations),
            "validation_failures": len(validation_failures),
            "validation_passed": state.get("validation_passed", False),
            "iteration": iteration_count
        }
        
        state.setdefault("agent_logs", []).append(agent_log)
        
        logger.info("=" * 80)
        logger.info("VALIDATOR AGENT COMPLETE")
        logger.info("=" * 80)
        
        return state
    
    except Exception as e:
        logger.error(f"Validator agent error: {e}", exc_info=True)
        state["validation_passed"] = False
        state["validation_errors"] = [f"Validator error: {str(e)}"]
        return state
