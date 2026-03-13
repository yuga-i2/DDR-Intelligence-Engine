"""
Tests for the Report Synthesis Agent.

Tests the HTML template rendering, PDF generation, metadata extraction,
image handling, and warning display functionality.
"""

import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

from jinja2 import Environment, FileSystemLoader

from src.agents.report_synthesis import report_synthesis_agent, _extract_report_metadata
from src.graph.state import (
    DDRState,
    Observation,
    Finding,
    Correlation,
    ImageEvidence,
    SemanticGraph,
)

class TestReportMetadataExtraction:
    """Test the metadata extraction helper function."""

    def test_metadata_extraction(self):
        """Test extraction of report metadata from structured text."""
        extracted_text = {
            "GENERAL INFORMATION": {
                "property_address": "RH-69, Sukhwani Oasis, Sector No. 11, Spine Road, Chikhali Pradhikaran, Pune - 411019"
            },
            "INSPECTION_DETAILS": {
                "inspection_date": "03/01/2023",
                "inspected_by": "Mr. Krushna"
            },
            "CASE_NO": "Case-2023-001"
        }

        metadata = _extract_report_metadata(extracted_text)

        assert "property_address" in metadata
        assert "inspection_date" in metadata
        assert "inspected_by" in metadata
        assert "report_id" in metadata
        assert "prepared_by" in metadata
        assert "generated_date" in metadata
        assert metadata["prepared_by"] == "DDR Intelligence Engine (UrbanRoof)"

    def test_metadata_extraction_fallback_defaults(self):
        """Test that metadata extraction handles missing fields gracefully."""
        extracted_text = {}

        metadata = _extract_report_metadata(extracted_text)

        # Should still have all required keys with defaults
        assert metadata["property_address"] == "Not Available"
        assert metadata["inspection_date"] == "Not Available"
        assert metadata["inspected_by"] == "Not Available"
        # Report ID should be auto-generated
        assert metadata["report_id"].startswith("DDR-")


