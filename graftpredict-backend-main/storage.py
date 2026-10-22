import os
import config
from pathlib import Path

UPLOAD_DIR = Path(os.path.join(os.path.dirname(__file__), "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_pdf(report_id: int, data: bytes) -> str:
    """Save PDF bytes to uploads/ and return relative path."""
    filename = f"report_{report_id}.pdf"
    path = UPLOAD_DIR / filename
    with open(path, "wb") as f:
        f.write(data)
    return str(path)


def delete_pdf(report_id: int) -> bool:
    path = UPLOAD_DIR / f"report_{report_id}.pdf"
    try:
        if path.exists():
            path.unlink()
            return True
    except Exception:
        pass
    return False
