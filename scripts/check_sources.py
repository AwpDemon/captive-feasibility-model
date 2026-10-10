"""Re-check that every cited source URL in config/assumptions.yaml still resolves.

Usage:  python scripts/check_sources.py
Polite by design: descriptive User-Agent, one request at a time, 2-second pause.
This does not re-verify the figures themselves - open each URL and compare the
quoted text in the `sources:` block before relying on a number.
"""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

import yaml

UA = "AwpDemon portfolio aliaskari.georgia@gmail.com"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "assumptions.yaml"


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    urls = sorted({v["url"] for k, v in cfg["sources"].items() if isinstance(v, dict) and v.get("url")})
    bad = 0
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status = r.status
        except Exception as exc:  # noqa: BLE001 - report every failure mode the same way
            status = f"ERROR {exc.__class__.__name__}: {exc}"
            bad += 1
        print(f"{status}  {url}")
        time.sleep(2)
    print(f"\n{len(urls) - bad}/{len(urls)} sources reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
