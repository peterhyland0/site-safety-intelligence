"""Download the raw data. OSHA enforcement tables come from the DOL Open Data Portal's official
"Download Complete Dataset" zips (refreshed daily); WA and OR licence lists from their state open-data
portals. OSHA's ITA injury files and California's CSLB list are downloaded by hand in a browser (see the
README) and copied into data/raw/reference/.

    uv run python -m ssi.pipeline.download --osha --licences
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

import httpx

from ssi import config

OSHA_TABLES = ["inspection", "violation", "accident", "accident_injury", "accident_abstract", "accident_lookup2"]
OSHA_URL = "https://data.dol.gov/data-catalog/OSHA/{t}/OSHA_{t}.zip"
LICENCE_URLS = {
    "wa_lni/wa_lni_general_m8qx-ubtq.csv": "https://data.wa.gov/api/views/m8qx-ubtq/rows.csv?accessType=DOWNLOAD",
    "or_ccb/or_ccb_active_g77e-6bhs.csv": "https://data.oregon.gov/api/views/g77e-6bhs/rows.csv?accessType=DOWNLOAD",
}


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(60, read=300)) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            f.writelines(r.iter_bytes(1 << 20))
    tmp.replace(dest)
    print(f"  {dest.name}: {dest.stat().st_size / 1e6:.0f} MB", flush=True)


def download_osha(raw_dir: Path) -> None:
    for t in OSHA_TABLES:
        z = raw_dir / f"OSHA_{t}.zip"
        fetch(OSHA_URL.format(t=t), z)
        extract(z, raw_dir / t)


def extract(z: Path, out: Path) -> None:
    """The zip's files into `out`, replacing what's there only once every file is out whole: extracting in place left
    a partial folder when it failed part way (a full disk), which a later build read as the whole dataset."""
    part = out.with_name(out.name + ".part")
    shutil.rmtree(part, ignore_errors=True)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(part)  # a damaged member fails its CRC check here
        missing = [m.filename for m in zf.infolist() if not m.is_dir()
                   and (not (part / m.filename).is_file() or (part / m.filename).stat().st_size != m.file_size)]
    if missing:
        raise RuntimeError(f"{z.name}: {len(missing)} file(s) didn't extract whole, e.g. {missing[:3]}")
    shutil.rmtree(out, ignore_errors=True)
    part.rename(out)


def download_licences(raw_dir: Path) -> None:
    for rel, url in LICENCE_URLS.items():
        fetch(url, raw_dir / "reference" / rel)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osha", action="store_true")
    ap.add_argument("--licences", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR)
    a = ap.parse_args()
    raw = a.data_dir / "raw"
    if a.osha:
        download_osha(raw)
    if a.licences:
        download_licences(raw)


if __name__ == "__main__":
    main()
