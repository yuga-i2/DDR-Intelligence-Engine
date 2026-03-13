import json

with open("outputs/extraction_debug.json") as f:
    data = json.load(f)

print("✓ Verification Checklist:")
print(f"  1. observations:     {len(data.get('observations', []))} items (expected: 7)")
print(f"  2. findings:         {len(data.get('findings', []))} items (expected: 8)")
print(f"  3. semantic_graph:   {data.get('semantic_graph') is not None}")

if data.get("semantic_graph"):
    nodes = data["semantic_graph"].get("nodes", [])
    edges = data["semantic_graph"].get("edges", [])
    print(f"  4. graph nodes:      {len(nodes)} nodes")
    print(f"  5. graph edges:      {len(edges)} edges")

print(f"  6. extracted_text:   {len(data.get('extracted_text', {}))} sections")
print(f"  7. extracted_images: {len(data.get('extracted_images', []))} images")
print(f"  8. validation:       {data.get('validated')}")
print(f"  9. agent_logs:       {len(data.get('agent_logs', []))} entries")

# Check a sample observation
if data.get("observations"):
    obs = data["observations"][0]
    print(f"\nSample Observation:")
    print(f"  Location: {obs.get('location')}")
    print(f"  Symptom: {obs.get('symptom')}")
    print(f"  Severity: {obs.get('severity')}")

# Check a sample finding
if data.get("findings"):
    finding = data["findings"][0]
    print(f"\nSample Finding:")
    print(f"  Location: {finding.get('location')}")
    print(f"  Defect: {finding.get('defect_type')}")
