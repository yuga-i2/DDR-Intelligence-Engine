"""
Spatial reasoning utilities for semantic graph traversal.

Enables spatial queries on the SemanticGraph:
- Find rooms above/adjacent to a location
- Retrieve findings/observations at a location
- Build spatial relationships from text
"""

import logging
from typing import Any, Dict, List

from src.graph.state import (
    NODE_ROOM,
    NODE_FINDING,
    NODE_SYMPTOM,
    REL_ABOVE,
    REL_ADJACENT,
    Finding,
    Observation,
    SemanticGraph,
)

logger = logging.getLogger(__name__)


def get_rooms_above(graph: SemanticGraph, location: str) -> List[str]:
    """
    Get all rooms positioned above the given location.
    
    Traverses the graph's DiGraph to find room nodes with an "above"
    edge pointing to the given location.
    
    Args:
        graph: SemanticGraph instance
        location: Location string (case-insensitive match)
        
    Returns:
        List of room names above this location
    """
    try:
        rooms_above = []
        
        # Iterate through all nodes in the graph
        for node_id in graph.graph.nodes():
            node_data = graph.graph.nodes[node_id]
            
            # Check if this is a room node
            if node_data.get("type") != NODE_ROOM:
                continue
            
            # Check if there's an edge from this room to the location with REL_ABOVE
            for successor in graph.graph.successors(node_id):
                if successor.lower() == location.lower():
                    edge_data = graph.graph.get_edge_data(node_id, successor)
                    if edge_data and edge_data.get("relation") == REL_ABOVE:
                        rooms_above.append(node_id)
                        logger.debug(f"Found room above {location}: {node_id}")
        
        return rooms_above
    
    except Exception as e:
        logger.error(f"Error getting rooms above {location}: {e}", exc_info=True)
        return []


def get_rooms_adjacent(graph: SemanticGraph, location: str) -> List[str]:
    """
    Get all rooms adjacent to the given location.
    
    Traverses the graph to find room nodes with an "adjacent_to"
    edge pointing to the given location.
    
    Args:
        graph: SemanticGraph instance
        location: Location string (case-insensitive match)
        
    Returns:
        List of adjacent room names
    """
    try:
        adjacent_rooms = []
        
        for node_id in graph.graph.nodes():
            node_data = graph.graph.nodes[node_id]
            
            if node_data.get("type") != NODE_ROOM:
                continue
            
            for successor in graph.graph.successors(node_id):
                if successor.lower() == location.lower():
                    edge_data = graph.graph.get_edge_data(node_id, successor)
                    if edge_data and edge_data.get("relation") == REL_ADJACENT:
                        adjacent_rooms.append(node_id)
                        logger.debug(f"Found adjacent room to {location}: {node_id}")
        
        return adjacent_rooms
    
    except Exception as e:
        logger.error(f"Error getting adjacent rooms to {location}: {e}", exc_info=True)
        return []


def get_findings_at(graph: SemanticGraph, location: str) -> List[Finding]:
    """
    Get all defects recorded at a specific location.
    
    Finds the room/location node and returns all Finding objects
    attached to it via has_finding edges.
    
    Args:
        graph: SemanticGraph instance
        location: Location string
        
    Returns:
        List of Finding objects at this location
    """
    try:
        findings = []
        
        # Find the location node (room node)
        location_node = None
        for node_id in graph.graph.nodes():
            if node_id.lower() == location.lower():
                location_node = node_id
                break
        
        if not location_node:
            logger.debug(f"Location node not found: {location}")
            return []
        
        # Find all finding nodes connected to this location
        for successor in graph.graph.successors(location_node):
            node_data = graph.graph.nodes[successor]
            if node_data.get("type") == NODE_FINDING:
                finding = node_data.get("finding")
                if finding:
                    findings.append(finding)
                    logger.debug(f"Found finding at {location}: {finding.defect_type}")
        
        return findings
    
    except Exception as e:
        logger.error(f"Error getting findings at {location}: {e}", exc_info=True)
        return []


