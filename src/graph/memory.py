"""
Memory layer for the DDR Intelligence Engine.

Implements the SemanticGraph (defined in state.py) and VectorStoreWrapper
for long-term memory and knowledge retrieval.

The VectorStoreWrapper uses ChromaDB to store and retrieve similar past
inspection cases, enhancing the diagnostic reasoning with historical patterns.
"""

import logging
import os
from typing import Any, Dict, List, Optional

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except (ImportError, Exception):
    CHROMADB_AVAILABLE = False

from src.graph.state import Observation, SemanticGraph

logger = logging.getLogger(__name__)


class VectorStoreWrapper:
    """
    Wrapper around ChromaDB for storing and retrieving past inspection cases.
    
    Stores case summaries as embeddings and enables semantic similarity search.
    Uses sentence-transformers (all-MiniLM-L6-v2) via ChromaDB's default embedding.
    """

    def __init__(self, persist_dir: str):
        """
        Initialize the vector store with persistence.
        
        Creates or loads a ChromaDB instance persisted to disk.
        Gets or creates a collection named "ddr_cases" for inspection data.
        
        Args:
            persist_dir: Directory path for ChromaDB persistence
            
        Raises:
            ValueError: If persist_dir is invalid
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB not installed — system will run in rules-only mode")
        
        if not persist_dir:
            raise ValueError("persist_dir cannot be empty")
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_dir, exist_ok=True)
        
        try:
            # Initialize ChromaDB persistent client
            self.client = chromadb.PersistentClient(path=persist_dir)
            logger.info(f"Initialized ChromaDB client with persist_dir: {persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}", exc_info=True)
            raise
        
        try:
            # Get or create the collection for DDR cases
            self.collection = self.client.get_or_create_collection(
                name="ddr_cases",
                metadata={"description": "Past DDR inspection cases for similarity matching"}
            )
            logger.info("Got or created 'ddr_cases' collection in ChromaDB")
        except Exception as e:
            logger.error(f"Failed to get or create collection: {e}", exc_info=True)
            raise

    def add_case(self, case_dict: Dict[str, Any]) -> None:
        """
        Add a case (past inspection) to the vector store.
        
        Takes a case summary and stores it with an embedding so it can be
        retrieved later via semantic similarity search. The case_dict should
        contain the inspection summary as a string field that will be embedded.
        
        Args:
            case_dict: Dictionary with case data including a 'summary' field
            
        Example:
            case_dict = {
                "case_id": "2024_001",
                "summary": "Hall dampness from bathroom tile gaps above. Confidence 0.92.",
                "observations": [...],
                "findings": [...],
                "date": "2024-01-15"
            }
        """
        if not case_dict:
            logger.warning("add_case called with empty case_dict")
            return
        
        try:
            case_id = case_dict.get("case_id", "unknown")
            summary = case_dict.get("summary", "")
            
            if not summary:
                logger.warning(f"Case {case_id} has no summary, skipping")
                return
            
            # ChromaDB will handle embedding automatically
            # We add the summary as the document, with case metadata
            self.collection.add(
                ids=[case_id],
                documents=[summary],
                metadatas=[{
                    "case_id": case_id,
                    "date": case_dict.get("date", ""),
                    "property": case_dict.get("property", "")
                }]
            )
            logger.info(f"Added case {case_id} to vector store")
        except Exception as e:
            logger.error(f"Failed to add case: {e}", exc_info=True)

    def search_similar(
        self,
        observations: List[Observation],
        k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the k most similar past cases based on observations.
        
        Embeds the provided observations as a search query and retrieves
        the k most similar cases from the vector store. If the store is empty
        (first run), returns an empty list gracefully.
        
        Args:
            observations: List of Observation objects from current inspection
            k: Number of similar cases to retrieve (default 3)
            
        Returns:
            List of dicts with similar case data, empty list if no results
            
        Example return:
            [
                {
                    "case_id": "2024_001",
                    "similarity": 0.87,
                    "summary": "Hall dampness from bathroom defects...",
                    "property": "123 Main St"
                },
                ...
            ]
        """
        if not observations:
            logger.debug("search_similar called with empty observations")
            return []
        
        try:
            # Build a search query from observations
            # Combine all observation descriptions into one search text
            query_texts = [f"{obs.location}: {obs.symptom}" for obs in observations]
            query = " ".join(query_texts)
            
            if not query.strip():
                logger.debug("No valid query built from observations")
                return []
            
            # Query the collection
            # ChromaDB returns results with distances; convert to similarity
            results = self.collection.query(
                query_texts=[query],
                n_results=k
            )
            
            # Transform results into return format
            similar_cases = []
            if results and results.get("ids") and len(results["ids"]) > 0:
                ids = results["ids"][0]
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results.get("distances", [[]])[0]
                
                for idx, (case_id, doc, metadata, distance) in enumerate(
                    zip(ids, documents, metadatas, distances)
                ):
                    # Convert distance to similarity (ChromaDB uses euclidean by default)
                    # Smaller distance = more similar; convert to 0-1 similarity score
                    similarity = 1.0 / (1.0 + distance) if distance is not None else 0.0
                    
                    similar_cases.append({
                        "case_id": case_id,
                        "summary": doc,
                        "similarity": similarity,
                        "property": metadata.get("property", ""),
                        "date": metadata.get("date", "")
                    })
                
                logger.info(f"Retrieved {len(similar_cases)} similar cases")
            else:
                logger.debug("No similar cases found in vector store")
            
            return similar_cases
        
        except Exception as e:
            logger.error(f"Failed to search similar cases: {e}", exc_info=True)
            return []

    def get_collection_size(self) -> int:
        """
        Get the number of cases in the collection.
        
        Returns:
            Number of documents in the collection
        """
        try:
            return len(self.collection.get()["ids"]) if self.collection else 0
        except Exception as e:
            logger.error(f"Failed to get collection size: {e}", exc_info=True)
            return 0
