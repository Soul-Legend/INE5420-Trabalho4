# Personagem gerado com IA – registro do processo

Este diretório guarda o caminho real de geração do personagem, como evidência para os pontos extras de IA gerativa. O processo foi conduzido pelo assistente Claude (Anthropic), a pedido do grupo, por meio dos scripts abaixo. Os serviços de IA gerativa usados são públicos, no Hugging Face. **O relatório deve declarar isso.**

| Etapa | Ferramenta | Script | Saída |
| --- | --- | --- | --- |
| 1. Conceito 2D | Stable Diffusion 3.5 Large Turbo (Space `stabilityai/stable-diffusion-3.5-large-turbo`) | `gerar_conceito.py` | `conceito/conceito_seed*.png` + `conceito/registro.json` |
| 2. Recorte do fundo e atlas de textura | Python (máscara por preenchimento a partir da borda) | `textura_projecao.py` | `conceito/*_sem_fundo.png`, `textura/*_atlas.png`, `textura/*_bbox.json` |
| 3. Imagem → malha 3D | Hunyuan3D-2, modelo `hunyuan3d-dit-v2-0` (Space `tencent/Hunyuan3D-2`, `/shape_generation`) | `gerar_malha.py` | `malha/*.glb` + `malha/registro.json` |
| 4. Textura 3D por IA, **local** | Hunyuan3D-Paint (`hunyuan3d-delight-v2-0` + `hunyuan3d-paint-v2-0-turbo`), código oficial da Tencent, na Radeon RX 9070 XT | `texturizar_local.py` (+ `local/`) | `malha/conceito_seed5420_texturizada_local.glb` |
| 5. Limpeza e encaixe no esqueleto da captura | Blender 5.3 (pesos automáticos, *bone heat*) | `../blender/rig_personagem.py` | `../game/assets/personagem.glb`, `../blender/personagem.blend` |

As imagens de cada etapa estão em `etapas/`.

## Tema

Robô inspirado nas bruxas do imaginário de Franklin Cascaes, como sugere a página de IA da disciplina: xale de pescadora açoriana, chapéu de palha, máscara de madeira, peças de cobre e cerâmica. A pose T com as pernas separadas é exigência técnica: o esqueleto das capturas da turma está em pose T, e pernas separadas permitem pesos limpos.

## Linha do tempo

1. **21/11, 23:27 – Conceitos (Stable Diffusion 3.5).** Foram geradas 3 imagens (sementes 11, 2026 e 5420; `etapas/1_conceitos_sd35.png`). A semente 5420 foi escolhida por estar em pose T, de corpo inteiro, com fundo claro. A semente 777 não foi gerada porque a cota anônima de GPU acabou. O grupo então criou uma conta gratuita no Hugging Face.
2. **23:43 – Malha, 1ª tentativa** (remoção de fundo do próprio Hunyuan3D, resolução 256). A malha saiu **sem os braços**: os braços mecânicos finos foram apagados junto com o fundo (`etapas/2a_...`).
3. **23:44 – 2ª tentativa** (sem remoção de fundo, resolução 384). Os braços apareceram, mas a borda da imagem virou uma **moldura** colada no personagem (`etapas/2b_...`).
4. **Tentativa de textura com o Hunyuan3D.** A textura do Hunyuan3D-2 está desativada no Space público (erro `texgen_worker is not defined`), e o Hunyuan3D-2.1 pede 270 s de GPU, mais que a cota gratuita diária (266 s). Solução adotada: a textura passou a ser **a própria imagem do Stable Diffusion, projetada de frente** (`textura_projecao.py`). As faces voltadas para trás usam uma versão desfocada, para o rosto não aparecer na nuca (`etapas/3_atlas_textura.png`).
5. **23:56 – 3ª tentativa.** O fundo foi recortado pela nossa própria máscara e a imagem foi enviada com fundo transparente, sem a remoção do Hunyuan3D. Saíram braços e nenhuma moldura, mas a sombra no chão virou uma placa sob os pés. A máscara foi corrigida para tratar essa sombra como fundo, e o arquivo `conceito_seed5420_sem_fundo.png` foi **substituído** pela versão corrigida. A malha `malha/conceito_seed5420_sem_fundo_rgba_384.glb` corresponde à versão anterior, com sombra, que não foi guardada.
6. **22/11, 00:05 – 4ª tentativa (final).** A mesma imagem, agora sem sombra, gerou uma malha limpa, com braços, sem moldura e sem placa (`etapas/2c_...`).
7. **00:06 – Encaixe no Blender.** A malha foi limpa (14 vértices soltos removidos), recebeu a textura projetada, foi escalada pela envergadura dos braços (×1,14), reduzida para 40 mil triângulos e ligada ao esqueleto de 28 ossos da captura com pesos automáticos, que alcançaram todos os 19.952 vértices (`etapas/4_...`).
8. **No jogo (Godot).** O personagem anda, corre e coleta moedas com as animações das capturas da turma. Os 17 testes automáticos passam (`etapas/5_personagem_no_jogo.png`).
9. **00:54 – Textura por IA rodando no computador do grupo.** A textura projetada (passo 4) era uma solução provisória. A textura definitiva foi gerada pelo próprio **Hunyuan3D-Paint**, com o código oficial da Tencent, rodando localmente na Radeon RX 9070 XT. Foram usados o PyTorch oficial da AMD para Windows (`torch 2.15.0+rocm10.2.0`) e os pesos oficiais do Hugging Face (18 GB, no disco D:). O pipeline remove luz e sombra da imagem, gera 6 vistas do personagem condicionadas pela geometria e projeta essas vistas de volta na malha, em uma textura de 2048 px. A malha foi reduzida de 498.400 para 40.000 faces (pelo redutor do próprio Hunyuan3D). A geração levou 313 s, com pico de 11,5 GiB de memória de vídeo (`etapas/6_...`). Duas adaptações foram necessárias, ambas fora do código da Tencent (pasta `local/`):
   - O rasterizador `custom_rasterizer` é uma extensão CUDA/C++ que não compila com o PyTorch ROCm no Windows. Ele foi reescrito em PyTorch, com a mesma interface, e verificado contra uma transcrição linha a linha do C++ original: índice de face idêntico em 100% dos pixels, na CPU e na GPU (`local/test_rasterizer.py`).
   - Sem *flash attention*, a atenção entre as 6 vistas (24.576 posições) materializaria matrizes de vários GiB. O *flash attention* experimental do ROCm (`TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1`) foi conferido contra a atenção exata antes do uso (diferença máxima de 0,00024 em meia precisão; `local/test_sdpa.py`) e permitiu manter a resolução original de 512 px por vista.
