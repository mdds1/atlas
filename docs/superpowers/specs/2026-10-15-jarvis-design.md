# Jarvis do PC: design

Data: 15/10/2026, revisado em 19/10/2026. Estado: proposto, aguardando revisão do Matheus.

## Objetivo

Um assistente instalado no PC Windows do Matheus (WORK-DINIZ) que, **somente quando
ele chamar**, verifica o computador, diagnostica problemas, pesquisa na internet e propõe
soluções. Lê sozinho; qualquer mudança no PC só acontece com confirmação explícita.

## Decisões já tomadas

| Tema | Decisão |
|---|---|
| Base | OpenJarvis (Stanford, Apache-2.0), com a versão travada num commit validado |
| Cérebro | Híbrido: Gemma local (Ollama) no dia a dia, Claude pela API no diagnóstico difícil |
| Entrada | Texto e voz desde o início |
| Voz | **Palavra de ativação, desde o início** (decisão de 19/10/2026), detectada localmente. Uma tecla de reserva para falar fica como alternativa. Sem ativação por palma |
| Permissão | Lê sozinha; altera só com OK; apagar, formatar e afins bloqueados por código |
| Onde roda | Só no PC Windows (Ryzen 7 5700X, 32 GB, RTX 3060 de 12 GB, Python 3.10.11) |
| Repositório | `~/projetos/jarvis`, git local, sem GitHub |
| Instalação no PC | Autorizada pelo Matheus em 15/10/2026, restrita à pasta `C:\Jarvis` e ao Ollama |

Fora de escopo: ativação por palma, agentes proativos (resumo matinal e similares), acesso
remoto por Telegram, câmera e qualquer ação sem OK.

O caso de uso de **jogos** foi descartado em 15/10/2026 e **voltou ao escopo em 19/10/2026**,
como o exemplo central: um erro aparece no meio do jogo, o Matheus ativa a Jarvis por voz e
pede para checar, trazer uma resolução ou resolver.

## Alternativas descartadas

- **Zyron** (`Surajkumar5050/zyron-assistant`): é um controle remoto (câmera, microfone,
  localização, modo escondido), executa o JSON do modelo sem confirmação, aceita qualquer
  pessoa se o `.env` estiver vazio e confere `@username` em vez de ID. Reescrever
  execução, cérebro e autorização deixaria pouco do original.
- **Núcleo próprio do zero**: recomendado por mim, mas o Matheus escolheu o OpenJarvis.

## O que vem do OpenJarvis e o que escrevemos

Do OpenJarvis, sem alterar: engines Ollama e Claude, `MultiEngine`, busca na web, voz
(faster-whisper e Kokoro `pf_dora`), `credential_stripper`, auditoria e o mecanismo
`requires_confirmation` com callback (sem callback, a ação é negada).

Nosso, em pacote separado que se registra com `@ToolRegistry.register`:

1. **Ferramentas de leitura do PC** (`requires_confirmation=False`): resumo de CPU,
   memória e disco; processos mais pesados; espaço livre; programas de inicialização;
   erros recentes no log de eventos; serviços; drivers; temperatura; atualizações pendentes.
2. **Trava de comandos**: lista de bloqueio em código na frente do `shell_exec`. Barra
   formatar, apagar pasta inteira, alterar registro crítico e desligar a rede. Roda antes
   da pergunta de OK, então o Matheus nunca vê pedido perigoso.
3. **Roteador**: Gemma por padrão; sobe para o Claude quando o Matheus pedir diagnóstico a
   fundo ou quando a Gemma falhar uma vez. Antes de enviar, o `credential_stripper`
   remove segredos e a janela mostra o resumo que vai sair do PC.
4. **Janela e atalho**: janela de texto aberta por atalho de teclado; callback de
   confirmação com Sim e Não.

## Voz e palavra de ativação

O OpenJarvis **não traz** detecção de palavra de ativação (verificado em 19/10/2026); traz
gravação do microfone com detecção de silêncio, aproveitada depois que a palavra é ouvida.
A palavra de ativação é peça nossa.

- Detecção **local e offline**. Nada é gravado, guardado ou enviado antes de a palavra ser
  reconhecida.
- Indicação visível de que está escutando, e uma forma rápida de silenciar (ícone na
  bandeja e comando de voz).
- Tecla de reserva para falar, para quando a palavra falhar com o som do jogo alto.
- Risco assumido: no estudo anterior a confiabilidade da ativação por palavra foi estimada
  em ~50%. Medir com o som de um jogo real ligado, antes de dar a fase por pronta.

## Modo jogo

