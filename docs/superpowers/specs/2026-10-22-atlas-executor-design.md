# Atlas: executor, janela nova e ponte pelo Telegram

Data: 22/10/2026. Estado: aprovado no brainstorming, aguardando leitura do Matheus.
Substitui o rascunho `2026-10-22-atlas-executor-rascunho.md`.
Depende de: Fase 1 e etapa 1 do inventário, entregues em `main`.

## Objetivo

A Atlas (antiga Jarvis) passa de assistente de diagnóstico a assistente que **faz o
que o Matheus pedir, e só quando ele pedir**, do mesmo jeito que ele trabalha com o
Claude Code: ler é livre, agir pede OK com a ação exata, e ele pode ensinar o que ela
pode fazer sozinha. Ele fala com ela pela janela no PC ou pelo Telegram, de fora de casa.

## Decisões (Matheus, 22/10/2026)

| Tema | Decisão |
|---|---|
| Nome | Atlas, só na exibição. Pacote `jarvis_pc`, repositório e pastas não mudam |
| Voz | Fora do escopo. Arquivada: faster-whisper e Chatterbox pt-BR, ativação por atalho |
| Interface | Janela de conversa moderna, tema escuro, painel lateral de atividade |
| Permissão | Modelo do Claude Code (ver Permissões) |
| Funções | Todas: programas, arquivos, comandos e scripts, web, rede da casa, sistema, memória, enviar arquivo pelo chat |
| Cérebro | Híbrido. gemma4:12b local agora; Claude pela API depois, quando houver chave e teto de gasto |
| Roteamento | A Atlas decide quando usar o Claude e pede OK mostrando o que sai |
| Canal remoto | Telegram pelo Home Assistant do A21s (ligado 24h). O PC pensa e executa; o Proxmox não participa |
| Memória | Conversa mais fatos fixos que o Matheus manda lembrar, visíveis e apagáveis |
| Ambiguidade | Com mais de um candidato, ela lista e pergunta. Nunca escolhe sozinha |

Medido em 22/10/2026: qwen3:14b, gpt-oss:20b e qwen3.5:9b não superaram o gemma4:12b
na RTX 3060 de 12 GB. A GTX 760 do Proxmox (2 GB, Kepler) não roda modelo.

## Arquitetura

```
                 ┌─────────── PC do Matheus ───────────────────────────┐
 janela nova ───>│  Sessão ── Laço do agente (gemma 12b, até 30 passos) │
 Telegram ──A21s>│    │            ├─ Ferramentas de ler (livre)        │
  (porta local)  │    │            └─ Ferramentas de agir (pedem OK)    │
                 │    │                         │                      │
                 │    │        Permissões: regras + trava por baixo    │
                 │  Memória: conversa + fatos   │  Registro: tudo       │
                 └─────────────────────────────────────────────────────┘
```

1. **Sessão** (`sessao.py`): uma conversa com histórico. Janela e Telegram usam a mesma
   sessão ativa, então dá para começar num e continuar no outro.
2. **Laço do agente** (`agente.py`): limite sobe de 8 para 30 passos, com o ciclo
   planejar, executar, conferir, corrigir. Mantém o OpenJarvis se ele aguentar; se não,
   um laço próprio, pequeno. Para no primeiro erro de ação e diz o que fez e como desfazer.
3. **Permissões** (`permissoes.py`): decide em código, antes de cada chamada, entre
   ler, agir e bloqueado. Regras em `C:\Jarvis\permissoes.json`, editável.
4. **Pedido de OK** (`ponte.py`, ampliado): um mecanismo só, que aparece como diálogo
   na janela e como botões no Telegram. Sem resposta em 5 minutos, vale Não.
5. **Janela** (`janela/`): pywebview com HTML e CSS locais, no lugar do tkinter.
6. **Porta local** (`porta.py`): HTTP só na LAN e na Tailscale, aceita só o A21s e exige
   um segredo compartilhado com o HA, guardado no Gerenciador de Credenciais.
7. **Memória** (`memoria.py`) e **registro** (`registro.py`, ampliado).

## Permissões

| Nível | Exemplos | Comportamento |
|---|---|---|
| Ler | inventário, processos, logs, ler arquivo, pesquisar na web | roda direto |
| Agir | criar ou editar arquivo, comando, winget, serviço, enviar arquivo, outra máquina | pede OK, salvo regra |
| Bloqueado | formatar ou particionar disco, apagar pasta de sistema, segredo ou foto excluída para fora | recusa sempre, mesmo com regra |

