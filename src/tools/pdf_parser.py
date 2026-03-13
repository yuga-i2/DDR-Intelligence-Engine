"""
PDF parsing utilities with pdfplumber and pdf2image.

Extracts text with structural awareness, tables, and images from PDF files.
Provides both layout-aware text extraction and image conversion.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber
from pdf2image import convert_from_path

logger = logging.getLogger(__name__)


def extract_text_by_section(pdf_path: str) -> Dict[str, Any]:
    """
    Extract text from PDF with section/heading awareness.
    
    Opens the PDF with pdfplumber. Iterates through every page, detecting
    section headings (ALL CAPS or known patterns). Groups text under the
    section heading it belongs to. Also extracts tables.
    
    Heading detection patterns:
    - ALL CAPS lines (e.g., "NEGATIVE SIDE INPUTS FOR BATHROOM")
    - Lines containing "SECTION", "SUMMARY", "ANALYSIS"
    - Lines ending with colon after being ALL CAPS
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict with keys as section names (str), values as section text (str).
        Includes "tables" key with list of extracted tables.
        
    Raises:
        FileNotFoundError: If PDF does not exist
        Exception: If pdfplumber fails to open the PDF
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    sections = {}
    current_section = "PREAMBLE"
    sections[current_section] = ""
    tables_list = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Opened PDF: {pdf_path} with {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text from page
                page_text = page.extract_text()
                if not page_text:
                    logger.debug(f"No text extracted from page {page_num}")
                    continue
                
                # Extract tables if any
                try:
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table in page_tables:
                            tables_list.append({
                                "page_number": page_num,
                                "table_data": table
                            })
                            logger.debug(f"Extracted table from page {page_num}")
                except Exception as e:
                    logger.debug(f"Error extracting tables from page {page_num}: {e}")
                
                # Split page text into lines and detect sections
                lines = page_text.split('\n')
                
                for line in lines:
                    stripped = line.strip()
                    
                    # Detect section headings
                    is_heading = (
                        stripped.isupper() and len(stripped) > 5 and not stripped.isdigit() or
                        "SECTION" in stripped.upper() or
                        "SUMMARY" in stripped.upper() or
                        "ANALYSIS" in stripped.upper() or
                        "NEGATIVE" in stripped.upper() or
                        "POSITIVE" in stripped.upper()
                    )
                    
                    if is_heading and stripped:
                        # Start new section
                        current_section = stripped
                        if current_section not in sections:
                            sections[current_section] = ""
                        logger.debug(f"Detected section: {current_section}")
                    else:
                        # Add text to current section
                        if stripped:
                            sections[current_section] += stripped + "\n"
    
    except Exception as e:
        logger.error(f"Error reading PDF {pdf_path}: {e}", exc_info=True)
        raise
    
    # Add tables to the sections dict
    sections["tables"] = tables_list
    
    logger.info(f"Extracted {len(sections) - 1} sections from {pdf_path}")
    logger.info(f"Section names: {list(sections.keys())}")
    
    return sections


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Convert all PDF pages to PNG images and save them.
    
    Uses pdf2image to convert each page to a PIL Image at 200 DPI.
    Saves images to output_dir with naming: {pdf_stem}_page_{page_number}.png
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted PNG images
        
    Returns:
        List of dicts, each with:
        - page_number (int)
        - image_path (str) — full path to saved PNG
        - width (int) — image width in pixels
        - height (int) — image height in pixels
        - pdf_source (str) — original PDF filename without path
        
    Raises:
        FileNotFoundError: If PDF does not exist
        Exception: If pdf2image fails
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    pdf_path_obj = Path(pdf_path)
    pdf_stem = pdf_path_obj.stem
    pdf_source = pdf_path_obj.name
    
    images_list = []
    
    try:
        logger.info(f"Converting PDF to images: {pdf_path}")
        
        # Convert all pages
        images = convert_from_path(pdf_path, dpi=200)
        logger.info(f"Converted {len(images)} pages to images")
        
        for page_num, image in enumerate(images, 1):
            # Save image
            image_filename = f"{pdf_stem}_page_{page_num}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            image.save(image_path, "PNG")
            
            width, height = image.size
            
            images_list.append({
                "page_number": page_num,
                "image_path": image_path,
                "width": width,
                "height": height,
                "pdf_source": pdf_source
            })
            
            logger.debug(f"Saved image: {image_path} ({width}x{height})")
    
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}", exc_info=True)
        raise
    
    logger.info(f"Extracted {len(images_list)} images to {output_dir}")
    return images_list


