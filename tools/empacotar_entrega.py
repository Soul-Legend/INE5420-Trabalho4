"""Builds the deliverable, split by the 100 MB upload limit.

- dist/INE5420_Grupo23_Trabalho4.zip (see entrega/LEIA-ME.md): report PDF,
  Windows executable, the Google Drive link file and the source code (Godot
  project, Blender scripts, tools and the AI generation record).
  Intermediate AI meshes and .blend files stay out.
- dist/para_o_drive/: the demo videos and the Linux executable, to upload to
  the Google Drive folder named in "entrega/links videos demo.txt".

Run: python tools/empacotar_entrega.py
"""

import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "INE5420_Grupo23_Trabalho4"
OUT = ROOT / "dist" / f"{NAME}.zip"
DRIVE = ROOT / "dist" / "para_o_drive"
LIMIT_MB = 100

# (source relative to ROOT, path inside the zip)
FILES = [
    ("entrega/LEIA-ME.md", "LEIA-ME.md"),
    ("docs/relatorio-trabalho-4.pdf", "relatorio-trabalho-4.pdf"),
    ("entrega/links videos demo.txt", "links videos demo.txt"),
    ("builds/windows/FortalezaEmMovimento.exe", "executaveis/windows/FortalezaEmMovimento.exe"),
    ("README.md", "codigo/README.md"),
    ("ia/malha/registro.json", "codigo/ia/malha/registro.json"),
    ("ia/malha/conceito_seed5420_texturizada_local.glb", "codigo/ia/malha/conceito_seed5420_texturizada_local.glb"),
]
# (directory relative to ROOT, glob patterns) copied to codigo/<directory>
TREES = [
    ("game", ["project.godot", "export_presets.cfg", "assets/*", "scenes/*", "scripts/*", "tests/*"]),
    ("blender", ["*.py"]),
    ("tools", ["*.py"]),
    ("ia", ["*.py", "README.md", "local/*.py", "conceito/*", "etapas/*", "textura/*"]),
]
# Too big for the zip: uploaded to Google Drive instead.
DRIVE_FILES = [
    "docs/videos/demo_wasd_animacao_procedural.mp4",
    "docs/videos/demo_mocap_sequencia_completa.mp4",
    "docs/videos/demo_mocap_sem_tratamento.mp4",
    "builds/linux/FortalezaEmMovimento.x86_64",
]
STORED = {".png", ".glb", ".pdf"}  # already compressed


def entries():
    for src, dst in FILES:
        yield ROOT / src, dst
    for folder, patterns in TREES:
        for pattern in patterns:
            for path in sorted((ROOT / folder).glob(pattern)):
                if path.is_file():
                    yield path, f"codigo/{path.relative_to(ROOT).as_posix()}"


def main():
    OUT.parent.mkdir(exist_ok=True)
    seen = set()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path, arc in entries():
            if arc in seen:
                continue
            seen.add(arc)
            info = zipfile.ZipInfo.from_file(path, f"{NAME}/{arc}")
            info.compress_type = zipfile.ZIP_STORED if path.suffix in STORED else zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | 0o644) << 16
            info.create_system = 3  # unix, so the permission bits are honoured
            with open(path, "rb") as f:
                z.writestr(info, f.read(), compresslevel=9 if info.compress_type else None)
    size_mb = OUT.stat().st_size / 2**20
    print(OUT, len(seen), "arquivos", round(size_mb, 1), "MB")

    shutil.rmtree(DRIVE, ignore_errors=True)
    DRIVE.mkdir()
    for src in DRIVE_FILES:
        shutil.copy2(ROOT / src, DRIVE)
        print(DRIVE / Path(src).name)
    if size_mb >= LIMIT_MB:
        sys.exit(f"ERRO: o zip passou do limite de {LIMIT_MB} MB")


if __name__ == "__main__":
    main()
