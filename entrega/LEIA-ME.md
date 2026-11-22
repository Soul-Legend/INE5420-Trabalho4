# Trabalho 4.0 – Modelos Hierárquicos com Captura de Movimentos

**INE5420 – Computação Gráfica – UFSC – 2026/2 – Grupo 23**

- Cristian Alexandre Alchini (20100519)
- Lucas Cardoso Soares (22100631)
- Pedro Henrique De Sena Trombini Taglialenha (22203674)

O trabalho é o jogo **Fortaleza em Movimento**, feito em Godot 4.7. Nele, um personagem modelado como um modelo hierárquico (o esqueleto de 28 ossos das capturas da turma) anda e corre pelo pátio de uma fortaleza e coleta moedas. O personagem tem duas versões de animação, que podem ser trocadas durante o jogo:

- **procedural** (padrão): ciclos de parado, andar e correr calculados matematicamente, com cinemática inversa nas pernas;
- **captura da turma**: clipes de parado, andar e correr recortados das capturas e ajustados para repetir sem emenda.

Há também uma cena automática que reproduz as 8 tomadas completas da captura, sem controle do jogador. O personagem (um robô-bruxa) foi gerado com IA; o processo está documentado no relatório (Seção 6) e em `codigo/ia/README.md`.

## O que tem no zip

| Caminho | Conteúdo |
| --- | --- |
| `relatorio-trabalho-4.pdf` | Relatório em formato de artigo: fundamentação, método, progresso e dificuldades, resultados, declaração do uso de IA e limitações |
| `executaveis/windows/FortalezaEmMovimento.exe` | Jogo para Windows 64 bits (arquivo único, dados embutidos) |
| `executaveis/linux/FortalezaEmMovimento.x86_64` | Jogo para Linux 64 bits (arquivo único, dados embutidos) |
| `videos/demo_wasd_animacao_procedural.mp4` | 26 s: sessão de jogo com WASD e Shift simulados, animação procedural |
| `videos/demo_mocap_sequencia_completa.mp4` | 8 min 57 s: as 8 tomadas completas da captura da turma, sem controle do jogador |
| `videos/demo_mocap_sem_tratamento.mp4` | 18 s: curiosidade, a mesma caminhada da captura usada sem tratamento, ao lado da versão tratada |
| `codigo/game/` | Projeto Godot 4.7 completo (cenas, scripts, personagem, animações e testes) |
| `codigo/blender/` | Scripts do Blender que geram o esqueleto, os clipes da captura, as animações procedurais e o encaixe do personagem |
| `codigo/tools/` | Análise das capturas, renders de verificação, gravação dos vídeos e geração do PDF |
| `codigo/ia/` | Geração do personagem com IA: scripts, imagens de cada etapa, registro com prompts e parâmetros, malha final texturizada |
| `codigo/README.md` | Descrição técnica do código e de como regerar cada parte |

## Como jogar

**Windows:** execute `executaveis/windows/FortalezaEmMovimento.exe`.

**Linux:** dê permissão de execução, se o descompactador não a preservar, e execute:

```sh
chmod +x executaveis/linux/FortalezaEmMovimento.x86_64
./executaveis/linux/FortalezaEmMovimento.x86_64
```

| Tecla | Ação |
| --- | --- |
| W, A, S, D ou setas | Andar |
| Shift (segurando) | Correr |
| Tab | Alternar a animação entre procedural e captura da turma |
| Q / E, ou mouse depois de um clique | Girar a câmera (Esc solta o mouse) |

O painel no alto da tela mostra a versão de animação ativa, a velocidade e a porcentagem de parado, andar e correr na mistura.

### Cenas automáticas

As cenas dos vídeos podem ser abertas passando uma opção depois de `--` (o exemplo usa Windows; no Linux, troque o nome do arquivo):

```sh
FortalezaEmMovimento.exe -- --mocap-show     # as 8 tomadas completas da captura (cerca de 9 min)
FortalezaEmMovimento.exe -- --demo           # sessão WASD automática com a animação procedural
FortalezaEmMovimento.exe -- --raw-compare    # captura sem tratamento ao lado da tratada
```

## Como abrir o código

1. Instale o Godot 4.7 (versão padrão, sem .NET).
2. No Godot, importe `codigo/game/project.godot`. A cena principal é `scenes/main.tscn`.
3. Os testes automáticos (35 verificações) rodam com:

```sh
godot --headless --path codigo/game -s res://tests/smoke_test.gd
```

Os scripts de `codigo/blender/` rodam no Blender 5.3 em modo de linha de comando e leem as capturas da turma (arquivos FBX), que não estão no zip. Elas devem ficar numa pasta `capturas Aldo 2026.2` ao lado da pasta do projeto (constante `CAPTURES` em `codigo/blender/build_character.py`). Os arquivos do jogo gerados por eles já estão em `codigo/game/assets/`, então não é preciso rodá-los para jogar ou abrir o projeto.