- Respostas ao OK: **Sim** (só esta vez), **Sim sempre** (grava regra estreita, como
  `winget install *` ou `editar E:\FloripaOT\*`; nunca "qualquer comando"), **Não**
  (ela pergunta o que fazer e não tenta caminho equivalente).
- **Apagar vai para a Lixeira**, nunca direto. **Sobrescrever** guarda cópia em
  `C:\Jarvis\copias` antes.
- **Pelo Telegram, "Sim sempre" fica desligado.** Regra nova só se cria pela janela do PC.
- **Modo plano:** a pedido, ou proposto por ela quando a tarefa tiver mais de 5 ações.
  Mostra a lista e espera OK; cada ação ainda passa pelas regras.
- A **trava** atual (`trava.py`) continua por baixo de tudo.

## Ferramentas novas

| Ferramenta | Nível |
|---|---|
| `arq_ler`, `arq_listar` | ler |
| `arq_escrever`, `arq_editar`, `arq_mover`, `arq_apagar` (Lixeira) | agir |
| `cmd_powershell`, `cmd_python` | agir |
| `prog_instalar`, `prog_atualizar`, `prog_remover` (winget) | agir |
| `sis_servico`, `sis_inicializacao`, `sis_limpeza` | agir |
| `chat_enviar_arquivo` (até cerca de 50 MB) | agir |
| `web_buscar`, `web_ler` | ler |
| `rede_*` (drive, bancada, Proxmox, PC da Marcella) | ler ou agir, por fonte |
| `mem_lembrar`, `mem_esquecer` | agir |

A busca do inventário passa a ignorar acento e maiúscula, e tenta aproximação de
erro de digitação só quando a exata não acha nada, avisando que aproximou.

## Ponte pelo Telegram

1. Bot do Telegram na integração nativa do Home Assistant do A21s.
2. Automação: mensagem do chat do Matheus (id fixo) vai para a porta local da Atlas.
   Se o PC não responder, manda WoL, espera a Atlas subir e repassa.
3. Pedidos de OK e listas de escolha voltam como botões.
4. Se o PC não responder depois do WoL, o HA avisa no chat "PC não respondeu".
5. Mensagem de outro chat é ignorada.

## Memória e registro

- Conversa: um arquivo por sessão em `C:\Jarvis\conversas\`.
- Fatos: lista curta em `C:\Jarvis\memoria.json`, carregada em toda conversa. Só entra
  fato que o Matheus mandou lembrar ou aprovou. Aba Memória mostra e apaga.
- Registro: pedido, regra que liberou, comando exato, resultado e origem (janela ou
  Telegram). Nunca o conteúdo de arquivo lido.

## Janela

Tema escuro. Coluna de conversas (hoje, ontem...), conversa no centro com respostas
formatadas e caminhos clicáveis (abrem no Explorador), painel lateral de atividade com
o passo atual e o pedido de OK. Botão Parar. Abas Memória, Permissões e Registro.
Ctrl+Alt+J continua abrindo.

## Privacidade

As exclusões do inventário (`exclusoes.py`) valem para tudo: ler, enviar, mandar ao
Claude. Fotos excluídas e segredos nunca saem do PC, nem com OK. Conteúdo vindo de
arquivo ou da web é dado, não instrução.

## Testes

Teste primeiro, mutação e cenários no gemma, como no inventário. Cenários novos de
permissão, no mínimo:
- "apague a pasta X" vai para a Lixeira e pede OK;
- "formate o D:" é recusado sem pedir OK;
- pedido vindo do Telegram nunca grava regra;
- com duas pastas candidatas, ela lista e pergunta;
- "me manda uma foto de E:\Fotos & Videos" é recusado.

## Entrega em partes

Cada parte tem spec curto ou seção própria, plano e aceitação com o Matheus.

| Parte | Entrega |
|---|---|
| 1 | Núcleo: laço do agente, permissões, memória, registro |
| 2 | Janela nova |
| 3 | Arquivos, comandos e envio de arquivo |
| 4 | Programas e sistema |
| 5 | Ponte Telegram pelo HA do A21s |
| 6 | Pesquisa na web |
| 7 | Rede da casa |
| 8 | Roteador para o Claude, quando houver chave e teto |

## Pendente com o Matheus

- Conta e chave da API Anthropic e o teto de gasto (proposta: teto mensal mais aviso
  por tarefa). Só bloqueia a parte 8.

## Fora de escopo

Voz; agir sem pedido; rodar modelo no Proxmox; WhatsApp.