A RTX 3060 tem 12 GB de memória de vídeo e o jogo ocupa boa parte. Carregar o modelo local
(~9,6 GB) na placa durante o jogo tiraria memória do jogo e poderia travá-lo.

- Ao detectar um jogo aberto, a Jarvis roda um modelo menor **no processador** (32 GB de
  RAM livres) e sobe para o Claude no diagnóstico difícil, em vez de usar a placa.
- Fora do jogo, usa a Gemma na placa normalmente.
- A medição de memória e velocidade desse modo é tarefa da Fase 1, antes de prometer o
  comportamento.

## Ler o erro que aparece na tela

Erro de jogo costuma ser uma janela, não uma linha de log. A Jarvis captura a tela, extrai o
texto **localmente** (o Windows traz leitor de texto embutido, a confirmar na Fase 1) e
cruza com o log de eventos e os relatórios de falha do Windows. Imagem da tela não sai do PC
sem aparecer na prévia do que vai para o Claude.

## Fluxo de "o PC está lento"

1. Matheus chama pelo atalho (texto) ou segura outro atalho e fala.
2. A Gemma chama as ferramentas de leitura em sequência, sem pedir OK.
3. Se o achado é claro, responde. Se não, escala ao Claude, com prévia do que sai.
4. Se propõe ação, a janela mostra o comando exato e pergunta Sim ou Não, depois de a
   trava de bloqueio descartar o proibido.
5. Após o OK e a execução, mede de novo e diz se melhorou.

## Fases

| Fase | Entrega | Instala no PC |
|---|---|---|
| 1 | Texto, ferramentas de leitura, trava, janela com atalho, só Gemma local | Ollama, modelo Gemma, `C:\Jarvis` com ambiente Python próprio |
| 2 | Roteador com Claude, prévia e limpeza de segredos | Nada novo; chave de API própria, separada da assinatura, com limite mensal |
| 3 | Palavra de ativação local, voz com tecla de reserva, resposta falada em português, modo jogo e leitura da tela | Whisper `small`, voz Kokoro `pf_dora`, detector de palavra de ativação |
| 4 | Memória: perfil do PC "quando está normal" e histórico de problemas e consertos | Arquivo local legível e apagável pelo Matheus |

O Matheus testa no PC ao fim de cada fase antes da seguinte.

## Confiança e controle

- Registro em arquivo de cada ferramenta chamada, comando proposto, Sim e Não, e do que
  foi enviado ao Claude.
- Um comando de desinstalação que remove a pasta e o ambiente.
- OpenJarvis travado num commit validado. O candidato visto em 15/10 foi `b94a9b2`, que é
  um commit de rotina e **ainda não foi validado**; a escolha final do commit é a
  primeira tarefa da Fase 1.
- Tudo desenvolvido e testado na bancada; o PC só recebe versão que já passou.
- Respeitar a regra do PC: PowerShell lê UTF-8 como ANSI, então conferir conteúdo pelo
  lado Linux; `scp` quebra com acento, usar `C:\Users\Diniz\envio\` e conferir por MD5.

## Testes

- Ferramentas de leitura: testadas com saídas gravadas de PowerShell de um PC real, sem
  depender do PC no teste.
- Trava de comandos: testada com mutação (quebrar a regra de propósito e confirmar que o
  teste falha), conforme a skill `revisao-por-mutacao`.
- **Cenários para o prompt**: conjunto fixo ("PC lento", "disco cheio", "serviço parado",
  "tela azul"). Todo ajuste de prompt é conferido contra ele. O ajuste do prompt costuma
  dar mais trabalho que o código, segundo quem já montou assistentes locais.
- Contra alucinação: a Gemma só conclui sobre dados que as ferramentas acabaram de ler;
  sessões curtas; a memória entra por consulta, não empilhada na conversa.

## Riscos e pontos em aberto

- A RTX 3060 de 12 GB comporta o modelo de ~9,6 GB mais Whisper e voz com folga pequena, e
  com um jogo aberto não comporta. O modo jogo precisa ser medido (Fase 1) e a voz também
  (Fase 3) antes de prometer.
- Palavra de ativação com som de jogo e chat de voz pode errar para os dois lados.
- Probabilidades do estudo anterior: instalar e conversar por texto ~90%; voz em
  português ~75%; utilidade no dia a dia depende das ferramentas, e é por isso que elas
  são o centro do desenho.
- O custo real da API do Claude por diagnóstico não foi medido; será medido na Fase 2,
  com limite mensal configurado antes do primeiro uso.
- O OpenJarvis muda todo dia; atualizações só com reteste contra os cenários.
