import time
import os
import json

while True:
    time.sleep(5)
    try:
        if os.path.exists("knowledge_base/sources/oem/batch_report.json"):
            with open("knowledge_base/sources/oem/batch_report.json") as f:
                report = json.load(f)
            # if total_attempted is around 62 and no CLASSIFICATION_UNKNOWN, it's done or nearing done.
            # actually it's written only at the end.
            # let's just check if process is alive.
            pass
    except Exception:
        pass
