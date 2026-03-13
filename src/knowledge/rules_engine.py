"""
Rules Engine — Deterministic Building Diagnostics Rules

This module contains expert IF-THEN rules for building diagnostics.
No LLM calls here — all rules are deterministic based on structured logic.
Rules evaluate observations and findings to produce confidence scores and root cause hypotheses.
"""

import logging
from typing import Any, Dict, List

from src.graph.state import (
    Finding,
    Observation,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
)

logger = logging.getLogger(__name__)


def evaluate_rules(
    observation: Observation,
    findings: List[Finding],
    graph_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Evaluate deterministic building domain rules against an observation.
    
    Each matching rule appends a result dict with:
    - rule_name (str): Name of the rule that matched
    - confidence (float): Confidence level 0.0-1.0
    - probable_root_cause_location (str): Location of the suspected root cause
    - probable_root_cause_type (str): Type of defect causing the issue
    - reasoning (str): Explanation of why this rule matched
    
    Args:
        observation: The Observation to evaluate
        findings: All findings in the building for reference
        graph_context: Dict with keys:
            - rooms_above (List[str]): Rooms spatially above this observation
            - rooms_adjacent (List[str]): Rooms adjacent to this observation
            - findings_above (List[Finding]): Findings in rooms above
            - findings_adjacent (List[Finding]): Findings in adjacent rooms
            - findings_at_location (List[Finding]): Findings at this location
    
    Returns:
        List of dicts, one per matching rule (may be empty if no rules match)
    """
    results = []
    
    # Extract context
    rooms_above = graph_context.get("rooms_above", [])
    rooms_adjacent = graph_context.get("rooms_adjacent", [])
    findings_above = graph_context.get("findings_above", [])
    findings_adjacent = graph_context.get("findings_adjacent", [])
    findings_at_location = graph_context.get("findings_at_location", [])
    
    symptom_lower = observation.symptom.lower()
    location_lower = observation.location.lower()
    
    # ========================================================================
    # RULE 1 — Bathroom above dampness
    # ========================================================================
    if any(word in symptom_lower for word in ["dampness", "skirting", "seepage"]):
        for room_above in rooms_above:
            room_upper = room_above.upper()
            if any(word in room_upper for word in ["BATHROOM", "WC", "TOILET"]):
                # Check if there are tile/waterproofing findings above
                for finding in findings_above:
                    defect_lower = finding.defect_type.lower() if finding.defect_type else ""
                    if any(
                        word in defect_lower
                        for word in ["tile", "joint", "gap", "hollowness", "grouting"]
                    ):
                        results.append(
                            {
                                "rule_name": "Bathroom above dampness",
                                "confidence": 0.90,
                                "probable_root_cause_location": room_above,
                                "probable_root_cause_type": "Tile joint gaps and waterproofing failure in bathroom above",
                                "reasoning": (
                                    "Water from bathroom above is migrating downward through failed tile joints "
                                    "via capillary action, causing dampness at skirting level on the floor below."
                                ),
                            }
                        )
                        break
    
    # ========================================================================
    # RULE 2 — External wall crack causing internal dampness
    # ========================================================================
    if any(word in symptom_lower for word in ["dampness", "efflorescence", "moisture"]):
        # Check for cracks in findings at this location or adjacent
        for finding in findings_at_location + findings_adjacent:
            defect_lower = finding.defect_type.lower() if finding.defect_type else ""
            if any(word in defect_lower for word in ["crack", "external wall", "wall crack"]):
                results.append(
                    {
                        "rule_name": "External wall crack causing internal dampness",
                        "confidence": 0.85,
                        "probable_root_cause_location": observation.location + " external wall",
                        "probable_root_cause_type": "Hairline and structural cracks in external wall allowing water ingress",
                        "reasoning": (
                            "Cracks on the external wall allow rainwater to penetrate and migrate inward, "
                            "causing dampness and efflorescence on interior surfaces and skirting areas."
                        ),
                    }
                )
                break
    
    # ========================================================================
    # RULE 3 — Terrace waterproofing failure
    # ========================================================================
    if any(word in symptom_lower for word in ["dampness", "ceiling", "leakage", "seepage"]):
        for room_above in rooms_above:
            if "terrace" in room_above.lower():
                # Check for terrace-related findings above
                for finding in findings_above:
                    defect_lower = finding.defect_type.lower() if finding.defect_type else ""
                    if any(
                        word in defect_lower
                        for word in ["terrace", "screed", "ips", "vegetation", "hollow", "waterproof"]
                    ):
                        results.append(
                            {
                                "rule_name": "Terrace waterproofing failure",
                                "confidence": 0.88,
                                "probable_root_cause_location": "Terrace",
                                "probable_root_cause_type": "Failed terrace screed and waterproofing system with accumulated water ingress",
                                "reasoning": (
                                    "Terrace IPS screed has developed cracks and hollowness. "
                                    "Vegetation growth indicates long-term moisture retention. "
                                    "Water channels through the slab below the screed, causing leakage at the ceiling below."
                                ),
                            }
                        )
                        break
    
    # ========================================================================
    # RULE 4 — Parking seepage from bathroom above
    # ========================================================================
    if "parking" in location_lower and any(
        word in symptom_lower for word in ["seepage", "leakage", "moisture"]
    ):
        for room_above in rooms_above:
            room_upper = room_above.upper()
            if any(
                word in room_upper
                for word in ["BATHROOM", "WC", "COMMON BATHROOM", "TOILET"]
            ):
                # Check for plumbing or tile failures
                for finding in findings_above:
                    defect_lower = finding.defect_type.lower() if finding.defect_type else ""
                    if any(
                        word in defect_lower
                        for word in ["tile", "joint", "plumbing", "waterproof", "gap"]
                    ):
                        results.append(
                            {
                                "rule_name": "Parking seepage from bathroom above",
                                "confidence": 0.87,
                                "probable_root_cause_location": room_above,
                                "probable_root_cause_type": "Tile joint failure and plumbing issues in bathroom above parking slab",
                                "reasoning": (
                                    "The parking ceiling receives seepage from the bathroom located directly above, "
                                    "due to tile joint gaps and plumbing issues allowing water infiltration."
                                ),
                            }
                        )
                        break
    
    # ========================================================================
    # RULE 5 — Cross-flat leakage (multi-storey)
    # ========================================================================
    for room_above in rooms_above:
        if "203" in room_above or "flat no. 203" in room_above.lower():
            if any(word in symptom_lower for word in ["dampness", "ceiling", "leakage"]):
                results.append(
                    {
                        "rule_name": "Cross-flat leakage (multi-storey)",
                        "confidence": 0.82,
                        "probable_root_cause_location": "Flat No. 203 bathrooms",
                        "probable_root_cause_type": "Tile joint failure in Flat No. 203 above causing leakage to Flat No. 103 below",
                        "reasoning": (
                            "Gaps between tile joints in bathrooms of Flat No. 203 allow water to migrate downward "
                            "into the ceiling and walls of Flat No. 103 below."
                        ),
                    }
                )
                break
    
    logger.info(f"Rules evaluation complete for {observation.location}: {len(results)} rules matched")
    return results


def get_treatment_recommendations(
    finding: Finding,
    severity_level: str
) -> List[Dict[str, Any]]:
    """
    Generate deterministic treatment recommendations for a finding.
    
    Applies treatment rules based on finding type and severity level.
    Each rule produces zero or more treatment recommendation dicts.
    
    Args:
        finding: The Finding to generate treatments for
        severity_level: The severity level ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        
    Returns:
        List of treatment recommendation dicts, each with keys:
        - treatment_name (str): Name of the treatment
        - description (str): Detailed treatment procedure
        - materials (List[str]): Required materials and tools
        - priority (str): "IMMEDIATE", "SHORT_TERM", or "LONG_TERM"
        - estimated_duration (str): Time estimate for treatment
    """
    recommendations = []
    
    defect_lower = (finding.defect_type or "").lower()
    location_lower = (finding.location or "").lower()
    
    # ========================================================================
    # TREATMENT 1 — Tile Joint Grouting and Waterproofing
    # ========================================================================
    if any(word in defect_lower for word in ["tile", "joint", "grout", "hollowness"]):
        priority = "IMMEDIATE" if severity_level in ("HIGH", "CRITICAL") else "SHORT_TERM"
        recommendations.append(
            {
                "treatment_name": "Tile Joint Grouting and Waterproofing Treatment",
                "description": (
                    "Cut existing joints into V-shape using electric cutter. Fill joints with liquid polymer "
                    "modified mortar (Dr. Fixit URP) ensuring penetration to sub-tile cracks. After initial set, "
                    "apply RTM grout to tile joints. Patch outlets and corners with PMM made from Dr. Fixit URP. "
                    "Allow 24-48 hours air cure."
                ),
                "materials": [
                    "Dr. Fixit URP (Polymer Modified Mortar)",
                    "RTM Tile Grout",
                    "Electric cutter/grinder",
                    "Clean cloth",
                    "Water"
                ],
                "priority": priority,
                "estimated_duration": "2-3 days per bathroom"
            }
        )
    
    # ========================================================================
    # TREATMENT 2 — Crack Repair and Plaster Restoration
    # ========================================================================
    if any(word in defect_lower for word in ["plaster", "crack", "external wall"]):
        priority = "IMMEDIATE" if severity_level == "CRITICAL" else "SHORT_TERM"
        recommendations.append(
            {
                "treatment_name": "Crack Repair and Plaster Restoration",
                "description": (
                    "Chip off damaged and loose plaster. Moisten surface. Apply bonding coat using Dr. Fixit "
                    "Pidicrete URP (1:1 ratio with cement). When tacky, apply first coat of sand-faced cement "
                    "plaster 12-15mm thick in ratio 1:4 CM with shrinkage-compensating waterproofing compound "
                    "Dr. Fixit Lw+ (200ml per cement bag). Apply second coat 8-10mm thick in 1:4 CM with same "
                    "waterproofing compound. Cure properly."
                ),
                "materials": [
                    "Dr. Fixit Pidicrete URP",
                    "Dr. Fixit Lw+ waterproofing compound",
                    "Cement",
                    "Sand",
                    "Tapping hammer",
                    "Bonding tools"
                ],
                "priority": priority,
                "estimated_duration": "5-7 days per area"
            }
        )
    
    # ========================================================================
    # TREATMENT 3 — RCC Member Treatment
    # ========================================================================
    if any(word in defect_lower for word in ["rcc", "structural", "spalling", "reinforcement", "corrosion"]):
        recommendations.append(
            {
                "treatment_name": "RCC Structural Crack Treatment and Reinforcement Protection",
                "description": (
                    "Open cracks in V-shape groove. Fill with heavy duty polymer mortar (Dr. Fixit HB). "
                    "Treat spalled concrete with heavy duty mortar. Treat exposed and corroded reinforcement "
                    "steel using jacketing and standardized strengthening methods. "
                    "Engage licensed Structural Engineer for assessment and supervision."
                ),
                "materials": [
                    "Dr. Fixit HB Heavy Duty Mortar",
                    "Polymer mortar",
                    "Structural engineer consultation",
                    "Jacketing materials",
                    "Anti-corrosion coating for steel"
                ],
                "priority": "IMMEDIATE",
                "estimated_duration": "Depends on structural engineer assessment"
            }
        )
    
    # ========================================================================
    # TREATMENT 4 — External Wall Waterproof Coating System
    # ========================================================================
    if (any(word in defect_lower for word in ["external wall", "crack"]) and
        ("external" in location_lower or "exterior" in location_lower)):
        recommendations.append(
            {
                "treatment_name": "External Wall Waterproof Coating System",
                "description": (
                    "Clean entire external surface. Repair all cracks using polymer modified mortar. "
                    "Apply premium waterproof acrylic emulsion coating system over entire external wall "
                    "surface to prevent water ingress from exterior. Apply minimum two coats with adequate "
                    "cure time between coats."
                ),
                "materials": [
                    "Premium waterproof acrylic emulsion paint",
                    "Polymer modified mortar for crack filling",
                    "Surface cleaner",
                    "Primer",
                    "Paint rollers/brushes"
                ],
                "priority": "SHORT_TERM",
                "estimated_duration": "3-5 days for complete external facade"
            }
        )
    
    # ========================================================================
    # TREATMENT 5 — Terrace Waterproofing System Replacement
    # ========================================================================
    if any(word in defect_lower for word in ["terrace", "screed", "ips", "vegetation", "hollow"]):
        priority = "IMMEDIATE" if severity_level in ("HIGH", "CRITICAL") else "SHORT_TERM"
        recommendations.append(
            {
                "treatment_name": "Terrace Waterproofing System Replacement",
                "description": (
                    "Remove existing failed screed and IPS surface. Clear all vegetation growth. "
                    "Treat the naked RCC slab. Apply new integrated waterproofing system: primer coat followed "
                    "by liquid waterproofing membrane. Lay new IPS/screed with adequate slope (1:100 minimum) "
                    "toward drain outlets. Install proper watta/fillet at all junctions with parapet walls. "
                    "Cover with protective topping."
                ),
                "materials": [
                    "Waterproofing membrane (liquid applied)",
                    "IPS/screed materials",
                    "Cement",
                    "Waterproofing compound",
                    "Slope-forming screed",
                    "Parapet fillet material"
                ],
                "priority": priority,
                "estimated_duration": "7-10 days"
            }
        )
    
    # ========================================================================
    # TREATMENT 6 — Plumbing Outlet and Concealed Pipe Repair
    # ========================================================================
    if any(word in defect_lower for word in ["plumbing", "outlet", "pipe", "trap", "nahani"]):
        priority = "IMMEDIATE" if severity_level in ("HIGH", "CRITICAL") else "SHORT_TERM"
        recommendations.append(
            {
                "treatment_name": "Plumbing Outlet and Concealed Pipe Repair",
                "description": (
                    "Inspect and repair all damaged plumbing outlets (Nahani traps, floor drains). "
                    "Replace damaged concealed plumbing sections where accessible. Install additional outlets "
                    "where required. Ensure proper sealing at all pipe penetrations through slab."
                ),
                "materials": [
                    "Replacement Nahani traps",
                    "Plumbing sealant",
                    "Pipe fittings",
                    "Waterproof grout for pipe penetrations"
                ],
                "priority": priority,
                "estimated_duration": "1-2 days per bathroom"
            }
        )
    
    logger.info(f"Treatment recommendations generated for {finding.location}: {len(recommendations)} treatments")
    return recommendations
