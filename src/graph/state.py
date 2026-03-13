"""
State schema and data models for the DDR Intelligence Engine.

Defines the central DDRState TypedDict that flows through all agents,
and the Pydantic models that represent structured data within the state.

Every field in DDRState is documented with which agent writes to it.
All nested objects use Pydantic v2 for validation and serialization.
"""

from typing import Any, Dict, List, Optional, TypedDict, Literal, NotRequired
from pydantic import BaseModel, Field
import networkx as nx

# ============================================================================
# STRING CONSTANTS - The Source of Truth for Magic Strings
# ============================================================================

# Severity levels
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

# Spatial relationship types
REL_ABOVE = "above"
REL_BELOW = "below"
REL_ADJACENT = "adjacent_to"

# Node types in semantic graph
NODE_ROOM = "room"
NODE_SYMPTOM = "symptom"
NODE_FINDING = "finding"

# Edge types in semantic graph
EDGE_HAS_SYMPTOM = "has_symptom"
EDGE_HAS_FINDING = "has_finding"
EDGE_CAUSES = "causes"

# ============================================================================
# PYDANTIC MODELS - Structured Data Validated by Schema
# ============================================================================


class ImageEvidence(BaseModel):
    """
    A single image extracted from a PDF with location and content metadata.
    
    Represents one piece of visual evidence (photo or thermal image)
    used to document a symptom or defect.
    """

    image_path: str = Field(
        ..., description="File path to the extracted image"
    )
    location: str = Field(
        ..., description="Building location this image documents (e.g., 'Hall', 'Bathroom')"
    )
    image_type: str = Field(
        ..., description="Type of image: 'thermal' or 'visual'"
    )
    description: str = Field(
        ..., description="Natural language description of what the image shows"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata: page number, bounding box, dimensions, etc."
    )


class Observation(BaseModel):
    """
    A symptom or defect observed on the negative side of an inspection report.
    
    Represents one piece of evidence that something is wrong,
    such as dampness, a crack, or discoloration.
    """

    location: str = Field(
        ..., description="Where the symptom is located (e.g., 'Hall Ceiling')"
    )
    symptom: str = Field(
        ..., description="Description of the symptom (e.g., 'dampness patch')"
    )
    severity: Literal["low", "medium", "high"] = Field(
        default=SEVERITY_LOW,
        description="Initial severity assessment"
    )
    extent: str = Field(
        default="",
        description="How much area is affected (e.g., '1.2m x 0.8m', '25%')"
    )
    evidence: List[ImageEvidence] = Field(
        default_factory=list,
        description="Images documenting this observation"
    )


class Finding(BaseModel):
    """
    A defect or root cause documented on the positive side of the inspection.
    
    Represents one identified structural issue, such as a tile joint gap,
    crack, or failed waterproofing.
    """

    location: str = Field(
        ..., description="Where the defect is located (e.g., 'Bathroom Floor')"
    )
    defect_type: str = Field(
        ..., description="Type of defect (e.g., 'tile joint gap', 'crack', 'failed grouting')"
    )
    description: str = Field(
        ..., description="Detailed description of the defect"
    )
    extent: str = Field(
        default="",
        description="Size or severity measure of the defect"
    )


class Correlation(BaseModel):
    """
    A validated causal link between a symptom and a root cause.
    
    Represents a verified (or high-confidence) connection showing
    that a specific defect is responsible for a specific symptom.
    """

    symptom_location: str = Field(
        ..., description="Location of the symptom"
    )
    symptom_type: str = Field(
        ..., description="Type of symptom (e.g., 'dampness', 'crack')"
    )
    root_cause_location: str = Field(
        ..., description="Location of the defect causing the symptom"
    )
    root_cause_type: str = Field(
        ..., description="Type of defect (e.g., 'tile gap', 'structural crack')"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence level 0.0 to 1.0 that this causal link is correct"
    )
    reasoning: str = Field(
        ..., description="Explanation of why this defect causes this symptom"
    )
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Direct quotes or references from source documents supporting this link"
    )


