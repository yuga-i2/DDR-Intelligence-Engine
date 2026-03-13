"""
Knowledge Retrieval Agent.

Enhances correlations using deterministic expert rules and vector similarity search.
Retrieves similar cases from the domain knowledge base and applies built-in rules for
severity assessment.

Responsible for:
- Firing expert rules against correlations
- Generating treatment recommendations
- Vector similarity search for past cases
- Building domain knowledge context for the validator and report
"""

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

from src.graph.memory import VectorStoreWrapper
from src.graph.state import DDRState, Finding, Observation
from src.knowledge.rules_engine import get_treatment_recommendations

logger = logging.getLogger(__name__)


def knowledge_retrieval_agent(state: DDRState) -> DDRState:
    """
    Apply expert knowledge and retrieve similar past cases.
    
    Enhances existing correlations by:
    - Generating treatment recommendations from expert rules
    - Searching ChromaDB for similar past cases (if available)
    - Stores case summaryin vector store for future retrieval
    
    Args:
        state: DDRState with findings, observations, and correlations
        
    Returns:
        Updated DDRState with recommended_actions and similar_cases
    """
    logger.info("=" * 80)
    logger.info("KNOWLEDGE RETRIEVAL AGENT START")
    logger.info("=" * 80)
    
    start_time = datetime.now(timezone.utc).isoformat()
    
    try:
        # ====================================================================
        # STEP 1: Initialize vector store (with fallback for cold start)
        # ====================================================================
        vector_store = None
        chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/vector_store")
        
        try:
            vector_store = VectorStoreWrapper(chroma_persist_dir)
            logger.info("Initialized ChromaDB vector store")
        except Exception as e:
            logger.warning(
                f"ChromaDB initialization failed (cold start?): {e}. "
                "Knowledge retrieval will continue without vector similarity search."
            )
            vector_store = None
        
        # ====================================================================
        # STEP 2: Generate treatment recommendations from rules
        # ====================================================================
        findings: List[Finding] = state.get("findings", [])
        severity_assessments: Dict[str, Dict[str, Any]] = state.get("severity_assessments", {})
        recommended_actions: Dict[str, List[Dict[str, Any]]] = {}
        
        total_treatments = 0
        
        for finding in findings:
            # Determine severity level for this finding
            severity_level = "MEDIUM"  # default
            
            # Look up severity assessment by location match
            for obs_location, severity_info in severity_assessments.items():
                if finding.location.lower() in obs_location.lower() or obs_location.lower() in finding.location.lower():
                    severity_level = severity_info.get("severity_level", "MEDIUM")
                    break
            
            # Get treatment recommendations
            treatments = get_treatment_recommendations(finding, severity_level)
            if treatments:
                if finding.location not in recommended_actions:
                    recommended_actions[finding.location] = []
                recommended_actions[finding.location].extend(treatments)
                total_treatments += len(treatments)
        
        # ====================================================================
        # STEP 3: Deduplicate recommendations by treatment_name within location
        # ====================================================================
        for location in recommended_actions:
            seen_treatments = set()
            deduplicated = []
            
            for treatment in recommended_actions[location]:
                treatment_name = treatment.get("treatment_name", "")
                if treatment_name not in seen_treatments:
                    deduplicated.append(treatment)
                    seen_treatments.add(treatment_name)
            
            recommended_actions[location] = deduplicated
            logger.debug(f"Deduped {location}: {len(recommended_actions[location])} unique treatments")
        
        state["recommended_actions"] = recommended_actions
        
        # ====================================================================
        # STEP 4: Vector store similarity search (only if available)
        # ====================================================================
        similar_cases = []
        
        if vector_store is not None:
            observations: List[Observation] = state.get("observations", [])
            if observations:
                try:
                    similar_cases = vector_store.search_similar(observations, k=3)
                    logger.info(f"Retrieved {len(similar_cases)} similar past cases from vector store")
                except Exception as e:
                    logger.warning(f"Vector store search failed: {e}")
                    similar_cases = []
        else:
            logger.info("Vector store not available - skipping similarity search")
        
        state["similar_cases"] = similar_cases
        
        # ====================================================================
        # STEP 5: Store current case in vector store for future use
        # ====================================================================
        if vector_store is not None:
            try:
                # Build a case summary from current state
                observations_summary = "\n".join(
                    [f"- {obs.location}: {obs.symptom}" for obs in state.get("observations", [])]
                )
                findings_summary = "\n".join(
                    [f"- {finding.location}: {finding.defect_type}" for finding in state.get("findings", [])]
                )
                
                case_dict = {
                    "case_id": f"ddr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    "summary": f"Observations:\n{observations_summary}\n\nFindings:\n{findings_summary}",
                    "property": state.get("inspection_pdf_path", "Unknown"),
                    "date": start_time,
                    "observations_count": len(state.get("observations", [])),
                    "findings_count": len(state.get("findings", [])),
                    "correlations_count": len(state.get("correlations", []))
                }
                
                vector_store.add_case(case_dict)
                logger.info(f"Stored current case {case_dict['case_id']} in vector store")
            except Exception as e:
                logger.warning(f"Failed to store case in vector store: {e}")
        
        # ====================================================================
        # STEP 6: Write to state and return
        # ====================================================================
        end_time = datetime.now(timezone.utc).isoformat()
        duration = (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()
        
        agent_log = {
            "agent": "knowledge_retrieval",
            "status": "success",
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "findings_processed": len(findings),
            "treatments_generated": total_treatments,
            "treatments_unique": sum(len(v) for v in recommended_actions.values()),
            "locations_with_treatments": len(recommended_actions),
            "similar_cases_retrieved": len(similar_cases),
            "vector_store_available": vector_store is not None
        }
        
        state.setdefault("agent_logs", []).append(agent_log)
        
        logger.info("=" * 80)
        logger.info(f"KNOWLEDGE RETRIEVAL AGENT COMPLETE - {len(recommended_actions)} locations with treatments")
        logger.info("=" * 80)
        
        return state
    
    except Exception as e:
        logger.error(f"Knowledge retrieval agent error: {e}", exc_info=True)
        state["recommended_actions"] = {}
        state["similar_cases"] = []
        return state
