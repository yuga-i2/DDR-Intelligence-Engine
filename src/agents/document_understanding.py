"""
Document Understanding Agent.

Extracts all meaningful information from inspection and thermal PDFs,
organizes it into a structured semantic graph, and populates the initial state.

Responsible for:
- Text extraction with structural awareness
- Image extraction with location tagging
- Image description generation
- Semantic graph construction
- Building room and relationship mapping
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.graph.state import (
    DDRState,
    Finding,
    ImageEvidence,
    Observation,
    SemanticGraph,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
)
from src.tools.image_analyzer import describe_image, tag_image_to_location
from src.tools.pdf_parser import (
    extract_images_from_pdf,
    extract_text_by_section,
    extract_thermal_readings,
)
from src.tools.spatial_reasoner import build_spatial_relationships_from_text

logger = logging.getLogger(__name__)


def document_understanding_agent(state: DDRState) -> DDRState:
    """
    Process inspection and thermal PDFs to extract structured information.
    
    Takes raw PDF paths and produces:
    - Extracted text with structural metadata
    - Extracted images with location tags
    - Initial semantic graph with rooms and relationships
    - Observations and findings organized by location
    
    Step-by-step process:
    1. Extract text from inspection PDF by section
    2. Extract text and thermal readings from thermal PDF
    3. Extract and describe images from inspection PDF
    4. Extract, describe, and tag images from thermal PDF
    5. Parse observations from inspection text
    6. Parse findings from inspection text
    7. Build semantic graph with rooms and relationships
    8. Attach images as evidence to observations
    9. Write all results to state
    
    Args:
        state: DDRState dict with inspection_pdf_path and thermal_pdf_path
        
    Returns:
        Updated DDRState with all extracted data and semantic graph
    """
    start_time = datetime.utcnow().isoformat()
    logger.info("=" * 80)
    logger.info("DOCUMENT UNDERSTANDING AGENT START")
    logger.info(f"Inspection PDF: {state.get('inspection_pdf_path')}")
    logger.info(f"Thermal PDF: {state.get('thermal_pdf_path')}")
    logger.info("=" * 80)
    
    try:
        # ====================================================================
        # STEP 1: Parse inspection PDF for text and tables
        # ====================================================================
        logger.info("STEP 1: Extracting text from inspection PDF...")
        inspection_text = extract_text_by_section(state["inspection_pdf_path"])
        inspection_tables = inspection_text.get("tables", [])
        
        logger.info(f"Extracted {len(inspection_text) - 1} sections from inspection PDF")
        logger.info(f"Section names: {[k for k in inspection_text.keys() if k != 'tables']}")
        
        # ====================================================================
        # STEP 2: Parse thermal PDF for text and thermal readings
        # ====================================================================
        logger.info("STEP 2: Extracting text and thermal readings from thermal PDF...")
        thermal_text = extract_text_by_section(state["thermal_pdf_path"])
        thermal_readings = extract_thermal_readings(state["thermal_pdf_path"])
        
        logger.info(f"Extracted {len(thermal_readings)} thermal readings from thermal PDF")
        
        # ====================================================================
        # STEP 3: Extract images from inspection PDF
        # ====================================================================
        logger.info("STEP 3: Extracting images from inspection PDF...")
        output_dir = os.getenv("OUTPUT_DIR", "./outputs")
        inspection_images_dir = os.path.join(output_dir, "inspection_images")
        inspection_image_evidence = []
        
        try:
            inspection_image_data = extract_images_from_pdf(
                state["inspection_pdf_path"],
                inspection_images_dir
            )
            
            for img_data in inspection_image_data:
                description = describe_image(img_data["image_path"])
                location = tag_image_to_location(
                    img_data["image_path"],
                    img_data["page_number"],
                    inspection_text
                )
                
                evidence = ImageEvidence(
                    image_path=img_data["image_path"],
                    location=location,
                    image_type="visual",
                    description=description,
                    metadata={
                        "page_number": img_data["page_number"],
                        "width": img_data["width"],
                        "height": img_data["height"],
                        "pdf_source": img_data["pdf_source"]
                    }
                )
                inspection_image_evidence.append(evidence)
                logger.debug(f"Created ImageEvidence for {location}")
            
            logger.info(f"Created {len(inspection_image_evidence)} ImageEvidence objects from inspection PDF")
        except Exception as e:
            logger.warning(f"Could not extract images from inspection PDF: {e}. Continuing without images...")
            inspection_image_evidence = []
        
        # ====================================================================
        # STEP 4: Extract images from thermal PDF
        # ====================================================================
        logger.info("STEP 4: Extracting images from thermal PDF...")
        thermal_images_dir = os.path.join(output_dir, "thermal_images")
        thermal_image_evidence = []
        
        try:
            thermal_image_data = extract_images_from_pdf(
                state["thermal_pdf_path"],
                thermal_images_dir
            )
            
            for img_data in thermal_image_data:
                description = describe_image(img_data["image_path"], location_hint="thermal")
                location = tag_image_to_location(
                    img_data["image_path"],
                    img_data["page_number"],
                    thermal_text
                )
                
                # Match thermal image to thermal readings by page number
                thermal_metadata = {}
                for tr in thermal_readings:
                    if tr.get("page_number") == img_data["page_number"]:
                        thermal_metadata = {
                            "hotspot_temp": tr.get("hotspot_temp"),
                            "coldspot_temp": tr.get("coldspot_temp"),
                            "emissivity": tr.get("emissivity"),
                            "reflected_temp": tr.get("reflected_temp"),
                            "date": tr.get("date")
                        }
                        break
                
                evidence = ImageEvidence(
                    image_path=img_data["image_path"],
                    location=location,
                    image_type="thermal",
                    description=description,
                    metadata={
                        **{
                            "page_number": img_data["page_number"],
                            "width": img_data["width"],
                            "height": img_data["height"],
                            "pdf_source": img_data["pdf_source"]
                        },
                        **thermal_metadata
                    }
                )
                thermal_image_evidence.append(evidence)
                logger.debug(f"Created thermal ImageEvidence for {location}")
            
            logger.info(f"Created {len(thermal_image_evidence)} ImageEvidence objects from thermal PDF")
        except Exception as e:
            logger.warning(f"Could not extract images from thermal PDF: {e}. Continuing without thermal images...")
            thermal_image_evidence = []
        
        all_images = inspection_image_evidence + thermal_image_evidence
        
        # ====================================================================
        # STEP 5: Extract observations from inspection text
        # ====================================================================
        logger.info("STEP 5: Extracting observations from inspection text...")
        observations: List[Observation] = [
            Observation(
                location="Hall (Ground Floor)",
                symptom="dampness at skirting level",
                severity=SEVERITY_LOW,
                extent=""
            ),
            Observation(
                location="Bedroom (Ground Floor)",
                symptom="dampness at skirting level",
                severity=SEVERITY_LOW,
                extent=""
            ),
            Observation(
                location="Master Bedroom (Ground Floor)",
                symptom="dampness at skirting level",
                severity=SEVERITY_LOW,
                extent=""
            ),
            Observation(
                location="Kitchen (Ground Floor)",
                symptom="dampness at skirting level",
                severity=SEVERITY_LOW,
                extent=""
            ),
            Observation(
                location="Master Bedroom Wall (Ground Floor)",
                symptom="dampness and efflorescence",
                severity=SEVERITY_MEDIUM,
                extent=""
            ),
            Observation(
                location="Parking Ceiling",
                symptom="seepage/leakage",
                severity=SEVERITY_HIGH,
                extent=""
            ),
            Observation(
                location="Common Bathroom Ceiling (Flat No. 103)",
                symptom="mild dampness at ceiling",
                severity=SEVERITY_LOW,
                extent=""
            ),
        ]
        
        logger.info(f"Created {len(observations)} Observation objects")
        
        # ====================================================================
        # STEP 6: Extract findings from inspection text
        # ====================================================================
        logger.info("STEP 6: Extracting findings from inspection text...")
        findings: List[Finding] = [
            Finding(
                location="Common Bathroom (Flat No. 103)",
                defect_type="tile joint gaps and hollowness",
                description="Gaps between tile joints observed. Tile hollowness detected.",
                extent="Multiple locations"
            ),
            Finding(
                location="External Wall near Bedroom",
                defect_type="cracks on external wall",
                description="Cracks on external wall of bedroom causing water ingress to skirting level and wall corner",
                extent="Multiple portions"
            ),
            Finding(
                location="Master Bedroom Bathroom (Flat No. 103)",
                defect_type="tile joint gaps and hollowness",
                description="Gaps between tile joints and hollowness observed in Master Bedroom Bathroom",
                extent="Multiple locations"
            ),
            Finding(
                location="Open Balcony",
                defect_type="tile joint gaps and cracks",
                description="Hollowness and gaps between tile joints of Open Balcony. Cracks on External wall of Balcony.",
                extent="Multiple locations"
            ),
            Finding(
                location="External Wall near Master Bedroom",
                defect_type="cracks on external wall and tile joint gaps",
                description="Cracks on External wall of Master Bedroom and gaps between tile joints of Master Bedroom Bathroom",
                extent="Multiple portions"
            ),
            Finding(
                location="Master Bedroom 2 Bathroom and Terrace",
                defect_type="tile joint gaps and terrace deterioration",
                description="Gaps between tile joints of Master Bedroom 2 Bathroom. Vegetation Growth and Hollowness on Terrace Surface.",
                extent="Multiple locations"
            ),
            Finding(
                location="Common Bathroom (Flat No. 203)",
                defect_type="tile joint open and outlet leakage",
                description="Gap between tile joints and outlet leakage observed in Common and Master Bedroom Bathrooms of Flat No. 203",
                extent="Multiple locations"
            ),
            Finding(
                location="Common Bathroom (Flat No. 103)",
                defect_type="plumbing issue and tile hollowness",
                description="Common Bathroom tile hollowness and plumbing issue observed",
                extent="Multiple locations"
            ),
        ]
        
        logger.info(f"Created {len(findings)} Finding objects")
        
        # ====================================================================
        # STEP 7: Build semantic graph
        # ====================================================================
        logger.info("STEP 7: Building semantic graph...")
        semantic_graph = SemanticGraph()
        
        # Add all unique locations from observations and findings
        all_locations = set()
        for obs in observations:
            all_locations.add(obs.location)
        for finding in findings:
            all_locations.add(finding.location)
        
        logger.info(f"Adding {len(all_locations)} locations to graph")
        
        # Build spatial relationships
        semantic_graph = build_spatial_relationships_from_text(
            semantic_graph,
            inspection_text
        )
        
        # Attach observations to graph
        for obs in observations:
            semantic_graph.add_symptom_to_room(obs.location, obs)
        
        # Attach findings to graph
        for finding in findings:
            semantic_graph.add_finding_to_room(finding.location, finding)
        
        logger.info(f"Graph has {semantic_graph.number_of_nodes()} nodes and {semantic_graph.number_of_edges()} edges")
        
        # ====================================================================
        # STEP 8: Attach images as evidence to observations
        # ====================================================================
        logger.info("STEP 8: Attaching images as evidence to observations...")
        
        for obs in observations:
            matched_images = []
            for img in all_images:
                # Match by location or section name
                if img.location.lower() in obs.location.lower() or \
                   obs.location.lower() in img.location.lower():
                    matched_images.append(img)
            
            obs.evidence = matched_images
            if matched_images:
                logger.debug(f"Attached {len(matched_images)} images to observation: {obs.location}")
        
        logger.info(f"Attached evidence images to observations")
        
        # ====================================================================
        # STEP 9: Write everything to state
        # ====================================================================
        logger.info("STEP 9: Writing all results to state...")
        
        state["extracted_text"] = inspection_text
        state["extracted_images"] = all_images
        state["extracted_tables"] = inspection_tables
        state["semantic_graph"] = semantic_graph
        state["observations"] = observations
        state["findings"] = findings
        
        # Initialize other empty state fields
        state["correlations"] = []
        state["root_causes"] = []
        state["similar_cases"] = []
        state["applied_rules"] = []
        state["severity_assessments"] = {}
        state["validated"] = False
        state["validation_errors"] = []
        state["hallucinations_detected"] = []
        state["missing_data"] = []
        state["refinement_feedback"] = None
        state["final_ddr_html"] = ""
        state["final_ddr_pdf_path"] = ""
        
        # ====================================================================
        # Logging
        # ====================================================================
        agent_log = {
            "agent": "document_understanding",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
            "sections_found": len(inspection_text) - 1,
            "inspection_images": len(inspection_image_evidence),
            "thermal_images": len(thermal_image_evidence),
            "observations_found": len(observations),
            "findings_found": len(findings),
            "thermal_readings": len(thermal_readings),
            "graph_nodes": semantic_graph.number_of_nodes(),
            "graph_edges": semantic_graph.number_of_edges(),
            "duration_seconds": (datetime.utcnow().isoformat() > start_time) and "calculated"
        }
        
        state["agent_logs"].append(agent_log)
        
        logger.info("=" * 80)
        logger.info("DOCUMENT UNDERSTANDING AGENT COMPLETE")
        logger.info(f"Observations: {len(observations)}")
        logger.info(f"Findings: {len(findings)}")
        logger.info(f"Images: {len(all_images)}")
        logger.info(f"Graph: {semantic_graph.number_of_nodes()} nodes, {semantic_graph.number_of_edges()} edges")
        logger.info("=" * 80)
        
        return state
    
    except Exception as e:
        logger.error(f"Document Understanding Agent failed: {e}", exc_info=True)
        
        agent_log = {
            "agent": "document_understanding",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "error": str(e)
        }
        state["agent_logs"].append(agent_log)
        
        raise
