"""
Report Synthesis Agent.

Transforms validated state into a professional client-ready DDR PDF.
Renders Jinja2 HTML template with findings, images, and recommendations.
Converts HTML to PDF using WeasyPrint.

Responsible for:
- Grouping findings by area
- Client-friendly summarization
- Image placement and annotation
- Recommendation generation
- Missing data and validation warning sections
- HTML template rendering
- PDF conversion and file output
"""

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Any

from jinja2 import Environment, FileSystemLoader

from src.graph.state import DDRState, Correlation
from src.tools.llm_wrapper import call_llm

logger = logging.getLogger(__name__)


def _extract_report_metadata(extracted_text: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract report metadata from extracted text.

    Looks for report metadata fields like property address, inspection date, etc.
    Returns sensible defaults if fields are not found.

    Args:
        extracted_text: Structured text dict from document_understanding

    Returns:
        Dict with keys: property_address, inspection_date, inspected_by, report_id,
                       prepared_by, generated_date
    """
    metadata = {}

    # Extract property address
    property_address = "Not Available"
    if extracted_text:
        # Try to find in GENERAL INFORMATION or similar sections
        for section_key, section_content in extracted_text.items():
            if isinstance(section_content, str):
                if "Customer Full Address" in section_content or "Site Address" in section_content:
                    lines = section_content.split("\n")
                    for i, line in enumerate(lines):
                        if "Address" in line and i + 1 < len(lines):
                            property_address = lines[i + 1].strip()
                            break
            elif isinstance(section_content, dict):
                if "property_address" in section_content:
                    property_address = section_content["property_address"]

    metadata["property_address"] = property_address

    # Extract inspection date
    inspection_date = "Not Available"
    if extracted_text:
        for section_key, section_content in extracted_text.items():
            if isinstance(section_content, str):
                if "Date of Inspection" in section_content:
                    lines = section_content.split("\n")
                    for i, line in enumerate(lines):
                        if "Date of Inspection" in line:
                            # Try to extract the date from the line or next line
                            parts = line.split(":")
                            if len(parts) > 1:
                                inspection_date = parts[1].strip()
                            elif i + 1 < len(lines):
                                inspection_date = lines[i + 1].strip()
                            break
            elif isinstance(section_content, dict):
                if "inspection_date" in section_content:
                    inspection_date = section_content["inspection_date"]

    metadata["inspection_date"] = inspection_date

    # Extract inspected by
    inspected_by = "Not Available"
    if extracted_text:
        for section_key, section_content in extracted_text.items():
            if isinstance(section_content, str):
                if "Inspected By" in section_content:
                    lines = section_content.split("\n")
                    for i, line in enumerate(lines):
                        if "Inspected By" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                inspected_by = parts[1].strip()
                            elif i + 1 < len(lines):
                                inspected_by = lines[i + 1].strip()
                            break
            elif isinstance(section_content, dict):
                if "inspected_by" in section_content:
                    inspected_by = section_content["inspected_by"]

    metadata["inspected_by"] = inspected_by

    # Extract or generate report ID
    report_id = "Not Available"
    if extracted_text:
        for section_key, section_content in extracted_text.items():
            if isinstance(section_content, str):
                if "Case No" in section_content or "Report ID" in section_content:
                    lines = section_content.split("\n")
                    for i, line in enumerate(lines):
                        if "Case No" in line or "Report ID" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                report_id = parts[1].strip()
                            elif i + 1 < len(lines):
                                report_id = lines[i + 1].strip()
                            break
            elif isinstance(section_content, dict):
                if "report_id" in section_content or "case_no" in section_content:
                    report_id = section_content.get("report_id") or section_content.get("case_no")

    if report_id == "Not Available":
        report_id = f"DDR-{datetime.now().strftime('%Y%m%d%H%M')}"

    metadata["report_id"] = report_id
    metadata["prepared_by"] = "DDR Intelligence Engine (UrbanRoof)"
    metadata["generated_date"] = datetime.now().strftime("%d %B %Y, %H:%M")

    return metadata


def report_synthesis_agent(state: DDRState) -> DDRState:
    """
    Generate the final Defect Diagnostic Report PDF.

    Synthesizes all validated findings into a professional report by:
    - Grouping observations and correlations by area
    - Generating client-friendly diagnostic summaries
    - Creating prioritized, actionable recommendations
    - Placing evidence images in appropriate sections
    - Including Missing Data and Validation Warnings sections if needed
    - Rendering Jinja2 template with all data
    - Converting HTML to PDF and saving to outputs directory

    Args:
        state: Validated DDRState with all reasoning complete

    Returns:
        Updated DDRState with final_ddr_html and final_ddr_pdf_path populated
    """
    logger.info("=" * 80)
    logger.info("REPORT SYNTHESIS AGENT START")
    logger.info("=" * 80)

    start_time = datetime.now(timezone.utc).isoformat()
    
    # Initialize output paths to ensure they're always defined
    html_output_path = None
    pdf_output_path = None
    pdf_success = False
    pdf_bytes = 0

    try:
        # ====================================================================
        # STEP 1: Extract report metadata
        # ====================================================================
        logger.info("Extracting report metadata...")
        extracted_text = state.get("extracted_text", {})
        report_metadata = _extract_report_metadata(extracted_text)
        logger.info(f"  Property: {report_metadata['property_address']}")
        logger.info(f"  Report ID: {report_metadata['report_id']}")

        # ====================================================================
        # STEP 2: Generate property summary using LLM
        # ====================================================================
        logger.info("Generating executive summary via LLM...")

        observations = state.get("observations", [])
        findings = state.get("findings", [])
        severity_assessments = state.get("severity_assessments", {})

        # Collect unique defect types
        defect_types = set()
        for finding in findings[:5]:  # First 5 findings
            defect_types.add(finding.defect_type)

        # Find highest severity
        highest_severity = "low"
        for sev in severity_assessments.values():
            if isinstance(sev, dict):
                sev_level = sev.get("severity_level", "low")
            else:
                sev_level = sev

            if sev_level == "critical":
                highest_severity = "critical"
                break
            elif sev_level == "high" and highest_severity != "critical":
                highest_severity = "high"
            elif sev_level == "medium" and highest_severity not in ["critical", "high"]:
                highest_severity = "medium"

        # Count total treatments
        recommended_actions = state.get("recommended_actions", {})
        total_treatments = sum(len(v) for v in recommended_actions.values())

        system_prompt = (
            "You are a professional technical report writer for a building diagnostics company. "
            "You write clear, factual, client-friendly executive summaries. "
            "You do not invent facts. You summarize only what is provided."
        )

        user_prompt = (
            f"Write a professional executive summary paragraph (3-4 sentences) for a building inspection report.\n\n"
            f"Property: {report_metadata['property_address']}\n"
            f"Inspection date: {report_metadata['inspection_date']}\n"
            f"Number of impacted areas: {len(observations)}\n"
            f"Defect types found: {', '.join(list(defect_types)[:5]) if defect_types else 'Various'}\n"
            f"Highest severity: {highest_severity.upper()}\n"
            f"Number of recommended treatments: {total_treatments}\n\n"
            f"The summary should: state the property and inspection date, briefly describe the nature and extent "
            f"of defects found, mention the highest severity issue, and state that detailed findings and "
            f"recommendations follow. Do not use bullet points. Write as one professional paragraph."
        )

        property_summary = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expect_json=False
        )

        logger.info("  Summary generated successfully")

        # ====================================================================
        # STEP 3: Build area_observations list with images
        # ====================================================================
        logger.info("Building area observations with images...")

        extracted_images = state.get("extracted_images", [])
        area_observations = []

        for obs in observations:
            # Find severity assessment for this location
            severity_info = severity_assessments.get(
                obs.location,
                {"severity_level": obs.severity, "severity_score": 5, "urgency": "N/A"}
            )

            if isinstance(severity_info, dict):
                severity_level = severity_info.get("severity_level", obs.severity).upper()
                severity_score = severity_info.get("severity_score", 5)
                urgency = severity_info.get("urgency", "N/A")
            else:
                severity_level = obs.severity.upper()
                severity_score = 5
                urgency = "N/A"

            # Find images for this location
            visual_images = []
            thermal_images = []

            for img_evidence in extracted_images:
                if img_evidence.location.lower() == obs.location.lower():
                    try:
                        # Read and encode image to base64
                        if os.path.exists(img_evidence.image_path):
                            with open(img_evidence.image_path, "rb") as f:
                                img_data = base64.b64encode(f.read()).decode("utf-8")

                                img_obj = {
                                    "data": img_data,
                                    "caption": img_evidence.description
                                }

                                if img_evidence.image_type.lower() == "thermal":
                                    thermal_images.append(img_obj)
                                else:
                                    visual_images.append(img_obj)
                        else:
                            logger.warning(f"Image file not found: {img_evidence.image_path}")
                    except Exception as e:
                        logger.error(f"Error reading image {img_evidence.image_path}: {e}")

            # Build thermal evidence text (from severity assessment or observation evidence)
            thermal_evidence = ""
            if severity_info.get("thermal_delta"):
                thermal_evidence = f"Temperature differential: {severity_info.get('thermal_delta')}"

            area_obs = {
                "location": obs.location,
                "symptom": obs.symptom,
                "severity_level": severity_level,
                "severity_score": severity_score,
                "urgency": urgency,
                "thermal_evidence": thermal_evidence,
                "visual_images": visual_images,
                "thermal_images": thermal_images
            }

            area_observations.append(area_obs)

        logger.info(f"  Built {len(area_observations)} area observations")

        # ====================================================================
        # STEP 4: Build correlations list for template
        # ====================================================================
        logger.info("Preparing correlations for template...")

        correlations_raw = state.get("correlations", [])
        correlations = []
        for corr in correlations_raw:
            if isinstance(corr, dict):
                correlations.append(Correlation(**corr))
            else:
                correlations.append(corr)
        correlations_list = []

        for corr in correlations:
            # Filter to only include correlations matching observation locations
            obs_locations = {obs.location for obs in observations}
            if corr.symptom_location in obs_locations:
                corr_dict = {
                    "symptom_location": corr.symptom_location,
                    "symptom_type": corr.symptom_type,
                    "root_cause_location": corr.root_cause_location,
                    "root_cause_type": corr.root_cause_type,
                    "confidence": corr.confidence,
                    "reasoning": corr.reasoning,
                    "causal_chain": corr.reasoning,  # Use reasoning as causal chain
                    "supporting_evidence": corr.supporting_evidence
                }
                correlations_list.append(corr_dict)

        logger.info(f"  Filtered to {len(correlations_list)} valid correlations")

        # ====================================================================
        # STEP 5: Sort severity assessments by level
        # ====================================================================
        logger.info("Sorting severity assessments...")

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        severity_assessments_sorted = {}

        # Create sortable list
        sev_list = []
        for location, sev_info in severity_assessments.items():
            if isinstance(sev_info, dict):
                sev_level = sev_info.get("severity_level", "LOW").upper()
                sev_list.append((location, sev_info, severity_order.get(sev_level, 99)))
            else:
                sev_list.append((location, sev_info, 99))

        # Sort by severity order
        sev_list.sort(key=lambda x: x[2])

        # Build sorted dict
        for location, sev_info, _ in sev_list:
            severity_assessments_sorted[location] = sev_info

        logger.info("  Severity assessments sorted")

        # ====================================================================
        # STEP 6: Build missing_information list
        # ====================================================================
        logger.info("Building missing information list...")

        missing_information = []

        # Check for observations without images
        for obs in observations:
            has_images = any(
                img.location.lower() == obs.location.lower()
                for img in extracted_images
            )
            if not has_images:
                missing_information.append(
                    f"Visual evidence for {obs.location}: Image Not Available"
                )

        # Check for low-confidence correlations
        for corr in correlations:
            if corr.confidence < 0.50:
                missing_information.append(
                    f"Causal evidence for {corr.symptom_location}: Low confidence "
                    f"({corr.confidence * 100:.0f}%) — further investigation recommended"
                )

        logger.info(f"  Identified {len(missing_information)} missing data items")

        # ====================================================================
        # STEP 7: Build additional_notes list
        # ====================================================================
        logger.info("Building additional notes...")

        additional_notes = [
            "Inspection conducted using IR Thermography (Bosch GTC 400 C Professional), "
            "moisture meter, tapping hammer, and visual inspection by UrbanRoof technical team."
        ]

        # Add validation warnings
        report_warnings = state.get("report_warnings", [])

        # Add iteration note if needed
        iteration_count = state.get("iteration_count", 0)
        if iteration_count > 1:
            additional_notes.append(
                f"Note: This report required {iteration_count} diagnostic reasoning iterations "
                f"to meet quality standards."
            )

        # Add unvalidated warning if applicable
        if not state.get("validation_passed", True) and report_warnings:
            additional_notes.insert(
                0,
                "⚠ UNVALIDATED REPORT: This report was generated after reaching the maximum "
                "correction iterations. Review validation errors before using for client delivery."
            )

        logger.info(f"  Built {len(additional_notes)} additional notes")

        # ====================================================================
        # STEP 8: Render Jinja2 template
        # ====================================================================
        logger.info("Rendering Jinja2 template...")

        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False
        )

        template = env.get_template("ddr_report.html")

        # Prepare context
        context = {
            "report_metadata": report_metadata,
            "property_summary": property_summary,
            "area_observations": area_observations,
            "correlations": correlations_list,
            "severity_assessments_sorted": severity_assessments_sorted,
            "recommended_actions": recommended_actions,
            "additional_notes": additional_notes,
            "report_warnings": report_warnings,
            "missing_information": missing_information
        }

        rendered_html = template.render(context)
        logger.info("  Template rendered successfully")

        # ====================================================================
        # STEP 9: Generate PDF with WeasyPrint (or HTML fallback)
        # ====================================================================
        logger.info("Generating PDF with WeasyPrint...")

        output_dir = os.getenv("OUTPUT_DIR", "./outputs")
        output_dir = os.path.abspath(output_dir)  # Convert to absolute path
        os.makedirs(output_dir, exist_ok=True)

        # Always save HTML first (useful for web viewing and as fallback)
        html_filename = f"DDR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html_output_path = os.path.join(output_dir, html_filename)
        
        try:
            with open(html_output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_html)
            logger.info(f"  HTML report saved successfully: {html_filename}")
        except Exception as e:
            logger.error(f"Error saving HTML report: {e}")

        # Try to generate PDF using WeasyPrint
        pdf_filename = f"DDR_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_output_path = os.path.join(output_dir, pdf_filename)

        try:
            from weasyprint import HTML
            
            # Create PDF from HTML string
            HTML(string=rendered_html).write_pdf(pdf_output_path)

            # Check file size
            file_size_kb = os.path.getsize(pdf_output_path) / 1024
            logger.info(f"  PDF generated successfully")
            logger.info(f"  File: {pdf_output_path}")
            logger.info(f"  Size: {file_size_kb:.1f} KB")
            
            pdf_success = True
            pdf_bytes = file_size_kb

        except ImportError as e:
            logger.warning(
                f"WeasyPrint not available (missing system dependencies like GTK+): {e}"
            )
            logger.warning("HTML report will be used as fallback for viewing the report")
            pdf_success = False
            pdf_bytes = 0

        except Exception as e:
            logger.warning(f"WeasyPrint PDF generation failed: {e}")
            logger.warning("HTML report will be used as fallback for viewing the report")
            pdf_success = False
            pdf_bytes = 0

        # ====================================================================
        # STEP 10 & 11: Write to state and log
        # ====================================================================
        end_time = datetime.now(timezone.utc).isoformat()
        duration = (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()

        agent_log = {
            "agent": "report_synthesis",
            "status": "success",
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration,
            "areas_documented": len(area_observations),
            "correlations_documented": len(correlations_list),
            "html_path": html_output_path,
            "pdf_success": pdf_success,
            "pdf_size_kb": pdf_bytes if pdf_success else 0,
            "pdf_path": pdf_output_path if pdf_success else None
        }

        state.setdefault("agent_logs", []).append(agent_log)

        state["final_ddr_html"] = rendered_html
        state["final_ddr_html_path"] = html_output_path
        if pdf_success:
            state["final_ddr_pdf_path"] = pdf_output_path

        logger.info("=" * 80)
        logger.info("REPORT SYNTHESIS AGENT COMPLETE")
        if pdf_success:
            logger.info(f"PDF: {pdf_output_path}")
        logger.info(f"HTML: {html_output_path}")
        logger.info("=" * 80)

        return state

    except Exception as e:
        logger.error(f"Report synthesis agent error: {e}", exc_info=True)
        state["final_ddr_html"] = ""
        state["final_ddr_html_path"] = html_output_path  # Set even if None
        state["final_ddr_pdf_path"] = pdf_output_path if pdf_success else None
        raise

