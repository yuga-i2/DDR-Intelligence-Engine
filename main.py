"""
DDR Intelligence Engine — Main Entry Point

Command-line interface for invoking the complete DDR generation workflow.
Validates inputs, loads configuration, and orchestrates the LangGraph state machine.

Usage:
    python main.py --inspection data/inspection_report.pdf --thermal data/thermal_report.pdf
"""

import argparse
import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
    },
    "handlers": {
        "default": {
            "level": LOG_LEVEL,
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["default"],
    },
}
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)


def validate_file_path(file_path: str, file_type: str) -> Path:
    """
    Validate that a file path exists and is a regular file.
    
    Args:
        file_path: Path to the file
        file_type: Description of file type (e.g., "inspection PDF")
        
    Returns:
        Path object if valid
        
    Raises:
        SystemExit: If file does not exist or is not a file
    """
    path = Path(file_path)
    
    if not path.exists():
        logger.error(f"{file_type} not found: {file_path}")
        print(f"Error: {file_type} not found at {file_path}", file=sys.stderr)
        sys.exit(1)
    
    if not path.is_file():
        logger.error(f"{file_type} is not a file: {file_path}")
        print(f"Error: {file_type} is not a regular file: {file_path}", file=sys.stderr)
        sys.exit(1)
    
    logger.info(f"{file_type} validated: {path.absolute()}")
    return path


def serialize_state_to_json(state: dict) -> dict:
    """
    Serialize DDRState to JSON-compatible format.
    
    Handles non-JSON-serializable types:
    - SemanticGraph: calls to_dict()
    - Pydantic models: calls model_dump()
    - Lists of Pydantic models: calls model_dump() on each item
    
    Args:
        state: DDRState dict
        
    Returns:
        JSON-serializable dict
    """
    serialized = {}
    
    for key, value in state.items():
        try:
            if key == "semantic_graph" and value is not None:
                # SemanticGraph has a to_dict() method
                serialized[key] = value.to_dict()
            elif key in ["observations", "findings", "extracted_images"]:
                # Lists of Pydantic models
                if value:
                    serialized[key] = [item.model_dump() for item in value]
                else:
                    serialized[key] = []
            elif hasattr(value, "model_dump"):
                # Single Pydantic model
                serialized[key] = value.model_dump()
            else:
                # Standard JSON-serializable types
                serialized[key] = value
        except Exception as e:
            logger.warning(f"Could not serialize state field {key}: {e}")
            serialized[key] = str(value)
    
    return serialized


def main():
    """
    Main entry point for the DDR Intelligence Engine.
    
    Parses command-line arguments, validates file paths, and invokes the
    compiled LangGraph workflow.
    """
    parser = argparse.ArgumentParser(
        description="DDR Intelligence Engine - Generate Defect Diagnostic Reports from inspection PDFs"
    )
    parser.add_argument(
        "--inspection",
        required=True,
        help="Path to the inspection report PDF"
    )
    parser.add_argument(
        "--thermal",
        required=True,
        help="Path to the thermal imaging PDF"
    )
    
    args = parser.parse_args()
    
    try:
        # Validate input file paths
        inspection_path = validate_file_path(args.inspection, "Inspection PDF")
        thermal_path = validate_file_path(args.thermal, "Thermal PDF")
        
        logger.info("=" * 80)
        logger.info("DDR Intelligence Engine Starting")
        logger.info(f"Inspection PDF: {inspection_path}")
        logger.info(f"Thermal PDF: {thermal_path}")
        logger.info("=" * 80)
        
        # Import the compiled workflow
        try:
            from src.graph.workflow import app
        except ImportError as e:
            logger.error(
                "Failed to import workflow: src/graph/workflow.py has not been implemented yet. "
                "The LangGraph app must be defined and compiled in src/graph/workflow.py.",
                exc_info=True
            )
            print(
                "Error: Workflow not implemented. "
                "Please implement src/graph/workflow.py with the LangGraph state machine.",
                file=sys.stderr
            )
            sys.exit(1)
        
        # Build initial state
        initial_state = {
            "inspection_pdf_path": str(inspection_path),
            "thermal_pdf_path": str(thermal_path),
            "iteration_count": 0,
            "agent_logs": [],
            # All other state fields will be initialized to empty/None by agents
        }
        
        logger.info("Invoking LangGraph workflow...")
        
        # Execute the workflow
        result = app.invoke(initial_state)
        
        # ====================================================================
        # DUMP STATE TO JSON FILE FOR INSPECTION
        # ====================================================================
        output_dir = os.getenv("OUTPUT_DIR", "./outputs")
        os.makedirs(output_dir, exist_ok=True)
        
        debug_json_path = os.path.join(output_dir, "extraction_debug.json")
        
        logger.info(f"Serializing state to JSON: {debug_json_path}")
        
        serialized_state = serialize_state_to_json(result)
        
        with open(debug_json_path, "w") as f:
            json.dump(serialized_state, f, indent=2, default=str)
        
        logger.info(f"Wrote debug JSON to {debug_json_path}")
        
        # ====================================================================
        # CHECK FOR FINAL OUTPUT
        # ====================================================================
        logger.info(f"Final state keys: {list(result.keys())}")
        logger.info(f"  final_ddr_pdf_path: {result.get('final_ddr_pdf_path', 'NOT SET')}")
        logger.info(f"  final_ddr_html_path: {result.get('final_ddr_html_path', 'NOT SET')}")
        logger.info(f"  final_ddr_html: {type(result.get('final_ddr_html', 'NOT SET'))}")
        
        final_pdf_path = result.get("final_ddr_pdf_path")
        final_html_path = result.get("final_ddr_html_path")
        
        # Prefer PDF, but fall back to HTML if PDF unavailable
        report_path = None
        report_type = None
        
        if final_pdf_path and os.path.exists(final_pdf_path):
            # Verify the PDF actually exists and has reasonable size
            file_size_kb = os.path.getsize(final_pdf_path) / 1024
            
            if file_size_kb >= 10:
                report_path = final_pdf_path
                report_type = "PDF"
                logger.info("=" * 80)
                logger.info("DDR Report generated successfully (PDF)")
                logger.info(f"Report Path: {final_pdf_path}")
                logger.info(f"File Size: {file_size_kb:.1f} KB")
                logger.info("=" * 80)
                print(final_pdf_path)
                sys.exit(0)
            else:
                logger.error(
                    f"PDF was created but is suspiciously small ({file_size_kb:.1f} KB). "
                    f"This may indicate a PDF generation failure."
                )
        
        # Try HTML fallback
        if not report_path and final_html_path and os.path.exists(final_html_path):
            file_size_kb = os.path.getsize(final_html_path) / 1024
            report_path = final_html_path
            report_type = "HTML"
            logger.warning("PDF unavailable. Using HTML report instead.")
            logger.info("=" * 80)
            logger.info("DDR Report generated successfully (HTML)")
            logger.info(f"Report Path: {final_html_path}")
            logger.info(f"File Size: {file_size_kb:.1f} KB")
            logger.info("=" * 80)
            print(final_html_path)
            sys.exit(0)
        
        # Neither PDF nor HTML available
        logger.error(
            "Workflow completed but no valid report was generated. "
            f"PDF path: {final_pdf_path}, HTML path: {final_html_path}"
        )
        print(
            "Error: No valid report file was generated. Check logs for report synthesis errors.",
            file=sys.stderr
        )
        
        # Still print debug file for inspection
        print(debug_json_path)
        sys.exit(1)
    
    except Exception as e:
        logger.error(f"Unhandled exception during workflow execution: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
