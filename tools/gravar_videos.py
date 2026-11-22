"""Records the two demo videos with Godot's movie writer and converts them to MP4.

1. docs/videos/demo_wasd_animacao_procedural.mp4 - scripted WASD + Shift session
   with the procedural animations (andar/correr com IK), coins, HUD.
2. docs/videos/demo_mocap_sequencia_completa.mp4 - the complete class capture
   takes played by the character, with no player input.
3. docs/videos/demo_mocap_sem_tratamento.mp4 - curiosity: one capture clip used
   raw, side by side with the treated clip.

Run: uv run --no-project --with imageio-ffmpeg python tools/gravar_videos.py [wasd|mocap|raw|all]
"""

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
GODOT = r"D:\Programs\godot-4.7.2\Godot_v4.7.2-stable_win64_console.exe"
OUT = ROOT / "docs" / "videos"
TMP = Path(r"D:\Programs\hy3d\tmp")

DEMOS = {
    "wasd": ("demo_wasd_animacao_procedural", ["--demo", f"--screenshots={ROOT / 'docs' / 'images'}"], 780),
    "mocap": ("demo_mocap_sequencia_completa", ["--mocap-show"], 30 * 60 * 12),
    "raw": ("demo_mocap_sem_tratamento", ["--raw-compare", f"--screenshots={TMP / 'raw_shots'}"], 30 * 25),
}


def record(key):
    name, args, max_frames = DEMOS[key]
    avi = TMP / f"{name}.avi"
    mp4 = OUT / f"{name}.mp4"
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    subprocess.run([GODOT, "--path", str(ROOT / "game"), "--write-movie", str(avi), "--fixed-fps", "30",
                    "--quit-after", str(max_frames), "--", *args], check=True)
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(avi),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-an", str(mp4)], check=True)
    avi.unlink()
    print(mp4, round(mp4.stat().st_size / 2**20, 1), "MB")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for key in (DEMOS if which == "all" else [which]):
        record(key)
