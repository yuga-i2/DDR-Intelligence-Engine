"""
Diagnostic Reasoning Agent.

Connects observations (symptoms) to their root causes using spatial graph traversal
and LLM-guided causal inference. Produces correlation objects linking symptoms to defects.

Responsible for:
- Spatial relationship traversal from semantic graph
- Causal reasoning between symptoms and potential defects
- Correlation confidence scoring
- Building causal link edges in the semantic graph
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List

from src.graph.memory import SemanticGraph
from src.graph.state import Correlation, DDRState, ImageEvidence
from src.knowledge.rules_engine import evaluate_rules
from src.knowledge.severity_matrix import assess_severity
from src.tools.llm_wrapper import call_llm_with_schema
from src.tools.spatial_reasoner import (
    get_findings_at,
    get_observations_at,
    get_rooms_above,
    get_rooms_adjacent,
)

logger = logging.getLogger(__name__)


def diagnostic_reasoning_agent(state: DDRState) -> DDRState:
    """
    Infer causal relationships between observations and findings.
    
    Uses spatial traversal to identify candidate root causes for each symptom,
    then uses LLM reasoning to score causation likelihood and confidence.
    On retry (iteration_count > 0), incorporates validator feedback.
    
    Step-by-step process:
    1. Check if this is a refinement retry
    2. Load semantic graph and build location context
    3. Apply deterministic rules to each observation
    4. For each observation, use LLM to infer root causes
    5. Merge rule and LLM results
    6. Create Correlation objects
    7. Assess severity for each correlation
    8. Write to state and return
    
    Args:
        state: DDRState with observations, findings, and semantic graph
        
    Returns:
        Updated DDRState with correlations list populated
    """
    logger.info("=" * 80)
    logger.info("DIAGNOSTIC REASONING AGENT START")
    logger.info("=" * 80)
    
    start_time = datetime.now(timezone.utc).isoformat()
    
    try:
        # ====================================================================
        # STEP 1: Check for refinement mode
        # ====================================================================
        refinement_feedback = state.get("refinement_feedback", None)
        is_refinement = refinement_feedback is not None and len(refinement_feedback) > 0
        iteration_count = state.get("iteration_count", 0)
        
        if is_refinement:
            logger.info(f"REFINEMENT MODE ACTIVE: Iteration {iteration_count}, incorporating validator feedback")
        else:
            logger.info("First pass: initial causal reasoning")
        
        # ====================================================================
        # STEP 2: Load graph and build location contexts
        # ====================================================================
        semantic_graph_dict = state.get("semantic_graph")
        if isinstance(semantic_graph_dict, dict):
            semantic_graph = SemanticGraph.from_dict(semantic_graph_dict)
        else:
            semantic_graph = semantic_graph_dict
        
        observations: List = state.get("observations", [])
        findings: List = state.get("findings", [])
        
        logger.info(f"Building location context for {len(observations)} observations")
        
        # Build context for each observation's location
        location_context: Dict[str, Dict] = {}
        for obs in observations:
            location = obs.location
            rooms_above = get_rooms_above(semantic_graph, location)
            rooms_adjacent = get_rooms_adjacent(semantic_graph, location)
            findings_above = []
            findings_adjacent = []
            findings_at_loc = get_findings_at(semantic_graph, location)
            
            # Get findings at rooms above
            for room_above in rooms_above:
                findings_above.extend(get_findings_at(semantic_graph, room_above))
            
            # Get findings at adjacent rooms
            for room_adj in rooms_adjacent:
                findings_adjacent.extend(get_findings_at(semantic_graph, room_adj))
            
            location_context[location] = {
                "rooms_above": rooms_above,
                "rooms_adjacent": rooms_adjacent,
                "findings_above": findings_above,
                "findings_adjacent": findings_adjacent,
                "findings_at_location": findings_at_loc,
            }
            
            logger.debug(
                f"  {location}: {len(rooms_above)} above, {len(rooms_adjacent)} adjacent, "
                f"{len(findings_above)} findings above, {len(findings_at_loc)} at location"
            )
        
        # ====================================================================
        # STEP 3 & 4: Apply rules and LLM reasoning to each observation
        # ====================================================================
        correlations_list: List[Correlation] = []
        
        for obs in observations:
            logger.info(f"Processing observation: {obs.location} - {obs.symptom}")
            
            graph_context = location_context.get(obs.location, {})
            
            # Apply deterministic rules
            rule_results = evaluate_rules(obs, findings, graph_context)
            logger.info(f"  {len(rule_results)} rules matched")
            
            # Build LLM prompt for causal reasoning
            rooms_above = graph_context.get("rooms_above", [])
            rooms_adjacent = graph_context.get("rooms_adjacent", [])
            findings_above = graph_context.get("findings_above", [])
            findings_at_loc = graph_context.get("findings_at_location", [])
            
            findings_above_summary = "\n".join(
                [f"  - {f.location}: {f.defect_type}" for f in findings_above]
            ) or "None"
            
            findings_at_summary = "\n".join(
                [f"  - {f.location}: {f.defect_type}" for f in findings_at_loc]
            ) or "None"
            
            # Build thermal summary
            thermal_summary = _build_thermal_summary(state, obs.location)
            
            # Build rule results summary
            rule_results_summary = "\n".join(
                [f"  - {r['rule_name']}: confidence={r['confidence']}, cause={r['probable_root_cause_type']}"
                 for r in rule_results]
            ) or "No deterministic rules matched"
            
            # Build refinement section if needed
            refinement_section = ""
            if is_refinement:
                refinement_section = f"""
