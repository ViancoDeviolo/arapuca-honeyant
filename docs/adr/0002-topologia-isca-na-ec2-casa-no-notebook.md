# ADR 0002 — Topologia: isca na EC2, casa no notebook

- **Status:** aceito (revisto em 07/11/2026)
- **Data:** 2026-11-05

## Contexto

A isca precisa estar na internet para receber ataques reais. A casa simulada, o sensor e a
demonstração precisam funcionar na sala da ExpoTech, inclusive sem internet. E o IP dos
atacantes é dado pessoal (LGPD): não deve sair da nuvem.

## Decisão

- **EC2 (t3.micro, us-east-1):** só a isca (`arapuca`) e o leitor em `mode=ro`
  (`verificar-ro` e `exportar-resumo`). Entrada 23 e 1883 abertas; 22 só para o IP de
  quem faz o deploy; **nenhuma regra de saída**.
- **Notebook:** twin (Docker), sensor, pathfinder e painel (`honeyant-local`, em 127.0.0.1).
- **Ponte:** o resumo agregado e **sem IP** é exportado na EC2 (`honeyant-exportar-resumo`)
  e copiado por `scp` para `docs/demo/resumo-real-AAAA-MM-DD.json`. O painel e o twin usam
  sempre o mais recente; sem ele, o resumo de exemplo.

**Revisão de 07/11:** o spec original previa o painel também na EC2 (porta 443 com CA
própria) e o notebook puxando o resumo por HTTPS. Isso não foi implementado: com o prazo,
o resumo congelado por `scp` atende à demonstração, não abre mais uma porta na isca e
funciona offline. Fica como dívida técnica.

## Custo

Conta AWS no plano pago básico. Previsto: **R$ 20 a R$ 50** até a apresentação, com
orçamento de US$ 10 e alertas em 50% e 100%, uma instância só, 12 GB de disco e a
instância encerrada depois da ExpoTech (28/11/2026). O briefing pedia custo zero; a
diferença foi aceita pela equipe.

## Alternativas consideradas

- **Tudo no notebook, sem isca:** sem ataques reais, sem o diferencial. Descartado.
- **Tudo na nuvem:** a demo dependeria da rede do evento. Descartado.

## Consequências

- A rota da demo é calculada sobre um resumo **congelado**: um pico de ataques não muda a
  rota no meio da apresentação.
- Atualizar o resumo exige SSH na EC2 e abrir a janela de saída só para o build.
