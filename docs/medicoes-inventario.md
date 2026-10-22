# Medicoes do inventario deste PC

Data: 22/10/2026. PC do Matheus. Raizes C:\ e E:\. Roda instalada por `C:\Users\Diniz\envio\jarvis-rodas\` (MD5 conferido).

## Varredura real

| Coleta | Resultado |
|---|---|
| arquivos | 899.965 em 108 s, sem erro |
| apps | 389 |
| servicos | 303 |
| pacotes | 193 |
| sistema + pacotes | menos de 6 s |
| tempo total (sincrono) | 114 s |
| banco | 419,9 MB |

## Exclusoes conferidas no banco real

fotos em E: fora da FORWARD 0; E:\Fotos & Videos 0; AppData 0; .env, id_rsa, nome com senha ou password 0; pasta com nome de segredo 0; fotos em E:\FORWARD 134 (esperado maior que 0). Fotos em C: sao 37.407 (a regra de foto vale so para E:).

## Cenarios

| Modelo | Resultado | Falhas |
|---|---|---|
| gemma4:12b | 13 de 14 | inv_foto_excluida: nao chamou ferramenta |
| gemma4:e4b | 11 de 14 | inv_achar_arquivo e inv_foto_excluida: nao chamou ferramenta; inv_servico: usou pc_servicos em vez de inv_sistema |

Tempos de 2,6 s a 7 s por cenario de inventario. Nao conferi ainda o numero das respostas de inv_maiores e inv_programa contra o banco (pendente).
O cenario inv_foto_excluida pode estar certo ao recusar sem consultar; o julgador exige a chamada.

## Aceitacao (Matheus)

Pendente.
