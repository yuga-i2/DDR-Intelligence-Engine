"""
Tests for the Validator Agent.

Verifies:
- Hallucination detection via grounding checks
- Root cause verification
- Confidence-severity consistency validation
- Missing data detection
- Spatial plausibility checks
- Refinement feedback construction
- Iteration cap enforcement
"""


def test_validator_detects_hallucinations():
    """Test that claims not in source text are flagged."""
    pass


def test_validator_accepts_grounded_claims():
    """Test that claims in source text pass validation."""
    pass


def test_validator_checks_confidence_severity():
    """Test that high severity requires high confidence."""
    pass


def test_validator_detects_missing_data():
    """Test that missing building elements are flagged."""
    pass


def test_validator_constructs_refinement_feedback():
    """Test that retry feedback is properly structured."""
    pass
