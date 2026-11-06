"""Integração: gravação da execução em JSON e determinismo byte a byte."""

import json
import tempfile
import unittest
from pathlib import Path

from honeyant.pathfinder.adapters.gravador_json import GravadorJson
from honeyant.pathfinder.dominio.aco import ParametrosACO, executar
from tests.unit.test_pathfinder_aco import grafo_casa


def gravar(
    semente: int, params: ParametrosACO | None = None
) -> tuple[GravadorJson, str]:
    p = params or ParametrosACO()
    gravador = GravadorJson()
    resultado = executar(grafo_casa(), p, semente=semente, observador=gravador)
    return gravador, gravador.serializar(semente, p, resultado)


class TestGravadorJson(unittest.TestCase):
    def test_mesma_semente_gera_json_identico_byte_a_byte(self):
        _, a = gravar(42)
        _, b = gravar(42)
        self.assertEqual(a.encode("utf-8"), b.encode("utf-8"))

    def test_sementes_diferentes_geram_json_diferente(self):
        _, a = gravar(1)
        _, b = gravar(2)
        self.assertNotEqual(a, b)

    def test_json_e_valido_e_tem_a_estrutura_esperada(self):
        _, texto = gravar(7, ParametrosACO(iteracoes=5))
        dados = json.loads(texto)
        self.assertEqual(dados["versao"], 1)
        self.assertEqual(dados["semente"], 7)
        self.assertEqual(len(dados["snapshots"]), 5)
        self.assertEqual(
            dados["resultado"]["rota"], ["internet", "camera", "hub", "fechadura"]
        )
        self.assertEqual(dados["parametros"]["iteracoes"], 5)
        primeiro = dados["snapshots"][0]
        self.assertEqual(
            set(primeiro),
            {"iteracao", "feromonio", "caminhos", "melhor_rota", "melhor_custo"},
        )

    def test_resultado_sem_rota_e_serializado_sem_excecao(self):
        g = grafo_casa().com_bloqueio("hub", "fechadura")
        p = ParametrosACO()
        gravador = GravadorJson()
        r = executar(g, p, semente=1, observador=gravador)
        dados = json.loads(gravador.serializar(1, p, r))
        self.assertIsNone(dados["resultado"]["rota"])
        self.assertEqual(dados["resultado"]["parada"], "sem_rota")
        self.assertEqual(dados["snapshots"], [])

    def test_salvar_grava_arquivo_identico_ao_texto_serializado(self):
        gravador, texto = gravar(3)
        p = ParametrosACO()
        resultado = executar(grafo_casa(), p, semente=3)
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "replay.json"
            gravador.salvar(destino, 3, p, resultado)
            self.assertEqual(destino.read_bytes(), texto.encode("utf-8"))

    def test_replay_gravado_duas_vezes_gera_arquivos_identicos(self):
        p = ParametrosACO()
        with tempfile.TemporaryDirectory() as pasta:
            arquivos = []
            for i in range(2):
                gravador = GravadorJson()
                r = executar(grafo_casa(), p, semente=11, observador=gravador)
                destino = Path(pasta) / f"replay{i}.json"
                gravador.salvar(destino, 11, p, r)
                arquivos.append(destino.read_bytes())
            self.assertEqual(arquivos[0], arquivos[1])


if __name__ == "__main__":
    unittest.main()
