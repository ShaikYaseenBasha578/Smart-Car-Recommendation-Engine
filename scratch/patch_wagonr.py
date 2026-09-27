import json
import os
import hashlib

with open("knowledge_base/sources/oem/brochure_manifest.json", "r") as f:
    manifest = json.load(f)

key = "Maruti Suzuki_WagonR"
if key in manifest:
    val = manifest[key]
    found_pdf = "knowledge_base/sources/oem/maruti_suzuki/wagon_r/latest/brochures/WagonR_Brochure.pdf"
    def compute_sha256(filepath):
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    sz = os.path.getsize(found_pdf)
    h = compute_sha256(found_pdf)
    val["status"] = "ALREADY_PRESENT"
    val["artifact_path"] = found_pdf
    val["sha256"] = h
    val["file_size_bytes"] = sz
    val["generation"] = "latest"
    val["source_url"] = "LOCAL"
    val["direct_document_url"] = "LOCAL"
    val["original_filename"] = os.path.basename(found_pdf)
    val["source_classification"] = "OFFICIAL"
    val["verification_status"] = "VERIFIED"

with open("knowledge_base/sources/oem/brochure_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
