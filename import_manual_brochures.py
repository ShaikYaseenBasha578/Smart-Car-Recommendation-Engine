import sqlite3
import json
import os
import time
import hashlib
import shutil
import fitz  # PyMuPDF

DB_PATH = "knowledge_base/carrec_kb.db"
MANIFEST_PATH = "knowledge_base/sources/oem/brochure_manifest.json"
BASE_DIR = "knowledge_base/sources/oem"
DOWNLOADS_DIR = os.path.expanduser("~/Downloads/Missing Brochures")

MANUAL_MAP = {
    "NEXA-Xl6-Brochure.pdf": "Maruti Suzuki XL6",
    "e-brochure-hycross.pdf": "Toyota Innova Hycross",
    "kushaq_brochure.pdf": "Skoda Kushaq",
    "kylaq_brochure.pdf": "Skoda Kylaq",
    "nexon-ev-brochure.pdf": "Tata Nexon EV",
    "slavia_brochure.pdf": "Skoda Slavia",
    "tiago-brochure-evf-final.pdf": "Tata Tiago EV"
}

def get_models():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT mk.name as manufacturer, m.name as model, m.id as model_id
        FROM model m
        JOIN manufacturer mk ON m.manufacturer_id = mk.id
    """)
    models = [dict(r) for r in c.fetchall()]
    conn.close()
    return models

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def clean_name(name):
    return name.lower().replace(' ', '').replace('-', '').replace('_', '')

def verify_document(filepath, make, model):
    try:
        doc = fitz.open(filepath)
        if not doc: return "REJECTED"
        
        c_model = clean_name(model)
        c_make = clean_name(make)
        
        meta = doc.metadata
        if meta:
            meta_str = str(meta).lower().replace(' ', '').replace('-', '')
            if c_model in meta_str or c_make in meta_str:
                doc.close()
                return "OEM_DOCUMENT_ORIGIN_VERIFIED"
                
        for i in range(min(5, len(doc))):
            text = doc[i].get_text("text").lower().replace(' ', '').replace('-', '')
            if c_model in text or c_make in text:
                doc.close()
                return "OEM_DOCUMENT_ORIGIN_VERIFIED"
                
        doc.close()
        return "OEM_DOCUMENT_ORIGIN_UNCERTAIN"
    except:
        return "OEM_DOCUMENT_ORIGIN_UNCERTAIN"

def run():
    all_models = get_models()
    
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, 'r') as f:
            manifest = json.load(f)
    else:
        manifest = {}

    report = []
    
    for filename in os.listdir(DOWNLOADS_DIR):
        if not filename.lower().endswith('.pdf'): continue
        filepath = os.path.join(DOWNLOADS_DIR, filename)
        
        mapped_name = MANUAL_MAP.get(filename)
        target_model = None
        for m in all_models:
            if f"{m['manufacturer']} {m['model']}" == mapped_name:
                target_model = m
                break
                
        if not target_model:
            print(f"Skipping {filename}: Could not map to a canonical model")
            continue
            
        make = target_model['manufacturer']
        model = target_model['model']
        m_id = target_model['model_id']
        key = f"{make}_{model}"
        
        make_slug = make.lower().replace(' ', '_').replace('-', '_')
        model_slug = model.lower().replace(' ', '_').replace('-', '_')
        
        if make == "Skoda":
            acquisition_source = "CarTrade"
            official_verified = False
            dest_dir = os.path.join(BASE_DIR, make_slug, model_slug, "latest", "brochures", "cartrade")
        else:
            acquisition_source = "Official OEM Website (Manual)"
            official_verified = True
            dest_dir = os.path.join(BASE_DIR, make_slug, model_slug, "latest", "brochures")
            
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        
        identity = verify_document(filepath, make, model)
        if identity == "REJECTED": continue
            
        document_origin = "Skoda OEM" if make == "Skoda" and identity == "OEM_DOCUMENT_ORIGIN_VERIFIED" else "OEM"
        orig_sha = compute_sha256(filepath)
        size = os.path.getsize(filepath)
        
        conflict = False
        newly_imported = True
        if os.path.exists(dest_path):
            existing_sha = compute_sha256(dest_path)
            if existing_sha == orig_sha:
                newly_imported = False
            else:
                conflict = True
                dest_path = os.path.join(dest_dir, f"alt_{filename}")
                shutil.copy2(filepath, dest_path)
        else:
            shutil.copy2(filepath, dest_path)
            
        assert os.path.exists(dest_path), "File was not copied!"
        assert compute_sha256(dest_path) == orig_sha, "Hash mismatch after copy!"
        
        entry = manifest.get(key, {})
        entry.update({
            "manufacturer": make,
            "model": model,
            "model_id": m_id,
            "generation_status": "CURRENT_DOCUMENT_GENERATION_UNCERTAIN",
            "status": "SOURCE_AND_DOCUMENT_VERIFIED" if official_verified and identity == "OEM_DOCUMENT_ORIGIN_VERIFIED" else "SOURCE_VERIFIED_DOCUMENT_IDENTITY_UNCERTAIN" if official_verified else "ALREADY_PRESENT_AND_VERIFIED" if identity == "OEM_DOCUMENT_ORIGIN_VERIFIED" else "UNRESOLVED",
            "artifact_path": dest_path,
            "acquisition_source": acquisition_source,
            "document_origin": document_origin,
            "official_acquisition_verified": official_verified,
            "document_identity_verification": identity,
            "file_size_bytes": size,
            "sha256": orig_sha,
            "import_timestamp": time.time(),
            "provenance_notes": f"Manually imported from Downloads/Missing Brochures. Source: {acquisition_source}"
        })
        manifest[key] = entry
            
        report.append({
            "filename": filename,
            "model": f"{make} {model}",
            "acquisition_source": acquisition_source,
            "document_origin": document_origin,
            "official_acquisition_verified": official_verified,
            "destination_path": dest_path,
            "sha256": orig_sha,
            "identity_verification": identity,
            "newly_imported": newly_imported,
            "conflict": conflict
        })
        
    with open(MANIFEST_PATH, 'w') as f:
        json.dump(manifest, f, indent=2)
        
    with open("import_report.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run()