PREVIOUS ANALYSIS WAS REJECTED. VALIDATOR FEEDBACK:
{refinement_feedback}

You must address each piece of feedback explicitly in your revised analysis. 
Do not repeat previous errors.
"""
            
            system_prompt = (
                "You are a senior building diagnostics engineer with 20 years of experience in waterproofing, "
                "structural assessment, and moisture pathology. You reason from physical evidence to root causes. "
                "You do not speculate beyond the evidence provided. You are precise, professional, and conservative."
            )
            
            user_prompt = f"""You are analyzing a building inspection case. Here is the evidence:

AFFECTED LOCATION: {obs.location}
SYMPTOM OBSERVED: {obs.symptom}
SEVERITY RECORDED: {obs.severity}

ROOMS SPATIALLY ABOVE THIS LOCATION: {', '.join(rooms_above) if rooms_above else 'None'}
ROOMS ADJACENT TO THIS LOCATION: {', '.join(rooms_adjacent) if rooms_adjacent else 'None'}

DEFECTS FOUND IN ROOMS ABOVE: 
{findings_above_summary}

DEFECTS FOUND AT THIS LOCATION: 
{findings_at_summary}

THERMAL EVIDENCE: {thermal_summary}

DETERMINISTIC RULE RESULTS:
{rule_results_summary}

{refinement_section}