class SemanticGraph:
    """
    A semantic graph representing building structure and relationships.
    
    Wraps a NetworkX DiGraph where:
    - Nodes represent rooms, symptoms, and findings
    - Edges represent spatial relationships, causation, and containment
    
    This enables spatial traversal queries like "what rooms are above this location"
    that form the foundation of causal reasoning.
    """

    def __init__(self):
        """Initialize an empty semantic graph."""
        self.graph = nx.DiGraph()

    def add_room(self, name: str, level: Optional[int] = None) -> None:
        """
        Add a room/space node to the graph.
        
        Args:
            name: Room name (e.g., 'Hall', 'Bathroom')
            level: Floor level number if known
        """
        self.graph.add_node(
            name,
            type=NODE_ROOM,
            name=name,
            level=level
        )

    def add_spatial_relationship(self, room_a: str, relation: str, room_b: str) -> None:
        """
        Add a spatial relationship edge between two rooms.
        
        Args:
            room_a: First room name
            relation: Relationship type (REL_ABOVE, REL_BELOW, REL_ADJACENT)
            room_b: Second room name
        """
        self.graph.add_edge(room_a, room_b, relation=relation)

    def add_symptom_to_room(self, location: str, observation: Observation) -> None:
        """
        Add a symptom node and link it to a room.
        
        Args:
            location: Room location
            observation: Observation object representing the symptom
        """
        symptom_node_id = f"{location}__symptom__{observation.symptom}"
        self.graph.add_node(
            symptom_node_id,
            type=NODE_SYMPTOM,
            observation=observation,
            location=location
        )
        self.graph.add_edge(location, symptom_node_id, relation=EDGE_HAS_SYMPTOM)

    def add_finding_to_room(self, location: str, finding: Finding) -> None:
        """
        Add a finding node and link it to a room.
        
        Args:
            location: Room location
            finding: Finding object representing the defect
        """
        finding_node_id = f"{location}__finding__{finding.defect_type}"
        self.graph.add_node(
            finding_node_id,
            type=NODE_FINDING,
            finding=finding,
            location=location
        )
        self.graph.add_edge(location, finding_node_id, relation=EDGE_HAS_FINDING)

    def add_causal_link(self, finding_node_id: str, symptom_node_id: str) -> None:
        """
        Add a causal edge from a finding to a symptom.
        
        Args:
            finding_node_id: Node ID of the defect
            symptom_node_id: Node ID of the symptom it causes
        """
        self.graph.add_edge(finding_node_id, symptom_node_id, relation=EDGE_CAUSES)

    def get_rooms_above(self, location: str) -> List[str]:
        """
        Get all rooms positioned above the given location.
        
        Traverses "above" edges to find rooms that could affect this location
        via gravity-driven mechanisms (water seepage, etc.).
        
        Args:
            location: Location string
            
        Returns:
            List of room names above this location
        """
        rooms_above = []
        for node in self.graph.nodes():
            if self.graph.has_edge(node, location):
                edge_data = self.graph.get_edge_data(node, location)
                if edge_data.get('relation') == REL_ABOVE:
                    rooms_above.append(node)
        return rooms_above

    def get_rooms_adjacent(self, location: str) -> List[str]:
        """
        Get all rooms adjacent to the given location.
        
        Traverses "adjacent_to" edges for horizontal relationships
        (shared walls, connected spaces).
        
        Args:
            location: Location string
            
        Returns:
            List of adjacent room names
        """
        adjacent_rooms = []
        for node in self.graph.nodes():
            if self.graph.has_edge(node, location):
                edge_data = self.graph.get_edge_data(node, location)
                if edge_data.get('relation') == REL_ADJACENT:
                    adjacent_rooms.append(node)
        return adjacent_rooms

    def get_findings_at(self, location: str) -> List[Finding]:
        """
        Get all defects recorded at a specific location.
        
        Args:
            location: Location string
            
        Returns:
            List of Finding objects at this location
        """
        findings = []
        for node in self.graph.successors(location):
            node_data = self.graph.nodes[node]
            if node_data.get('type') == NODE_FINDING:
                findings.append(node_data.get('finding'))
        return findings

    def get_observations_at(self, location: str) -> List[Observation]:
        """
        Get all symptoms recorded at a specific location.
        
        Args:
            location: Location string
            
        Returns:
            List of Observation objects at this location
        """
        observations = []
        for node in self.graph.successors(location):
            node_data = self.graph.nodes[node]
            if node_data.get('type') == NODE_SYMPTOM:
                observations.append(node_data.get('observation'))
        return observations

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the graph to a dict for storage in state.
        
        Returns:
            Dict representation of the graph
        """
        return {
            "nodes": dict(self.graph.nodes(data=True)),
            "edges": [
                (u, v, self.graph.get_edge_data(u, v))
                for u, v in self.graph.edges()
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticGraph":
        """
        Deserialize a graph from a dict.
        
        Args:
            data: Dict representation of the graph
            
        Returns:
            SemanticGraph instance
        """
        graph_obj = cls()
        
        # Restore nodes with their attributes
        for node_id, node_attrs in data.get("nodes", {}).items():
            graph_obj.graph.add_node(node_id, **node_attrs)
        
        # Restore edges with their attributes
        for u, v, edge_attrs in data.get("edges", []):
            graph_obj.graph.add_edge(u, v, **edge_attrs)
        
        return graph_obj

    def number_of_nodes(self) -> int:
        """Get the number of nodes in the graph."""
        return self.graph.number_of_nodes()

    def number_of_edges(self) -> int:
        """Get the number of edges in the graph."""
        return self.graph.number_of_edges()


# ============================================================================
# DDRSTATE TYPEDDICT - The Central Flowing State
# ============================================================================


class DDRState(TypedDict):
    """
    The complete state object that flows through all agents in the LangGraph workflow.
    
    Every field is documented with which agent writes to it.
    The state is the single source of truth for all intermediate data.
    """

    # INPUT PATHS (set by main.py)
    inspection_pdf_path: str
    """Path to the inspection PDF file. Written by: main.py"""
    
    thermal_pdf_path: str
    """Path to the thermal imaging PDF file. Written by: main.py"""

    # EXTRACTED DATA (written by document_understanding_agent)
    extracted_text: Dict[str, Any]
    """Structured text from PDFs with layout/section metadata. Written by: document_understanding"""
    
    extracted_images: List[ImageEvidence]
    """All images from PDFs with location tags and descriptions. Written by: document_understanding"""
    
    extracted_tables: List[Dict[str, Any]]
    """Tabular data from PDFs if any. Written by: document_understanding"""

    # SEMANTIC GRAPH (written by document_understanding_agent, read by all subsequent agents)
    semantic_graph: SemanticGraph
    """NetworkX graph of building structure and relationships. Written by: document_understanding, read by: diagnostic_reasoning, validator"""

    # OBSERVATIONS AND FINDINGS (written by document_understanding_agent)
    observations: List[Observation]
    """Symptoms/defects observed (negative side). Written by: document_understanding"""
    
    findings: List[Finding]
    """Root causes/defects found (positive side). Written by: document_understanding"""

    # CORRELATIONS (written by diagnostic_reasoning_agent, refined by knowledge_retrieval_agent)
    correlations: List[Correlation]
    """Causal links between symptoms and root causes. Written by: diagnostic_reasoning, refined by: knowledge_retrieval"""
    
    # KNOWLEDGE-ENHANCED DATA (written by knowledge_retrieval_agent)
    recommended_actions: NotRequired[Dict[str, List[Dict[str, Any]]]]
    """Treatment recommendations keyed by location. Written by: knowledge_retrieval"""
    
    root_causes: List[Dict[str, Any]]
    """Consolidated unique root causes. Written by: knowledge_retrieval"""
    
    similar_cases: List[Dict[str, Any]]
    """Similar past cases retrieved from ChromaDB. Written by: knowledge_retrieval"""
    
    applied_rules: List[str]
    """Names of expert rules that fired. Written by: knowledge_retrieval"""
    
    severity_assessments: Dict[str, str]
    """Location → severity mapping from severity matrix. Written by: knowledge_retrieval"""

    # VALIDATION STATE (written by validator_agent)
    validated: bool
    """Whether all claims passed validation. Written by: validator"""
    
    validation_passed: NotRequired[bool]
    """Whether validation was successful (True/False). Written by: validator"""
    
    validation_errors: NotRequired[List[str]]
    """List of validation failures if any. Written by: validator"""
    
    hallucinations_detected: List[str]
    """Claims that could not be grounded in source text. Written by: validator"""
    
    missing_data: List[str]
    """Building elements not covered by inspection. Written by: validator"""
    
    refinement_feedback: NotRequired[str]
    """Structured feedback for retry iteration. Written by: validator"""
    
    report_warnings: NotRequired[List[str]]
    """Warnings surfaced in final report due to failed validation. Written by: validator"""

    # ITERATION AND LOGGING (written by workflow)
    iteration_count: int
    """Number of self-correction iterations performed. Written by: workflow"""
    
    agent_logs: List[Dict[str, Any]]
    """Execution trace with timestamps and metrics per agent. Written by: all agents"""

    # OUTPUT (written by report_synthesis_agent)
    final_ddr_html: str
    """Rendered HTML for the DDR. Written by: report_synthesis"""
    
    final_ddr_html_path: str
    """Path to generated HTML file. Written by: report_synthesis"""
    
    final_ddr_pdf_path: str
    """Path to generated PDF file. Written by: report_synthesis"""
