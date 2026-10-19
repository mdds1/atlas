# Jarvis do PC

Assistente de diagnóstico para o PC Windows do Matheus, sobre o OpenJarvis.
Roda só quando ele chama. Lê o PC sozinha; qualquer mudança só com Sim dele.
O desenho está em `docs/superpowers/specs/2026-10-15-jarvis-design.md`.

## Como é feito

| Arquivo | O que faz |
|---|---|
| `src/jarvis_pc/trava.py` | Lista de bloqueio em código: o que a Jarvis nunca executa |
| `src/jarvis_pc/ps.py` | Roda PowerShell e devolve o resultado sem levantar erro |
| `src/jarvis_pc/leitura.py` e `ps/*.ps1` | As 8 ferramentas de leitura do PC |
| `src/jarvis_pc/comando.py` | A ferramenta que altera o PC, com trava e confirmação |
| `src/jarvis_pc/agente.py` | Monta o agente do OpenJarvis com tudo acima |
| `src/jarvis_pc/ponte.py` e `janela.py` | Confirmação Sim e Não e a janela com atalho |
| `src/jarvis_pc/cenarios.py` | Medição do modelo contra cenários fixos |
| `src/jarvis_pc/verificar.py` | Confere no PC a telemetria fora e as 8 leituras |

## Desenvolvimento (na bancada)

```
python3 -m venv .venv
.venv/bin/pip install "OpenJarvis @ git+https://github.com/open-jarvis/OpenJarvis.git@$(cat OPENJARVIS-COMMIT.txt)"
.venv/bin/pip install -e .
.venv/bin/python -B -m unittest discover -s tests -q
.venv/bin/python tools/mutacoes_trava.py   # sabota cada palavra bloqueada
.venv/bin/python tools/mutacoes.py         # sabota os pontos de segurança
```

Toda mudança em código de segurança só vale depois de as duas ferramentas de
sabotagem acusarem zero escapes.

## No PC

`windows/instalar.ps1` e `windows/desinstalar.ps1`. A instalação cria só a pasta
`C:\Jarvis`. O Ollama é instalado à parte, pelo winget.