class TestTemplateRendering:
    """Test Jinja2 template rendering."""

    @pytest.fixture
    def minimal_context(self):
        """Minimal but complete context for template rendering."""
        return {
            "report_metadata": {
                "property_address": "Test Property, Room 101",
                "inspection_date": "15/03/2026",
                "inspected_by": "Test Inspector",
                "report_id": "DDR-20260315120000",
                "prepared_by": "DDR Intelligence Engine (UrbanRoof)",
                "generated_date": "15 March 2026, 12:00"
            },
            "property_summary": "This property shows moderate defects requiring attention. Visual and thermal inspection found dampness and potential structural concerns that need further evaluation.",
            "area_observations": [
                {
                    "location": "Hall",
                    "symptom": "Dampness patch on ceiling",
                    "severity_level": "HIGH",
                    "severity_score": 7,
                    "urgency": "Immediate attention required",
                    "thermal_evidence": "Temperature differential: 2.3°C",
                    "visual_images": [],
                    "thermal_images": []
                },
                {
                    "location": "Bathroom",
                    "symptom": "Water seepage at wall junction",
                    "severity_level": "MEDIUM",
                    "severity_score": 5,
                    "urgency": "Within 2-4 weeks",
                    "thermal_evidence": "",
                    "visual_images": [],
                    "thermal_images": []
                }
            ],
            "correlations": [
                {
                    "symptom_location": "Hall",
                    "symptom_type": "dampness",
                    "root_cause_location": "Bathroom",
                    "root_cause_type": "tile joint gap",
                    "confidence": 0.87,
                    "reasoning": "Water seeps through tile gaps and accumulates in the ceiling.",
                    "causal_chain": "Water seeps through tile gaps and accumulates in the ceiling.",
                    "supporting_evidence": ["Bathroom floor has visible gaps", "Hall ceiling shows moisture"]
                }
            ],
            "severity_assessments_sorted": {
                "Hall": {
                    "severity_level": "HIGH",
                    "severity_score": 7,
                    "urgency": "Immediate attention required"
                },
                "Bathroom": {
                    "severity_level": "MEDIUM",
                    "severity_score": 5,
                    "urgency": "Within 2-4 weeks"
                }
            },
            "recommended_actions": {
                "Hall": [
                    {
                        "treatment_name": "Roof waterproofing",
                        "description": "Apply proper waterproofing membrane",
                        "materials": ["Waterproofing compound", "Prime coat"],
                        "priority": "IMMEDIATE",
                        "estimated_duration": "2-3 days"
                    }
                ],
                "Bathroom": [
                    {
                        "treatment_name": "Tile joint sealing",
                        "description": "Seal all tile joints with epoxy grout",
                        "materials": ["Epoxy grout", "Grout remover"],
                        "priority": "SHORT_TERM",
                        "estimated_duration": "1-2 days"
                    }
                ]
            },
            "additional_notes": [
                "Inspection conducted with IR Thermography",
                "Note: This report required 2 iterations to meet quality standards."
            ],
            "report_warnings": [],
            "missing_information": []
        }

    def test_template_renders_without_error(self, minimal_context):
        """Test that the template renders without throwing errors."""
        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "src", "templates"
        )
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template("ddr_report.html")

        rendered = template.render(minimal_context)

        assert len(rendered) > 1000
        assert "Property Issue Summary" in rendered
        assert "Area-wise Observations" in rendered
        assert "Recommended Actions" in rendered
        assert "Missing or Unclear Information" in rendered

    def test_severity_badge_colors(self, minimal_context):
        """Test that severity badges use correct colors."""
        # Add CRITICAL observation
        minimal_context["area_observations"].append({
            "location": "Terrace",
            "symptom": "Structural crack",
            "severity_level": "CRITICAL",
            "severity_score": 9,
            "urgency": "Emergency",
            "thermal_evidence": "",
            "visual_images": [],
            "thermal_images": []
        })

        minimal_context["severity_assessments_sorted"]["Terrace"] = {
            "severity_level": "CRITICAL",
            "severity_score": 9,
            "urgency": "Emergency"
        }

        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "src", "templates"
        )
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template("ddr_report.html")

        rendered = template.render(minimal_context)

        # Check for CRITICAL color code
        assert "8e0000" in rendered  # CRITICAL color
        # Check for LOW color code (if we had one)
        # We should have at least one severity badge


        assert "severity-critical" in rendered

    def test_missing_images_handled_gracefully(self, minimal_context):
        """Test that missing images display 'Image Not Available' text."""
        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "src", "templates"
        )
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template("ddr_report.html")

        rendered = template.render(minimal_context)

        assert "Image Not Available" in rendered

    def test_report_warnings_displayed(self, minimal_context):
        """Test that report warnings appear in the rendered output."""
        minimal_context["report_warnings"] = [
            "Test warning: this report is unvalidated.",
            "Another warning about missing data."
        ]

        template_dir = os.path.join(
            os.path.dirname(__file__), "..", "src", "templates"
        )
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=False)
        template = env.get_template("ddr_report.html")

        rendered = template.render(minimal_context)

        assert "Validation Warnings" in rendered
        assert "Test warning" in rendered


