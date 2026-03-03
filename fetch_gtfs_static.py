from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

GTFS_LATEST_URL = "https://www.riderta.com/sites/default/files/gtfs/latest/google_transit.zip"

@dataclass(frozen=True)
class FetchResult:
    zip_path: Path
    extract_dir: Path
    sha256: str

def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    req = urllib.request.Request(url, headers={"User-Agent": "gtfs-fetch/1.0"})
    with urllib.request.urlopen(req) as r, tmp.open("wb") as f:
        shutil.copyfileobj(r, f)

    tmp.replace(dest)

def extract_zip(zip_path: Path, extract_dir: Path) -> None:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

def fetch_gtfs_latest(
    data_root: Path,
    url: str = GTFS_LATEST_URL,
    force: bool = False,
) -> FetchResult:
    """
    Fetches the GTFS 'latest' zip and extracts it.
    Stores:
      - zip:      data/raw/google_transit.zip
      - extract:  data/raw/gtfs/
      - metadata: data/raw/gtfs_meta.json
    """
    raw_dir = data_root / "raw"
    zip_path = raw_dir / "google_transit.zip"
    extract_dir = raw_dir / "gtfs"
    meta_path = raw_dir / "gtfs_meta.json"

    # If already present and not forcing, skip download but still ensure extract exists.
    if force or not zip_path.exists():
        download_file(url, zip_path)

    digest = sha256_file(zip_path)

    # Extract if missing or force
    if force or not extract_dir.exists():
        extract_zip(zip_path, extract_dir)

    meta = {
        "url": url,
        "downloaded_at_epoch": int(time.time()),
        "zip_path": str(zip_path.as_posix()),
        "extract_dir": str(extract_dir.as_posix()),
        "zip_sha256": digest,
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    return FetchResult(zip_path=zip_path, extract_dir=extract_dir, sha256=digest)

if __name__ == "__main__":
    data_root = Path("data").resolve()
    force_flag = "--force" in sys.argv

    res = fetch_gtfs_latest(data_root, force=force_flag)

    print(f"Saved zip: {res.zip_path}")
    print(f"Extracted: {res.extract_dir}")
    print(f"SHA256:    {res.sha256}")