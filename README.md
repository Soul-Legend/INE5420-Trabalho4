# Trabalho 4 – Fortaleza em Movimento

INE5420 – Computação Gráfica – UFSC – 2026/2 – Grupo 23: Cristian Alexandre Alchini, Lucas Cardoso Soares e Pedro Henrique De Sena Trombini Taglialenha.

Personagem modelado como um **modelo hierárquico** (o esqueleto de 28 ossos das capturas de movimento da turma), com **duas versões de animação** misturadas pela velocidade em uma `AnimationTree` do Godot: ciclos **procedurais** com cinemática inversa nas pernas (padrão) e clipes da **captura da turma**. **Tab** alterna entre elas. O jogador anda (WASD) e corre (Shift) dentro de uma fortaleza inspirada em Anhatomirim e coleta moedas. Uma cena automática (`--mocap-show`) reproduz as 8 tomadas completas da captura (8 min 57 s) sem controle do jogador.

O personagem é um **robô-bruxa gerado com IA** (Stable Diffusion 3.5 → forma no Hunyuan3D-2 → textura com Hunyuan3D-Paint executado localmente numa GPU AMD), ligado ao esqueleto da captura com pesos automáticos no Blender. O processo completo, com as imagens de cada etapa, está em `ia/README.md`.

**Relatório:** `docs/relatorio-trabalho-4.pdf`. **Vídeos curtos:** `docs/videos/demo_wasd_animacao_procedural.mp4` (26 s) e `docs/videos/demo_mocap_sem_tratamento.mp4` (18 s).

**Vídeos de demonstração e executável Linux (Google Drive):** https://drive.google.com/drive/folders/1dgt56__DUrvMx2SWGJ8syuFKvYADoYan?usp=sharing

## Entrega e arquivos grandes

Os arquivos grandes **não estão no git**: os executáveis (`builds/`, 121 MB e 86 MB), o vídeo da sequência completa da captura (`docs/videos/demo_mocap_sequencia_completa.mp4`, 107 MB) e o `blender/personagem.blend` (51 MB). O envio tem limite de 100 MB, então a entrega fica dividida em duas partes, geradas por:

```sh
python tools/empacotar_entrega.py
```

- `dist/INE5420_Grupo23_Trabalho4.zip` (cerca de 84 MB): relatório, executável Windows, código e `links videos demo.txt`. O conteúdo está descrito em `entrega/LEIA-ME.md`, que vai na raiz do zip;
- `dist/para_o_drive/`: os três vídeos e o executável Linux, para subir na pasta do Google Drive (https://drive.google.com/drive/folders/1dgt56__DUrvMx2SWGJ8syuFKvYADoYan?usp=sharing).

O `.blend` é regenerado pelos scripts do Blender.

## Estrutura

| Caminho | Conteúdo |
| --- | --- |
| `blender/build_character.py` | Lê as capturas, monta o esqueleto limpo e o manequim, gera os clipes de parado, andar e correr em loop e exporta `game/assets/manequim.glb` e `clips.json` |
| `blender/procedural_gait.py` | Animações procedurais `idle_pro`, `walk_pro` e `run_pro` (IK de 2 ossos, pés sem deslizar) |
| `blender/bake_mocap_full.py` | Converte as 8 tomadas completas da captura para o personagem, com o deslocamento original |
| `blender/bake_raw_clip.py` | Curiosidade: um trecho de caminhada da captura sem nenhum tratamento (`walk_raw`), para a cena `--raw-compare` |
| `blender/rig_personagem.py` | Limpa a malha gerada por IA, escala para o esqueleto, aplica pesos automáticos e exporta `game/assets/personagem.glb` |
| `ia/` | Personagem gerado com IA: scripts, imagens, malhas e registro de cada etapa |
| `game/` | Projeto Godot 4.7: `scripts/player.gd` (controle e mistura), `camera_rig.gd`, `fortress.gd`, `coin.gd`, `main.gd`, `mocap_show.gd`, `raw_compare.gd` |
| `game/tests/smoke_test.gd` | 35 verificações automáticas: clipes das duas versões (inclusive duração), tomadas completas, esqueleto, mistura, velocidades, Tab e moedas |
| `tools/` | Análise das capturas, renders de verificação, gravação dos vídeos, geração do PDF e empacotamento da entrega |
| `docs/` | Relatório (HTML, figuras e PDF), figuras das capturas, prints e vídeos curtos |
| `entrega/LEIA-ME.md` | LEIA-ME do zip de entrega |

## Como executar

Ferramentas: Blender 5.3 e Godot 4.7 (versão padrão, sem .NET). As capturas da turma devem estar na pasta `capturas Aldo 2026.2`, ao lado desta pasta (constante `CAPTURES` em `blender/build_character.py`). Os arquivos gerados pelos scripts do Blender já estão em `game/assets/`, então os passos 1 a 3 só são necessários para regerá-los.

```sh
# 1. Esqueleto, manequim e clipes da captura
blender -b --factory-startup -P blender/build_character.py
# 2. Personagem gerado por IA no esqueleto (cria blender/personagem.blend)
blender -b blender/manequim.blend -P blender/rig_personagem.py -- ia/malha/conceito_seed5420_texturizada_local.glb
# 3. Animações procedurais, tomadas completas e clipe sem tratamento (o último exporta o .glb do jogo)
blender -b blender/personagem.blend -P blender/procedural_gait.py
blender -b blender/personagem.blend -P blender/bake_mocap_full.py
blender -b blender/personagem.blend -P blender/bake_raw_clip.py -- --export game/assets/personagem.glb

# Jogar / abrir o editor
godot --path game
godot --path game -e

# Testes automáticos (sem janela)
godot --headless --path game -s res://tests/smoke_test.gd

# Cenas automáticas (opções depois de "--")
godot --path game -- --mocap-show
godot --path game -- --demo
godot --path game -- --raw-compare

# Vídeos (Godot movie writer + ffmpeg) e PDF do relatório
python tools/gravar_videos.py [wasd|mocap|raw|all]
python tools/build_report.py
```

O caminho do Godot usado por `tools/gravar_videos.py` fica na constante `GODOT`, no início do arquivo.

## Clipes extraídos das capturas

| Clipe | Origem | Duração | Velocidade medida |
| --- | --- | --- | --- |
| parado | `Movimentos02.fbx`, 20,1–22,1 s | 2,0 s | — |
| andar | `Movimentos02.fbx`, 61,2–63,8 s | 2,6 s | 0,99 m/s |
| correr | `Movimentos06.fbx`, 19,6–21,1 s | 1,5 s | 1,86 m/s |

Em cada trecho candidato, o script escolhe o par de quadros com poses mais parecidas (soma das diferenças de ângulo das articulações), com penalidades por curva, por mudança de direção e por deslocamento fora da frente do corpo. Depois remove o deslocamento horizontal e o giro do quadril (animação "no lugar") e distribui o pequeno erro restante ao longo do clipe, para o loop fechar sem tranco. No jogo, os clipes da captura tocam 1,4 vez mais rápido, e o controlador desloca o personagem na velocidade medida multiplicada pelo mesmo fator, por isso os pés não deslizam. As versões procedurais andam a 1,35 m/s e correm a 2,8 m/s.