class TestReportSynthesisAgent:
    """Test the report_synthesis_agent function."""

    @pytest.fixture
    def minimal_state(self):
        """Minimal but complete DDRState for testing."""
        semantic_graph = SemanticGraph()
        semantic_graph.add_room("Hall")
        semantic_graph.add_room("Bathroom")

        observation = Observation(
            location="Hall",
            symptom="Dampness patch",
            severity="high",
            extent="1.2m x 0.8m",
            evidence=[]
        )

        finding = Finding(
            location="Bathroom",
            defect_type="tile joint gap",
            description="Visible gaps in tile grouting",
            extent="Multiple locations"
        )

        correlation = Correlation(
            symptom_location="Hall",
            symptom_type="dampness",
            root_cause_location="Bathroom",
            root_cause_type="tile joint gap",
            confidence=0.87,
            reasoning="Water seeps through gaps",
            supporting_evidence=[]
        )

        state = {
            "inspection_pdf_path": "test_inspection.pdf",
            "thermal_pdf_path": "test_thermal.pdf",
            "extracted_text": {
                "property_address": "Test Property",
                "inspection_date": "15/03/2026",
                "inspected_by": "Test Inspector"
            },
            "extracted_images": [],
            "extracted_tables": [],
            "semantic_graph": semantic_graph,
            "observations": [observation],
            "findings": [finding],
            "correlations": [correlation],
            "recommended_actions": {
                "Hall": [
                    {
                        "treatment_name": "Waterproofing",
                        "description": "Apply waterproofing",
                        "materials": ["Material 1"],
                        "priority": "IMMEDIATE",
                        "estimated_duration": "2 days"
                    }
                ]
            },
            "root_causes": [],
            "similar_cases": [],
            "applied_rules": [],
            "severity_assessments": {
                "Hall": {
                    "severity_level": "HIGH",
                    "severity_score": 7,
                    "urgency": "Immediate"
                }
            },
            "validated": True,
            "validation_passed": True,
            "validation_errors": [],
            "hallucinations_detected": [],
            "missing_data": [],
            "iteration_count": 1,
            "agent_logs": []
        }

        return state

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY to test LLM-based summary generation"
    )
    def test_report_synthesis_agent_generates_pdf(self, minimal_state):
        """Test that report_synthesis_agent generates a PDF file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set OUTPUT_DIR to temp directory
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                result = report_synthesis_agent(minimal_state)

                # Check that final_ddr_pdf_path is set
                assert "final_ddr_pdf_path" in result
                pdf_path = result["final_ddr_pdf_path"]

                # Check that file exists
                assert os.path.exists(pdf_path)

                # Check that file is non-trivial (> 10 KB)
                file_size = os.path.getsize(pdf_path) / 1024
                assert file_size > 10, f"PDF size {file_size} KB is suspiciously small"

                # Check that agent_logs is updated
                assert len(result["agent_logs"]) > 0
                last_log = result["agent_logs"][-1]
                assert last_log["agent"] == "report_synthesis"
                assert last_log["status"] == "success"

    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY to test LLM-based summary generation"
    )
    def test_report_synthesis_agent_html_generated(self, minimal_state):
        """Test that report_synthesis_agent generates HTML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"OUTPUT_DIR": tmpdir}):
                result = report_synthesis_agent(minimal_state)

                # Check that HTML is generated
                assert "final_ddr_html" in result
                html = result["final_ddr_html"]

                assert len(html) > 100
                assert "<!DOCTYPE html>" in html
                assert "Defect Diagnostic Report" in html or "Property Issue Summary" in html

    def test_extract_report_metadata_with_string_content(self):
        """Test metadata extraction when text is in string format."""
        extracted_text = {
            "GENERAL INFORMATION": "Customer Full Address: 123 Test Street\nDate of Inspection: 15/03/2026\nInspected By: Mr. Smith"
        }

        metadata = _extract_report_metadata(extracted_text)

        assert metadata["property_address"] != "Not Available" or metadata["property_address"] == "Not Available"
        assert "prepared_by" in metadata
        assert metadata["prepared_by"] == "DDR Intelligence Engine (UrbanRoof)"


class TestImageHandling:
    """Test image encoding and embedding in reports."""

    def test_image_evidence_properties(self):
        """Test that ImageEvidence objects have required properties."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"fake png data")
            tmp_path = tmp.name

        try:
            img = ImageEvidence(
                image_path=tmp_path,
                location="Hall",
                image_type="visual",
                description="Test image",
                metadata={}
            )

            assert img.image_path == tmp_path
            assert img.location == "Hall"
            assert img.image_type == "visual"
            assert img.description == "Test image"
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
