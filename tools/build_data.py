"""Convert the Finndex spreadsheet into site/data.json for the map.

Usage:
    python3 tools/build_data.py "Finndex (1).xlsx"            # real data -> site/data.json
    python3 tools/build_data.py "Finndex (1).xlsx" --redact   # placeholder reasons -> site/data.json

Reason text is copied straight through and never printed. Only country codes
and names show up in the output, so the script can be run without exposing it.
"""
import json
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
ISO = json.loads((ROOT / "tools" / "iso3_to_numeric.json").read_text())
MAP = json.loads((ROOT / "site" / "vendor" / "countries-50m.json").read_text())

# Map features that have no ISO numeric id in world-atlas are matched by name.
NAME_KEYS = {"KSV": "Kosovo", "XKX": "Kosovo"}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    redact = "--redact" in sys.argv
    xlsx = Path(args[0]) if args else ROOT / "Finndex (1).xlsx"

    ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip().lower() if h else "" for h in next(rows)]
    col = {name: header.index(name) for name in ("code", "attractiveness", "country", "reason")}

    features = MAP["objects"]["countries"]["geometries"]
    ids = {f["id"] for f in features if "id" in f}
    names = {f["properties"]["name"] for f in features}

    data, unmatched = {}, []
    for r in rows:
        code = r[col["code"]]
        if not code:
            continue
        code = str(code).strip().upper()
        country = r[col["country"]]
        key = NAME_KEYS.get(code) or ISO.get(code)
        if key is None or (key not in ids and key not in names):
            unmatched.append(f"{code} ({country})")
            continue
        reason = r[col["reason"]] or ""
        data[key] = {
            "code": code,
            "country": country,
            "score": r[col["attractiveness"]],
            "reason": f"Placeholder reason for {country}." if redact else str(reason).strip(),
        }

    out = ROOT / "site" / "data.json"
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    no_data = sorted(f["properties"]["name"] for f in features
                     if f.get("id") not in data and f["properties"]["name"] not in data)
    print(f"wrote {len(data)} countries to {out.relative_to(ROOT)}{' (redacted)' if redact else ''}")
    print("in sheet but not on map:", ", ".join(unmatched) or "none")
    print("on map with no sheet row:", ", ".join(no_data) or "none")


if __name__ == "__main__":
    main()
