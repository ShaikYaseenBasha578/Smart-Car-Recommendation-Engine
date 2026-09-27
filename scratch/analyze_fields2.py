import re

def clean_key(k):
    k = k.lower().strip()
    k = re.sub(r'[^a-z0-9]', ' ', k)
    k = re.sub(r'\s+', ' ', k).strip()
    return k

examples = [
    "electronic stability control (esc)",
    "tyre pressure monitoring system(tpms) highline",
    "abs(anti-lock braking system) with ebd",
    "abs with ebd",
    "tpms - tyre pressure monitoring system",
    "hyundai smartsense (level 2 adas)"
]

for e in examples:
    print(f"'{e}' -> '{clean_key(e)}'")