def extract_thermal_readings(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract thermal metadata from thermal imaging PDF.
    
    Parses text from each page to find thermal-specific fields.
    
    Expected fields on each page:
    - image_id: filename like "RB02380X.JPG"
    - hotspot_temp: value after "Hotspot :"
    - coldspot_temp: value after "Coldspot :"
    - emissivity: value after "Emissivity :"
    - reflected_temp: value after "Reflected temperature :"
    - date: DD/MM/YY format
    - page_number: the page itself
    
    Args:
        pdf_path: Path to the thermal PDF
        
    Returns:
        List of dicts (one per page) with thermal readings and metadata.
        Missing fields are set to None.
        
    Raises:
        FileNotFoundError: If PDF does not exist
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Thermal PDF not found: {pdf_path}")
    
    thermal_readings = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Extracting thermal readings from {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if not page_text:
                    logger.debug(f"No text on thermal page {page_num}")
                    continue
                
                reading = {
                    "page_number": page_num,
                    "image_id": None,
                    "hotspot_temp": None,
                    "coldspot_temp": None,
                    "emissivity": None,
                    "reflected_temp": None,
                    "date": None
                }
                
                # Parse thermal fields
                lines = page_text.split('\n')
                
                for line in lines:
                    line_upper = line.upper()
                    
                    # Image ID (usually a filename like RB02380X.JPG)
                    if ".JPG" in line_upper or ".PNG" in line_upper:
                        # Extract the filename
                        parts = line.split()
                        for part in parts:
                            if ".JPG" in part.upper() or ".PNG" in part.upper():
                                reading["image_id"] = part
                                break
                    
                    # Hotspot temperature
                    if "HOTSPOT" in line_upper and ":" in line:
                        try:
                            # Extract number after colon
                            value_part = line.split(":")[-1].strip()
                            # Get first number
                            temp_str = ''.join(c for c in value_part.split()[0] if c.isdigit() or c == '.')
                            if temp_str:
                                reading["hotspot_temp"] = float(temp_str)
                        except (ValueError, IndexError):
                            pass
                    
                    # Coldspot temperature
                    if "COLDSPOT" in line_upper and ":" in line:
                        try:
                            value_part = line.split(":")[-1].strip()
                            temp_str = ''.join(c for c in value_part.split()[0] if c.isdigit() or c == '.')
                            if temp_str:
                                reading["coldspot_temp"] = float(temp_str)
                        except (ValueError, IndexError):
                            pass
                    
                    # Emissivity
                    if "EMISSIVITY" in line_upper and ":" in line:
                        try:
                            value_part = line.split(":")[-1].strip()
                            emis_str = ''.join(c for c in value_part.split()[0] if c.isdigit() or c == '.')
                            if emis_str:
                                reading["emissivity"] = float(emis_str)
                        except (ValueError, IndexError):
                            pass
                    
                    # Reflected temperature
                    if "REFLECTED" in line_upper and ":" in line:
                        try:
                            value_part = line.split(":")[-1].strip()
                            temp_str = ''.join(c for c in value_part.split()[0] if c.isdigit() or c == '.')
                            if temp_str:
                                reading["reflected_temp"] = float(temp_str)
                        except (ValueError, IndexError):
                            pass
                    
                    # Date in DD/MM/YY format
                    if "/" in line and not reading["date"]:
                        # Look for date pattern
                        date_match = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line)
                        if date_match:
                            reading["date"] = date_match.group()
                
                thermal_readings.append(reading)
                logger.debug(f"Extracted thermal reading from page {page_num}")
    
    except Exception as e:
        logger.error(f"Error extracting thermal readings: {e}", exc_info=True)
        raise
    
    logger.info(f"Extracted {len(thermal_readings)} thermal readings")
    return thermal_readings
