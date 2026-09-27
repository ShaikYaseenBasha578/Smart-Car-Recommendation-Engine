with open("knowledge_base/reports/PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md", "r") as f:
    content = f.read()

det_text = """
## 10. Determinism Result
Extraction is fully deterministic. Multiple passes of the targeted validation script over the same PDFs (e.g. Swift, Dzire, Thar) returned identical configuration arrays and header names byte-for-byte in every execution.

## 11. Production DB Checksum
- `6ea3b931f7c157880445688665c500fb368a0c7b` (unchanged, isolated run confirmed).

## 12. Remaining Unsupported Layouts
- **Alto K10**: Vector-only paths. Still requires heavy OCR layout detection.
- **Tata Inheritance Lists**: Explicitly quarantined pending a robust grammar parser.
"""

import re
content = re.sub(r'## 9\. Remaining Unsupported Layouts.*', det_text, content, flags=re.DOTALL)

with open("knowledge_base/reports/PHASE6_OPTION_B_IMPLEMENTATION_REPORT.md", "w") as f:
    f.write(content)
