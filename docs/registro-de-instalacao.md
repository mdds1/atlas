# Registro de instalacao no PC

Data: 20/10/2026. PC do Matheus (RTX 3060 12 GB, Python 3.10.11).

| Item | Valor |
|---|---|
| Ollama | 0.40.5, instalado pelo winget sem elevacao |
| Modelo | gemma4:12b-it-q4_K_M, 8,0 GB |
| OpenJarvis | 1.0.5.dev144+g6ae98f0 |
| jarvis-pc | 0.1.0 |
| Espaco livre no C: | antes 340,2 GB, depois 325,4 GB |
| Pasta | C:\Jarvis (venv, config.json, iniciar.bat) |
| verificar | telemetria carregada: False, 8 de 8 leituras ok |

## Desvios do plano

1. O Ollama so abriu a janela do aplicativo; o servidor nao subiu. Um `ollama serve`
   iniciado por SSH morre quando a conexao fecha. O Matheus rodou `ollama serve`
   num PowerShell dele, que precisa ficar aberto enquanto a Jarvis for usada.
2. `windows/instalar.ps1` tinha um bug: a variavel local `$rodas` colidia com o
   parametro `$Rodas` (PowerShell ignora maiusculas) e o instalador achava 1 roda.
   Renomeada para `$listaRodas`.
3. `scripts/pc.py cmd` corta em 120 s. Instalador e `pull` do modelo precisam do
   modo `rodar` (1200 s). O `pull` terminou mesmo assim, no lado do PC.
4. Os acentos da saida do `verificar` aparecem quebrados no terminal do Linux
   (saida em codepage do Windows); nao afeta a Jarvis.
5. O `iniciar.bat` passou a subir o `ollama serve` escondido, na sessao de quem
   clicou, quando a porta 11434 nao responde. Assim nenhum terminal fica aberto.
6. O primeiro `iniciar.bat` passava `"%~dp0"` (termina em `\"`), o que o Windows le como
   aspa escapada: a pasta virava um caminho invalido e a partida falhava sem rastro.
   Trocado por `"%~dp0."`. Confirmado pelo `registro.jsonl` (evento `inicio`).
