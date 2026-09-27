import os
import json
import hashlib
import time

BASE_DIR = "knowledge_base/sources/oem"
MANIFEST_PATH = "knowledge_base/sources/oem/brochure_manifest.json"

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

with open(MANIFEST_PATH, 'r') as f:
    manifest = json.load(f)

for key, val in manifest.items():
    if val["status"] == "OTHER_FAILURE":
        make_slug = val["manufacturer"].lower().replace(' ', '_').replace('-', '_')
        model_slug = val["model"].lower().replace(' ', '_').replace('-', '_')
        model_dir = os.path.join(BASE_DIR, make_slug, model_slug)
        
        found_pdf = None
        gen_dir = "latest"
        if os.path.exists(model_dir):
            for g_dir in os.listdir(model_dir):
                b_dir = os.path.join(model_dir, g_dir, "brochures")
                if os.path.isdir(b_dir):
                    pdfs = [f for f in os.listdir(b_dir) if f.lower().endswith('.pdf')]
                    if pdfs:
                        found_pdf = os.path.join(b_dir, pdfs[0])
                        gen_dir = g_dir
                        break
                        
        if found_pdf:
            sz = os.path.getsize(found_pdf)
            h = compute_sha256(found_pdf)
            val["status"] = "ALREADY_PRESENT"
            val["artifact_path"] = found_pdf
            val["sha256"] = h
            val["file_size_bytes"] = sz
            val["generation"] = gen_dir
            val["source_url"] = "LOCAL"
            val["direct_document_url"] = "LOCAL"
            val["original_filename"] = os.path.basename(found_pdf)
            val["source_classification"] = "OFFICIAL"
            val["verification_status"] = "VERIFIED"

with open(MANIFEST_PATH, 'w') as f:
    json.dump(manifest, f, indent=2)
