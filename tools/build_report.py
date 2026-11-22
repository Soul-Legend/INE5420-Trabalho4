"""Prints docs/relatorio/trabalho-4.html to docs/relatorio-trabalho-4.pdf (headless Chrome/Edge).

Run: python tools/build_report.py
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "docs" / "relatorio" / "trabalho-4.html"
PDF = ROOT / "docs" / "relatorio-trabalho-4.pdf"
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome",
    "chromium",
)

browser = next((b for b in BROWSERS if Path(b).exists() or shutil.which(b)), None)
if browser is None:
    raise SystemExit("Chrome/Edge não encontrado para gerar o PDF.")
subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                "--allow-file-access-from-files", f"--print-to-pdf={PDF}", HTML.resolve().as_uri()],
               check=True, capture_output=True)
print(PDF)