10. **00:55 – Personagem final.** A malha texturizada foi ligada ao esqueleto (pesos automáticos em 19.952 de 19.952 vértices) e testada no jogo (`etapas/7_...`, `etapas/8_...`).

## Como reproduzir

```powershell
# (uma vez) token gratuito do Hugging Face, salvo localmente (só para as etapas 1 e 3, no Hugging Face)
python -m uv tool run --from huggingface_hub hf auth login

python -m uv run --no-project --with gradio_client --with huggingface_hub python ia\gerar_conceito.py
python -m uv run --no-project --with pillow --with numpy --with scipy python ia\textura_projecao.py ia\conceito\conceito_seed5420.png
python -m uv run --no-project --with gradio_client --with huggingface_hub python ia\gerar_malha.py ia\conceito\conceito_seed5420_sem_fundo.png rgba_384_sem_sombra check_box_rembg=0 octree_resolution=384
D:\Programs\blender-5.3.0-windows-x64\blender.exe -b blender\manequim.blend -P blender\rig_personagem.py -- ia\malha\conceito_seed5420_sem_fundo_rgba_384_sem_sombra.glb --texture ia\textura\conceito_seed5420_atlas.png
```

## Rodar a textura localmente

Requisitos já instalados nesta máquina, em `D:\Programs\hy3d`: ambiente Python 3.12 com o PyTorch ROCm da AMD, o repositório oficial `Tencent-Hunyuan/Hunyuan3D-2`, os pesos em `hf\` e o rasterizador em PyTorch em `compat\` (cópia em `ia/local/`).

```powershell
D:\Programs\hy3d\.venv\Scripts\python.exe ia\texturizar_local.py ia\malha\conceito_seed5420_sem_fundo_rgba_384_sem_sombra.glb ia\conceito\conceito_seed5420_sem_fundo.png ia\malha\conceito_seed5420_texturizada_local.glb
D:\Programs\blender-5.3.0-windows-x64\blender.exe -b blender\manequim.blend -P blender\rig_personagem.py -- ia\malha\conceito_seed5420_texturizada_local.glb
```

## Limitações

- O Windows reinicia a GPU quando uma operação passa de 2 s (TDR). A geração local terminou sem reinício e o resultado foi conferido visualmente, mas aumentar esse limite (`TdrDelay`, exige administrador e reinicialização) deixaria execuções futuras mais seguras.
- A projeção da imagem 2D (`textura_projecao.py`) continua disponível como alternativa, mas não é mais usada.
