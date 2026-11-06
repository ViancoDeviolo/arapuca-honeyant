# Contratos entre módulos

Todos os formatos de dados que passam de um módulo para outro estão em `src/honeyant/core/`
(modelos pydantic, imutáveis, com `schema_version`). **Ninguém cria formato paralelo.**
Mudar um contrato exige PR aprovado por todos.

Os arquivos `*.schema.json` desta pasta são gerados a partir dos modelos, para quem consome
sem Python (por exemplo, o JavaScript do painel). Depois de mudar um contrato, rode:

```bash
uv run honeyant-contratos
```

O teste `tests/unit/core/test_esquemas.py` falha no CI se esta pasta estiver desatualizada.

## Quem produz e quem consome

| Contrato | Arquivo | Produz | Consome | Fixture de exemplo |
|---|---|---|---|---|
| `EventoDeAtaque` | `core/eventos.py` | arapuca | intel (nunca sai da EC2: tem IP) | — |
| `ResumoDeAmeaca` | `core/resumo.py` | intel (`GET /api/v1/resumo`) | twin, sensor, pathfinder, painel | `docs/demo/resumo-congelado.json` |
| `PerfilDaCasa` | `core/casa.py` | twin (versionado) | sensor, pathfinder, painel | `docs/demo/perfil-{inseguro,seguro}.json` |
| `EvidenciaDeRede` | `core/evidencia.py` | sensor | pathfinder, painel | `docs/demo/evidencias-{inseguro,seguro}.json` |
| `Rota` | `core/rota.py` | pathfinder | painel | dentro dos snapshots |
| `Snapshot` | `core/rota.py` | pathfinder | painel (SSE e replay) | `docs/demo/snapshots-exemplo.jsonl` |

Exemplo de uso:

```python
import json
from pathlib import Path

from honeyant.core.casa import PerfilDaCasa
from honeyant.core.evidencia import EvidenciaDeRede, combinar_evidencias

perfil = PerfilDaCasa.model_validate_json(Path("docs/demo/perfil-inseguro.json").read_text("utf-8"))
brutas = json.loads(Path("docs/demo/evidencias-inseguro.json").read_text("utf-8"))
evidencias = combinar_evidencias(EvidenciaDeRede.model_validate(e) for e in brutas)
evidencias["camera->broker"].credencial_vazada  # True
```

## Convenções

- **Toda aresta é identificada por `"origem->destino"`** (função `chave_aresta`). É a chave usada
  em `EvidenciaDeRede.aresta`, em `Snapshot.feromonio` e em `Rota.arestas`.
- **Id de nó:** minúsculas, dígitos e `_`, começando por letra, até 32 caracteres. Seguro para
  usar como chave JSON, id no SVG ou tópico MQTT sem escapar.
- **Horários** sempre com fuso; o modelo converte para UTC.
- **Campos a mais são rejeitados** (`extra="forbid"`). No resumo isso impede, por exemplo, que um
  IP de atacante saia da EC2 por engano (LGPD).
- **Escalas 0–10:** `exposicao`, `fraqueza_fixa` e `sensibilidade`.
- **`fraqueza_fixa`** só existe nas arestas que o sensor não observa (`lan`, `upnp` e o `telnet`
  vindo da internet). Nas outras é `None` e a fraqueza vem da evidência.
- **`None` numa evidência = "não observado".** O pathfinder trata como o pior caso.
- **Combinar evidências da mesma aresta:** use `combinar_evidencias`. Um valor observado
  substitui `None`; em conflito, vale a evidência **ativa** mais recente (ela testa de fato; a
  passiva só infere).
- **Resumo:** a soma de `por_servico` é igual a `total_eventos`. País desconhecido = `"ZZ"`;
  ASN desconhecido = `0`. No máximo 20 credenciais, já limpas de caracteres de controle e
  truncadas em 64 caracteres. **Continuam sendo texto hostil:** no navegador, só `textContent`.
- **Rota:** não repete nó; `custo` ≥ 0 e finito; `plausibilidade` precisa ser `e^(−custo)`.
- **Snapshot:** no máximo 20 caminhos; feromônio ≥ 0 por aresta.

## Sobre as fixtures

- Os **perfis** seguem o grafo da seção 7 da spec, com coordenadas para um quadro de
  1000 × 620 (internet no topo e fechadura no fundo, como num formigueiro em corte). Os valores
  de `fraqueza_fixa` vêm da própria tabela de fraqueza da spec: telnet com senha vazada =
  4 + 3 + 1 = **8**; com senha forte = 3 + 1 = **4**; upnp sem autenticação = 3 + 2 + 1 = **6**;
  lan = **3** (proposta). No perfil seguro só muda a telnet da câmera: o resto da mitigação
  aparece nas evidências.
- O **resumo congelado** ainda é um **exemplo** com credenciais típicas de botnets IoT. Antes do
  congelamento (08/11), ele será trocado por um resumo real gerado pelo intel a partir dos dados da
  isca. Os testes exigem só que ele seja válido.
- As **evidências** trazem, na câmera do perfil inseguro, uma passiva e uma ativa para a mesma
  aresta, justamente para exercitar `combinar_evidencias`.
- Os **snapshots** são feitos à mão e não vêm do ACO de verdade. Servem para o painel desenhar o
  formigueiro antes de o pathfinder existir.
