# Trabalho 4 – Fortaleza em Movimento

INE5420 – Computação Gráfica – 2026/2 – Grupo 23.

Personagem modelado como um **modelo hierárquico** (esqueleto de 28 ossos da captura de movimentos da turma), com **duas versões de animação** misturadas pela velocidade em uma `AnimationTree` do Godot: ciclos **procedurais** com cinemática inversa nas pernas (padrão) e clipes da **captura da turma**. **Tab** alterna entre elas. O jogador anda (WASD) e corre (Shift) dentro de uma fortaleza inspirada em Anhatomirim e coleta moedas. Uma cena automática (`--mocap-show`) reproduz as 8 tomadas completas da captura (8 min 57 s) sem controle do jogador.

**Vídeos:** `docs/videos/demo_wasd_animacao_procedural.mp4` (26 s), `docs/videos/demo_mocap_sequencia_completa.mp4` (8 min 57 s) e, por curiosidade, `docs/videos/demo_mocap_sem_tratamento.mp4` (18 s: a mesma caminhada da captura usada direto, sem tratamento, ao lado do clipe tratado; cena `--raw-compare`, clipe gerado por `blender/bake_raw_clip.py`). **Relatório:** `docs/relatorio-trabalho-4.pdf`. **Executáveis (64 bits):** `builds/windows/FortalezaEmMovimento.exe` e `builds/linux/FortalezaEmMovimento.x86_64`.

> Estado em 22/11/2026: o personagem é um **robô-bruxa gerado com IA** (Stable Diffusion 3.5 → forma no Hunyuan3D-2 → textura com Hunyuan3D-Paint rodando localmente na RX 9070 XT), ligado ao esqueleto da captura com pesos automáticos no Blender. O processo completo, com as imagens de cada etapa, está em `ia/README.md`. O manequim rígido (`game/assets/manequim.glb`) é usado se `personagem.glb` não existir.

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `blender/build_character.py` | Gera os clipes em loop a partir das capturas, o esqueleto limpo, o manequim e exporta `game/assets/manequim.glb` e `clips.json` |
| `blender/procedural_gait.py` | Animações procedurais `idle_pro`, `walk_pro`, `run_pro` (IK de 2 ossos, pés sem deslizar) |
| `blender/bake_mocap_full.py` | Converte as 8 tomadas completas da captura para o personagem, com o deslocamento original |
| `blender/bake_raw_clip.py` | Curiosidade: um trecho de caminhada da captura sem nenhum tratamento (`walk_raw`), para a cena `--raw-compare` |
| `blender/rig_personagem.py` | Limpa a malha gerada por IA, projeta a textura, escala para o esqueleto, aplica pesos automáticos e exporta `game/assets/personagem.glb` |
| `ia/` | Personagem gerado com IA: scripts, imagens, malhas e registro de cada etapa |
| `game/` | Projeto Godot 4.7 (`scripts/player.gd`, `camera_rig.gd`, `fortress.gd`, `coin.gd`, `main.gd`) |
| `game/tests/smoke_test.gd` | 35 verificações automáticas: clipes das duas versões (inclusive duração), tomadas completas, esqueleto, mistura, velocidades, Tab, moedas |
| `tools/gravar_videos.py`, `tools/build_report.py` | Gravação dos vídeos (Godot + ffmpeg) e geração do PDF |
| `tools/` | Análise das capturas (trechos de caminhada e corrida, bonecos de palito) |
| `docs/` | Figuras das capturas, prints e vídeo de demonstração |

## Como executar

Ferramentas portáteis (já instaladas nesta máquina): Blender 5.3 em `D:\Programs\blender-5.3.0-windows-x64` e Godot 4.7.2 em `D:\Programs\godot-4.7.2`.

```powershell
# 1. Gerar personagem e animações a partir das capturas (~2,5 min)
D:\Programs\blender-5.3.0-windows-x64\blender.exe -b --factory-startup -P blender\build_character.py

# 2. Abrir o jogo no editor do Godot
D:\Programs\godot-4.7.2\Godot_v4.7.2-stable_win64.exe --path game -e

# 3. Jogar direto
D:\Programs\godot-4.7.2\Godot_v4.7.2-stable_win64.exe --path game

# 4. Testes automáticos (sem janela)
D:\Programs\godot-4.7.2\Godot_v4.7.2-stable_win64_console.exe --headless --path game -s res://tests/smoke_test.gd

# 5. Tour automático gravando vídeo e prints
D:\Programs\godot-4.7.2\Godot_v4.7.2-stable_win64_console.exe --path game --write-movie ..\docs\demo.avi --fixed-fps 30 --quit-after 540 -- --demo --screenshots=..\docs\images
```

## Clipes extraídos das capturas

| Clipe | Origem | Duração | Velocidade medida |
| --- | --- | --- | --- |
| parado | `Movimentos02.fbx`, 20,1–22,1 s | 2,0 s | — |
| andar | `Movimentos02.fbx`, 61,2–63,8 s | 2,6 s | 0,99 m/s |
| correr | `Movimentos04.fbx`, 2,6–3,2 s | 0,53 s (um ciclo) | 1,36 m/s |

O script escolhe automaticamente, em cada trecho candidato, o par de quadros com poses mais parecidas (soma das diferenças de ângulo das articulações, mais penalidades por curva e mudança de direção). Em seguida, remove o deslocamento horizontal e o giro do quadril (animação "no lugar") e distribui o pequeno erro restante ao longo do clipe para o loop fechar sem tranco. O controlador do Godot desloca o personagem exatamente à velocidade medida, multiplicada pelo mesmo fator que acelera a animação, por isso os pés não deslizam.
