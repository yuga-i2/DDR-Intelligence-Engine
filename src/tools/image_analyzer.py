"""
Image analysis utilities for processing and describing extracted images.

Generates natural language descriptions offline (no LLM calls).
Tags images with building locations based on document context.
"""

import logging
from pathlib import Path
from typing import Dict

from PIL import Image, ImageStat

logger = logging.getLogger(__name__)


def describe_image(image_path: str, location_hint: str = "") -> str:
    """
    Generate a structured text description of an image.
    
    Uses deterministic logic based on image properties:
    - Analyzes brightness to infer lighting conditions
    - Detects if image is thermal based on filename or location_hint
    - No LLM calls — works offline
    
    Brightness thresholds:
    - < 80: "dark interior conditions"
    - 80-160: "moderate lighting"
    - > 160: "well-lit conditions"
    
    Args:
        image_path: Path to the image file
        location_hint: Optional context (e.g., "thermal", "Thermal_Images.pdf")
        
    Returns:
        str: Structured natural language description
    """
    try:
        # Open image and analyze
        image = Image.open(image_path)
        logger.debug(f"Opened image: {image_path} size {image.size}")
        
        # Convert to RGB if needed for analysis
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Calculate mean brightness
        stat = ImageStat.Stat(image)
        mean_brightness = sum(stat.mean) / len(stat.mean)  # Average across RGB
        
        # Build description
        description_parts = []
        
        # Lighting conditions
        if mean_brightness < 80:
            description_parts.append("dark interior conditions")
        elif mean_brightness < 160:
            description_parts.append("moderate lighting")
        else:
            description_parts.append("well-lit conditions")
        
        # Image type detection
        image_filename = Path(image_path).name.lower()
        location_hint_lower = location_hint.lower() if location_hint else ""
        
        is_thermal = (
            "thermal" in image_filename or
            "thermal" in location_hint_lower
        )
        
        if is_thermal:
            description_parts.append("thermal imaging capture")
            description_parts.append("temperature variation pattern visible")
        else:
            description_parts.append("visual inspection photograph")
        
        # Add location hint if provided
        if location_hint:
            description_parts.append(f"Location: {location_hint}")
        
        description = ". ".join(description_parts) + "."
        
        logger.debug(f"Generated description for {image_path}: {description}")
        return description
    
    except Exception as e:
        logger.error(f"Error analyzing image {image_path}: {e}", exc_info=True)
        # Return a fallback description
        return f"Image at {image_path}. {location_hint if location_hint else ''}"


def tag_image_to_location(
    image_path: str,
    page_number: int,
    section_text_map: Dict[str, str]
) -> str:
    """
    Assign a location tag to an image based on document context.
    
    Logic:
    1. Search section_text_map for any section mentioning this page number
    2. If found, return the section name as the location
    3. If not found, check filename for keywords
    4. Falls back to "Page {page_number} — Location Unidentified"
    
    Args:
        image_path: Path to the image file
        page_number: Page number the image was extracted from
        section_text_map: Dict from extract_text_by_section with section names as keys
        
    Returns:
        str: Location tag for the image (room name, section name, or fallback)
    """
    try:
        image_filename = Path(image_path).name.lower()
        
        # Search section text for page references
        for section_name, section_text in section_text_map.items():
            if section_name == "tables":
                # Skip the tables entry
                continue
            
            # Look for page number references in the section text
            if str(page_number) in section_text:
                logger.debug(f"Matched image page {page_number} to section: {section_name}")
                return section_name
            
            # Also check for "Photo", "Image" patterns
            if f"photo {page_number}" in section_text.lower() or \
               f"image {page_number}" in section_text.lower() or \
               f"page {page_number}" in section_text.lower():
                return section_name
        
        # Fallback: check image filename for keywords
        if "thermal" in image_filename:
            return "Thermal Reference"
        
        # If no match found
        return f"Page {page_number}"
    
    except Exception as e:
        logger.error(f"Error tagging image {image_path}: {e}", exc_info=True)
        return f"Page {page_number}"
