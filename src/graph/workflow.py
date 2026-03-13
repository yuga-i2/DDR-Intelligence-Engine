"""
LangGraph workflow for the DDR Intelligence Engine.

Defines the state machine that orchestrates all five agents in a complete pipeline.
Implements the self-correction loop: validator can send diagnostic_reasoning back for refinement
until validation passes or max iterations reached.
"""

import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from src.agents.document_understanding import document_understanding_agent
from src.agents.diagnostic_reasoning import diagnostic_reasoning_agent
from src.agents.knowledge_retrieval import knowledge_retrieval_agent
from src.agents.validator import validator_agent
from src.agents.report_synthesis import report_synthesis_agent
from src.graph.state import DDRState

logger = logging.getLogger(__name__)


def should_refine(state: DDRState) -> Literal["refine", "continue"]:
    """
    Routing function for conditional edge from validator.
    
    Returns "refine" if validation failed and iteration count < 3.
    Returns "continue" otherwise (validation passed or max iterations reached).
    
    Args:
        state: Current DDRState
        
    Returns:
        "refine" to loop back to diagnostic_reasoning, "continue" to proceed to report_synthesis
    """
    validation_passed = state.get("validation_passed", False)
    iteration_count = state.get("iteration_count", 0)
    max_iterations = 3
    
    if not validation_passed and iteration_count < max_iterations:
        logger.info(
            f"Validation failed. Refining (iteration {iteration_count + 1}/{max_iterations})"
        )
        # Increment iteration count for next pass
        state["iteration_count"] = iteration_count + 1
        return "refine"
    
    if not validation_passed and iteration_count >= max_iterations:
        logger.warning(
            f"Validation failed after {max_iterations} iterations. "
            f"Proceeding to report synthesis with warnings."
        )
    
    return "continue"


def compile_workflow():
    """
    Build, compile, and return the LangGraph workflow.
    
    Creates a StateGraph with all five agents registered and wired:
    document_understanding → diagnostic_reasoning → knowledge_retrieval → validator 
    → (conditional) → diagnostic_reasoning (if refine) OR report_synthesis (if continue) → END
    
    The validator's should_refine function determines whether to loop back or proceed.
    
    Returns:
        Compiled LangGraph app ready for invocation
    """
    logger.info("Compiling LangGraph workflow...")
    
    workflow = StateGraph(DDRState)
    
    # Register all five agent nodes
    logger.info("Registering agent nodes...")
    workflow.add_node("document_understanding", document_understanding_agent)
    workflow.add_node("diagnostic_reasoning", diagnostic_reasoning_agent)
    workflow.add_node("knowledge_retrieval", knowledge_retrieval_agent)
    workflow.add_node("validator", validator_agent)
    workflow.add_node("report_synthesis", report_synthesis_agent)
    
    logger.info("All five agent nodes registered")
    
    # Set entry point
    workflow.set_entry_point("document_understanding")
    
    # Wire the main pipeline
    logger.info("Wiring agent edges...")
    workflow.add_edge("document_understanding", "diagnostic_reasoning")
    workflow.add_edge("diagnostic_reasoning", "knowledge_retrieval")
    workflow.add_edge("knowledge_retrieval", "validator")
    
    # Add conditional edge from validator for self-correction loop
    workflow.add_conditional_edges(
        "validator",
        should_refine,
        {
            "refine": "diagnostic_reasoning",
            "continue": "report_synthesis"
        }
    )
    
    # Final edge to END
    workflow.add_edge("report_synthesis", END)
    
    logger.info(
        "Workflow structure: "
        "document_understanding → diagnostic_reasoning → knowledge_retrieval → validator "
        "→ (conditional) → diagnostic_reasoning OR report_synthesis → END"
    )
    
    # Compile the graph
    logger.info("Compiling LangGraph...")
    app = workflow.compile()
    
    logger.info("LangGraph compilation complete")
    return app


# Compile and export the app at module level
app = compile_workflow()