Based on all evidence above, identify:
1. The single most probable root cause
2. The causal chain (how the root cause leads to the symptom)
3. Your confidence level (0.0 to 1.0)
4. Whether deterministic rules confirm or contradict your finding
"""
            
            schema_example = {
                "root_cause_location": "Common Bathroom (Ground Floor)",
                "root_cause_type": "Tile joint gaps causing waterproofing failure",
                "causal_chain": "Water seeps through gaps in tile grout, accumulates above ceiling, migrates downward",
                "confidence": 0.87,
                "rule_confirmation": "Deterministic 'Bathroom above dampness' rule confirms. Confidence boosted from 0.82 to 0.87."
            }
            
            try:
                llm_response = call_llm_with_schema(system_prompt, user_prompt, schema_example)
                llm_result = json.loads(llm_response)
                logger.info(f"  LLM result: confidence={llm_result.get('confidence', 0)}")
            except Exception as e:
                logger.error(f"  LLM reasoning failed: {e}", exc_info=True)
                # FALLBACK: use best deterministic rule result if available
                if rule_results and len(rule_results) > 0:
                    best_rule = max(rule_results, key=lambda r: r.get("confidence", 0))
                    llm_result = {
                        "root_cause_location": best_rule.get("probable_root_cause_location", obs.location),
                        "root_cause_type": best_rule.get("probable_root_cause_type", "Unknown"),
                        "causal_chain": best_rule.get("reasoning", "Determined by deterministic rules engine (LLM unavailable)."),
                        "confidence": best_rule.get("confidence", 0.75),
                        "rule_confirmation": f"LLM call failed. Using deterministic rule '{best_rule.get('rule_name', 'unknown')}' as fallback."
                    }
                    logger.warning(f"  LLM failed — using rule fallback for {obs.location}: confidence={llm_result['confidence']}")
                else:
                    # No rules matched either — create a minimal correlation from observation data
                    llm_result = {
                        "root_cause_location": obs.location,
                        "root_cause_type": "Further investigation required",
                        "causal_chain": "Automated reasoning was unavailable. Manual review recommended.",
                        "confidence": 0.50,
                        "rule_confirmation": "LLM unavailable and no deterministic rules matched."
                    }
                    logger.warning(f"  LLM failed and no rules matched for {obs.location} — creating minimal correlation")
            
            # ================================================================
            # STEP 5: Merge rule and LLM results
            # ================================================================
            merged_confidence = llm_result.get("confidence", 0.5)
            merged_root_cause_location = llm_result.get("root_cause_location", "Unknown")
            merged_root_cause_type = llm_result.get("root_cause_type", "Unknown")
            merged_reasoning = llm_result.get("causal_chain", "")
            
            # Check if high-confidence rule exists
            high_confidence_rule = None
            for rule in rule_results:
                if rule["confidence"] >= 0.85:
                    high_confidence_rule = rule
                    break
            
            if high_confidence_rule:
                # Rule has high confidence
                if merged_root_cause_type.lower() in high_confidence_rule["probable_root_cause_type"].lower():
                    # LLM agrees with rule
                    merged_confidence = min(0.98, high_confidence_rule["confidence"] + 0.05)
                    merged_reasoning = f"{high_confidence_rule['reasoning']} [Rule/LLM agreement]"
                else:
                    # LLM contradicts rule
                    logger.warning(
                        f"  LLM contradicts high-confidence rule: "
                        f"Rule={high_confidence_rule['probable_root_cause_type']}, "
                        f"LLM={merged_root_cause_type}"
                    )
                    merged_confidence = high_confidence_rule["confidence"] - 0.10
                    merged_root_cause_location = high_confidence_rule["probable_root_cause_location"]
                    merged_root_cause_type = high_confidence_rule["probable_root_cause_type"]
                    merged_reasoning = f"{high_confidence_rule['reasoning']} [Rule takes precedence over LLM]"
            
            # ================================================================
            # STEP 6: Create Correlation object
            # ================================================================
            supporting_evidence = []
            for img in state.get("extracted_images", []):
                if obs.location.lower() in img.location.lower() or img.location.lower() in obs.location.lower():
                    supporting_evidence.append(img.image_path)
            
            correlation = Correlation(
                symptom_location=obs.location,
                symptom_type=obs.symptom,
                root_cause_location=merged_root_cause_location,
                root_cause_type=merged_root_cause_type,
                confidence=merged_confidence,
                reasoning=merged_reasoning,
                supporting_evidence=supporting_evidence
            )
            
            correlations_list.append(correlation)
            logger.info(f"  Created correlation: confidence={merged_confidence}")
        
        # ====================================================================
        # STEP 7: Assess severity for each correlation
        # ====================================================================
        severity_assessments: Dict[str, Dict] = {}
        
        for i, corr in enumerate(correlations_list):
            # Find corresponding observation
            obs = next((o for o in observations if o.location == corr.symptom_location), None)
            if obs:
                severity_info = assess_severity(obs, correlations_list)
                severity_assessments[corr.symptom_location] = severity_info
                logger.info(f"  {corr.symptom_location}: {severity_info['severity_level']}")
        
        # ====================================================================
        # STEP 8: Write to state
        # ====================================================================
        state["correlations"] = [c.model_dump() if hasattr(c, 'model_dump') else c for c in correlations_list]
        state["severity_assessments"] = severity_assessments
        
        # Log completion
        end_time = datetime.now(timezone.utc).isoformat()
        duration = (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()
        
        agent_log = {
            "agent": "diagnostic_reasoning",
            "status": "success",
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "observations_processed": len(observations),
            "correlations_created": len(correlations_list),
            "iteration": iteration_count,
            "is_refinement": is_refinement
        }
        
        state.setdefault("agent_logs", []).append(agent_log)
        
        logger.info("=" * 80)
        logger.info(f"DIAGNOSTIC REASONING AGENT COMPLETE - {len(correlations_list)} correlations")
        logger.info("=" * 80)
        
        return state
    
    except Exception as e:
        logger.error(f"Diagnostic reasoning agent error: {e}", exc_info=True)
        state["correlations"] = []
        return state


def _build_thermal_summary(state: DDRState, location: str) -> str:
    """
    Build a thermal evidence summary for a location.
    
    Args:
        state: DDRState with extracted_images
        location: Location to find thermal images for
        
    Returns:
        Formatted string summarizing thermal evidence or "None"
    """
    extracted_images = state.get("extracted_images", [])
    
    thermal_matches = []
    for img in extracted_images:
        if isinstance(img, dict):
            # Dict form
            if img.get("image_type") == "thermal":
                if location.lower() in img.get("location", "").lower():
                    metadata = img.get("metadata", {})
                    hotspot = metadata.get("hotspot_temp")
                    coldspot = metadata.get("coldspot_temp")
                    if hotspot and coldspot:
                        delta = hotspot - coldspot
                        activity = "low" if delta < 2 else "moderate" if delta < 4 else "high"
                        thermal_matches.append(
                            f"Hotspot {hotspot}°C vs coldspot {coldspot}°C (delta {delta}°C) — {activity} moisture activity"
                        )
        else:
            # ImageEvidence object
            if img.image_type == "thermal":
                if location.lower() in img.location.lower():
                    metadata = img.metadata or {}
                    hotspot = metadata.get("hotspot_temp")
                    coldspot = metadata.get("coldspot_temp")
                    if hotspot is not None and coldspot is not None:
                        delta = hotspot - coldspot
                        activity = "low" if delta < 2 else "moderate" if delta < 4 else "high"
                        thermal_matches.append(
                            f"Hotspot {hotspot}°C vs coldspot {coldspot}°C (delta {delta}°C) — {activity} moisture activity"
                        )
    
    if thermal_matches:
        return "\n".join([f"  - {m}" for m in thermal_matches])
    else:
        return "None"