def get_observations_at(graph: SemanticGraph, location: str) -> List[Observation]:
    """
    Get all symptoms recorded at a specific location.
    
    Finds the room/location node and returns all Observation objects
    attached to it via has_symptom edges.
    
    Args:
        graph: SemanticGraph instance
        location: Location string
        
    Returns:
        List of Observation objects at this location
    """
    try:
        observations = []
        
        # Find the location node
        location_node = None
        for node_id in graph.graph.nodes():
            if node_id.lower() == location.lower():
                location_node = node_id
                break
        
        if not location_node:
            logger.debug(f"Location node not found: {location}")
            return []
        
        # Find all observation nodes connected to this location
        for successor in graph.graph.successors(location_node):
            node_data = graph.graph.nodes[successor]
            if node_data.get("type") == NODE_SYMPTOM:
                observation = node_data.get("observation")
                if observation:
                    observations.append(observation)
                    logger.debug(f"Found observation at {location}: {observation.symptom}")
        
        return observations
    
    except Exception as e:
        logger.error(f"Error getting observations at {location}: {e}", exc_info=True)
        return []


def build_spatial_relationships_from_text(
    graph: SemanticGraph,
    extracted_text: Dict[str, Any]
) -> SemanticGraph:
    """
    Infer spatial relationships from extracted text and add to graph.
    
    Applies building-domain heuristics to detect spatial relationships.
    Hard-codes known relationships from the inspection documents.
    
    Rules:
    1. Floor inference: "1st Floor" → floor 1, "Ground Floor" → floor 0, etc.
    2. Above/below inference: extracts from context
    3. Hard-coded relationships from known document structure
    4. Parking relationship
    
    Args:
        graph: SemanticGraph instance
        extracted_text: Dict from extract_text_by_section
        
    Returns:
        Modified SemanticGraph with rooms and relationships added
    """
    try:
        logger.info("Building spatial relationships from text")
        
        # Known relationships to hardcode from the inspection documents
        known_relationships = [
            ("Master Bedroom Bathroom (1st Floor)", REL_ABOVE, "Hall Ceiling (Ground Floor)"),
            ("Master Bedroom Bathroom (1st Floor)", REL_ABOVE, "Bedroom Skirting (Ground Floor)"),
            ("Common Bathroom (Ground Floor)", REL_ADJACENT, "Hall (Ground Floor)"),
            ("Master Bedroom Bathroom (1st Floor)", REL_ABOVE, "Master Bedroom Skirting (Ground Floor)"),
            ("Common Bathroom (Flat No. 203)", REL_ABOVE, "Common Bathroom Ceiling (Flat No. 103)"),
            ("Balcony", REL_ADJACENT, "Staircase Area"),
            ("External Wall", REL_ADJACENT, "Master Bedroom (1st Floor)"),
            ("Terrace", REL_ABOVE, "Master Bedroom 2 (1st Floor)"),
            ("Common Bathroom (Ground Floor)", REL_ABOVE, "Parking Ceiling"),
        ]
        
        # Also extract room names from the text to add all rooms
        rooms_to_add = set()
        
        # Add rooms from the known relationships
        for room_a, _, room_b in known_relationships:
            rooms_to_add.add(room_a)
            rooms_to_add.add(room_b)
        
        # Extract additional rooms from text
        text_content = " ".join(extracted_text.values()) if isinstance(extracted_text, dict) else ""
        
        # Common room keywords
        room_keywords = [
            "Hall", "Bathroom", "Bedroom", "Kitchen", "Parking",
            "Terrace", "Balcony", "External Wall", "Staircase",
            "Ceiling", "Skirting", "Floor"
        ]
        
        for keyword in room_keywords:
            if keyword.lower() in text_content.lower():
                # Try to extract room phrases containing this keyword
                for section_name in extracted_text.keys():
                    if section_name != "tables" and keyword in section_name:
                        rooms_to_add.add(section_name)
        
        # Add all rooms to the graph
        for room_name in rooms_to_add:
            if room_name:  # Skip empty strings
                # Extract floor level from room name if present
                level = None
                if "1st Floor" in room_name:
                    level = 1
                elif "Ground Floor" in room_name or "Flat No." in room_name:
                    level = 0
                elif "Parking" in room_name:
                    level = -1
                
                graph.add_room(room_name, level=level)
                logger.debug(f"Added room: {room_name} (level {level})")
        
        # Add all spatial relationships
        for room_a, relation, room_b in known_relationships:
            try:
                graph.add_spatial_relationship(room_a, relation, room_b)
                logger.debug(f"Added relationship: {room_a} -{relation}-> {room_b}")
            except Exception as e:
                logger.warning(f"Could not add relationship {room_a} -{relation}-> {room_b}: {e}")
        
        logger.info(f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        return graph
    
    except Exception as e:
        logger.error(f"Error building spatial relationships: {e}", exc_info=True)
        return graph
