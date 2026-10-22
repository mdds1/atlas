# Atlas: executor e interface (rascunho do brainstorming)

Data: 22/10/2026. Estado: decisoes em andamento, spec ainda nao escrito.

## Decidido pelo Matheus

1. Nome de exibicao: **Atlas**. Pacote interno continua `jarvis_pc`.
2. Voz fora do escopo por agora (arquivada: faster-whisper + Chatterbox pt-BR, so atalho).
3. Interface: **janela de conversa moderna**, com historico, respostas formatadas, tema escuro e painel ao lado mostrando o que ela esta fazendo.
4. Permissao **como o Claude Code**: ler e livre; agir pede OK por acao com o comando exato; opcoes Sim / Sim e nao pergunte mais para este tipo (regra gravada, editavel) / Nao, faca diferente; modo plano opcional; trava de formatar e afins continua por baixo.
5. Funcoes: **todas**: programas (winget), arquivos (com copia antes de sobrescrever), comandos e scripts, pesquisa na web, rede da casa, sistema, memoria entre sessoes.
6. Cerebro **hibrido**: gemma4:12b local para o simples; Claude pela API para o longo ou dificil.
7. Roteamento: **a Atlas decide e pede OK** mostrando o que sai; "nao pergunte mais" vale aqui tambem. Segredos, fotos excluidas e conteudo nao aprovado nunca saem, em codigo.

## Pendente

- Conta e chave da API Anthropic (console.anthropic.com, credito pre-pago) e o teto de gasto: o Matheus vai ver. Proposta: teto mensal + aviso por tarefa, valores no config; rota para o Claude desligada ate existir a chave.
- Memoria: o que guardar e por quanto tempo.
- Detalhes da janela.

## Divisao proposta (um spec e plano por parte)

1. Nucleo: permissoes, laco de agente com mais passos, janela nova, memoria.
2. Arquivos e comandos.
3. Programas e sistema.
4. Pesquisa na web.
5. Rede da casa.
6. Roteador para o Claude (quando houver chave).
