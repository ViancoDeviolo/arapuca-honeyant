# ADR 0004 — Isca de baixa interação e política de uso da AWS

- **Status:** aceito
- **Data:** 2026-11-05

## Contexto

O HoneyAnt precisa de evidências reais de ataque (serviços visados, credenciais tentadas, origem por país/ASN) para alimentar o fuzzy e o ACO. Para isso, uma isca exposta à internet recebe conexões de atacantes. Uma isca que ofereça um shell real pode ser usada para atacar terceiros, minerar criptomoeda ou hospedar malware a partir da nossa conta.

## Decisão

Isca de **baixa interação**, escrita em Python:

- Telnet e MQTT **simulados**: só leem bytes e respondem com texto fixo. Não há shell, sistema de arquivos acessível nem execução de comandos.
- **Nenhuma conexão de saída**: o Security Group da EC2 não tem regras de saída; a saída só é aberta durante o deploy e fechada em seguida.
- Container sem privilégios: usuário não root, sistema de arquivos somente leitura, sem *capabilities*, limites de memória e de processos.
- Limites por sessão (bytes, tempo ocioso, prazo total, número de comandos) e por IP (conexões simultâneas e taxa).
- Teto de armazenamento e retenção de 7 dias, porque IP de atacante é dado pessoal (LGPD).

## Alternativas consideradas

- **Cowrie (alta/média interação):** emula um shell convincente e coleta mais comportamento, mas aumenta muito a superfície de risco operacional e é difícil de explicar inteiro na avaliação. Descartado.
- **Sem isca, só dados públicos de honeypots:** elimina o risco, mas tira o diferencial "com base no que os hackers estão fazendo agora". Descartado.

## Consequências

- Coletamos menos comportamento pós-login do que um honeypot de alta interação; credenciais e comandos iniciais bastam para o modelo.
- Um atacante atento percebe que é uma isca; isso não compromete o objetivo.
- Atualizar a imagem exige abrir a janela de saída (procedimento em `infra/aws/DEPLOY.md`).

## Política de uso da AWS

- **Verificada em:** 2026-11-05 (versão da política: "Last Updated: July 1, 2021")
- **Link:** https://aws.amazon.com/aup/
- **O que a política proíbe:** atividades ilegais ou fraudulentas; violar direitos de terceiros; ameaçar ou incentivar violência; conteúdo de exploração sexual infantil; **violar a segurança, a integridade ou a disponibilidade de qualquer usuário, rede, computador ou sistema de comunicação**; e envio de mensagens em massa não solicitadas (spam).
- **Conclusão:** a política não menciona honeypots e não proíbe receber conexões e registrá-las na própria instância. O risco real seria a isca ser usada **contra terceiros** (ataque, retransmissão, spam), o que violaria o item de segurança. As decisões deste ADR fecham exatamente esse caminho: sem execução de comandos, sem retransmissão de mensagens MQTT e **sem nenhuma conexão de saída** no Security Group. A AWS pode investigar suspeitas de violação; este ADR e o `infra/aws/DEPLOY.md` documentam o que a isca faz e o que ela não consegue fazer.
