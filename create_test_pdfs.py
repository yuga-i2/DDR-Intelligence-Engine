"""Create test PDF files for testing the DDR Intelligence Engine."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path

# Create data directory
data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

# Create Sample_Report.pdf (inspection report)
pdf_path = data_dir / "Sample_Report.pdf"
c = canvas.Canvas(str(pdf_path), pagesize=letter)
c.setFont("Helvetica", 14)

# Add content
c.drawString(1*inch, 10*inch, "INSPECTION REPORT")
c.setFont("Helvetica", 12)

y = 9.5 * inch
sections = [
    ("GROUND FLOOR", [
        "Hall - Skirting dampness detected, SEVERITY: LOW",
        "Bedroom - Skirting dampness observed, SEVERITY: LOW", 
        "Master Bedroom - Skirting dampness + efflorescence, SEVERITY: MEDIUM",
        "Kitchen - Minor dampness on skirting, SEVERITY: LOW"
    ]),
    ("FIRST FLOOR", [
        "Master Bedroom Wall - Moisture and salt deposits, SEVERITY: MEDIUM",
        "Master Bedroom Bathroom 1st Floor - Above Hall Ceiling"
    ]),
    ("PARKING & EXTRAS", [
        "Parking Ceiling - Water seepage detected, SEVERITY: HIGH",
        "Common Bathroom 103 - Mild dampness on ceiling, SEVERITY: LOW",
        "Common Bathroom 203 - Outlet leakage, SEVERITY: MEDIUM"
    ])
]

for section_name, items in sections:
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1*inch, y, section_name)
    y -= 0.25*inch
    
    c.setFont("Helvetica", 10)
    for item in items:
        c.drawString(1.2*inch, y, "• " + item)
        y -= 0.2*inch
    y -= 0.15*inch

c.save()
print(f"✓ Created {pdf_path}")

# Create Thermal_Images.pdf (thermal report with metadata)
pdf_path2 = data_dir / "Thermal_Images.pdf"
c2 = canvas.Canvas(str(pdf_path2), pagesize=letter)
c2.setFont("Helvetica", 14)

c2.drawString(1*inch, 10*inch, "THERMAL IMAGING REPORT")
c2.setFont("Helvetica", 12)

y = 9.5 * inch
c2.drawString(1*inch, y, "THERMAL IMAGE ANALYSIS")
y -= 0.3*inch

thermal_data = [
    ("Hall - Ceiling", "35.2°C", "18.5°C", "0.92", "22.1°C", "15/01/25"),
    ("Bedroom - Wall", "32.8°C", "16.3°C", "0.88", "23.4°C", "15/01/25"),
    ("Master Bedroom", "38.1°C", "14.2°C", "0.95", "24.8°C", "15/01/25"),
    ("Kitchen - Ceiling", "31.5°C", "17.8°C", "0.90", "23.0°C", "15/01/25"),
]

c2.setFont("Helvetica", 9)
c2.drawString(1*inch, y, "Location | Hotspot | Coldspot | Emissivity | Reflected | Date")
y -= 0.25*inch

for location, hotspot, coldspot, emissivity, reflected, date_val in thermal_data:
    text = f"{location} | {hotspot} | {coldspot} | {emissivity} | {reflected} | {date_val}"
    c2.drawString(1*inch, y, text)
    y -= 0.2*inch

c2.save()
print(f"✓ Created {pdf_path2}")

print("\n✓ Test PDF files created successfully")
