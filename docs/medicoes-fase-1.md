# Medicoes da Fase 1

Feitas em 20/10/2026 no PC do Matheus (RTX 3060 12 GB), Ollama 0.40.5, com a Jarvis
instalada pelo `iniciar.bat`. Nenhum jogo aberto; o navegador estava aberto (a linha de
base de memoria de video e 1007 a 1274 MiB). Saidas brutas em `docs/medicoes-brutas/`.

## 1. Cenarios, modelo padrao (gemma4:12b-it-q4_K_M)

Comando: `python -m jarvis_pc.cenarios gemma4:12b-it-q4_K_M`, tres rodadas.

| Rodada | Passaram | Tempo por cenario |
|---|---|---|
| 1 | 8 de 8 | 4,1 a 13,4 s |
| 2 | 8 de 8 | 4,1 a 8,1 s |
| 3 | 8 de 8 | 4,2 a 8,9 s |

Total 24 de 24, nenhum "nao leu". Primeira pergunta de todas (modelo frio): cerca de 80 s.

## 2. Cenarios, modelo menor (gemma4:e4b-it-q4_K_M, 6,6 GB)

| Rodada | Passaram | Falhas |
|---|---|---|
| 1 | 7 de 8 | inicializacao: terminou sem resposta |
| 2 | 6 de 8 | pc_lento e inicializacao: terminou sem resposta |
| 3 | 7 de 8 | inicializacao: terminou sem resposta |

Total 20 de 24. O cenario `inicializacao` falhou nas tres rodadas. O `pc_lento` levou ate
63,7 s numa rodada.

## 3. Memoria de video (12b)

| Momento | Usada |
|---|---|
| Sem modelo (linha de base) | 1274 MiB |
| 12b carregado (contexto 16384, 100% GPU) | 10317 de 12288 MiB |
| 5 a 11 minutos ocioso (descarregado) | 1007 MiB |

Com o 12b carregado sobram menos de 2 GB: um jogo pesado nao convive. Depois de 5 minutos
parado o Ollama descarrega o modelo e a memoria volta.

## 4. Velocidade no processador (e4b, num_gpu=0)

23,6 tokens/s (618 tokens), carga de 6 s. Memoria de video antes 1007 MiB (com o e4b
ainda na GPU: 6106 MiB) e depois 1007 MiB: o modo processador nao ocupa a GPU.
Ressalva: medido com o PC ocioso; um jogo rodando disputa o processador.

## 5. OCR do Windows

Duas rodadas: lido `Erro Ox80070005: acesso negado ao arquivo do jogo`, esperado
`0x80070005`. Mesma troca de `0` por `O` de 19/10.

## Decisoes

1. **Modelo padrao: continua o gemma4:12b-it-q4_K_M.** Passou 24 de 24 contra 20 de 24 do
   e4b, sem "nao leu". Nada a trocar em `config.py` nem no instalador.
2. **Modo jogo: viavel com o e4b no processador.** A memoria de video nao sobe e 23,6
   tokens/s esta acima do limite de 5. Nao esta provado com um jogo aberto. O 12b na GPU
   nao convive com jogo pesado: durante o jogo, usar o e4b no processador (ou o Claude).
3. **OCR: usar com conferencia do codigo de erro.** Le o portugues, erra o `0` do codigo.
