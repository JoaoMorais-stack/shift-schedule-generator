import json
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app


class IsolatedDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory(prefix=".tmp-", dir=Path(__file__).parent)
        self.original_db_path = app.DB_PATH
        app.DB_PATH = Path(self.temp_dir.name) / "schedule.db"
        app.criar_banco()

    def tearDown(self):
        app.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()


class SchedulingRulesTests(IsolatedDatabaseTestCase):
    def test_classifies_weekends_and_fixed_holidays(self):
        with app.conectar() as conn:
            self.assertEqual(app.classificar_dia(conn, date(2027, 1, 2))[0], "regular")
            self.assertEqual(app.classificar_dia(conn, date(2027, 1, 1))[0], "prioritaria")
            self.assertEqual(app.classificar_dia(conn, date(2027, 1, 4))[0], "")

    def test_rotation_skips_an_unavailable_employee(self):
        with app.conectar() as conn:
            employees = conn.execute(
                "SELECT id, nome_curto FROM colaboradores ORDER BY ordem_rotacao, id"
            ).fetchall()
            last_employee = employees[-2]
            skipped_employee = employees[-1]
            conn.execute(
                """
                INSERT INTO indisponibilidades
                    (colaborador_id, inicio, fim, motivo, categorias, observacao)
                VALUES (?, '2027-01-02', '2027-01-02', 'Compromisso pessoal', 'regular', '')
                """,
                (skipped_employee["id"],),
            )
            selected, note = app.proximo_colaborador(
                conn, "regular", date(2027, 1, 2), last_employee["id"]
            )

        self.assertEqual(selected["id"], employees[0]["id"])
        self.assertIn(skipped_employee["nome_curto"], note)

    def test_fill_missing_preserves_manual_assignment(self):
        employee_id = app.listar_colaboradores()[0]["id"]
        app.salvar_linha_escala(
            {
                "data": "2027-01-02",
                "tipo": "regular",
                "colaborador_id": employee_id,
                "origem": "ajuste local",
                "observacao": "Mantido pelo teste",
            }
        )

        app.gerar_escala("2027-01-02", "2027-01-03", overwrite=False)
        items = app.escala_periodo("2027-01-02", "2027-01-03")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["colaborador_id"], employee_id)
        self.assertEqual(items[0]["editado"], 1)
        self.assertEqual(items[0]["observacao"], "Mantido pelo teste")

    def test_rejects_invalid_period(self):
        with self.assertRaisesRegex(ValueError, "Periodo invalido"):
            app.gerar_escala("2027-02-10", "2027-02-01")


class PersistenceTests(IsolatedDatabaseTestCase):
    def test_employee_leave_and_shift_are_persisted(self):
        app.salvar_colaborador(
            {
                "funcao": "qualidade",
                "nome_curto": "iris",
                "nome_completo": "iris campos demo",
                "telefone": "00900000100",
            }
        )
        employee = next(item for item in app.listar_colaboradores() if item["nome_curto"] == "Iris")
        app.salvar_ferias(
            {
                "colaborador_id": employee["id"],
                "inicio": "01/03/2027",
                "fim": "05/03/2027",
                "dias": 5,
            }
        )
        app.salvar_turno(
            {
                "colaborador_id": employee["id"],
                "horario": "09:00-17:00",
                "equipe": "Equipe Verde",
                "inicio": "2027-03-01",
                "fim": "2027-03-31",
            }
        )

        snapshot = app.bootstrap()

        self.assertEqual(employee["funcao"], "QUALIDADE")
        self.assertEqual(employee["telefone"], "(00) 90000-0100")
        self.assertTrue(any(item["colaborador_id"] == employee["id"] for item in snapshot["ferias"]))
        shift = next(item for item in snapshot["turnos"] if item["colaborador_id"] == employee["id"])
        self.assertEqual(shift["equipe"], "Equipe Verde")
        self.assertTrue(any("Ferias" in conflict for conflict in shift["conflitos"]))


class HttpTests(IsolatedDatabaseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("localhost", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://localhost:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=data, headers=headers)
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_serves_interface_and_bootstrap_api(self):
        with urlopen(self.base_url + "/", timeout=3) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Gerador de Escalas", body)

        status, payload = self.request_json("/api/bootstrap")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(payload["colaboradores"]), 8)

    def test_generates_schedule_through_http(self):
        status, payload = self.request_json(
            "/api/gerar",
            {"inicio": "2027-01-02", "fim": "2027-01-03", "overwrite": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["total"], 2)

        status, payload = self.request_json("/api/escala?inicio=2027-01-02&fim=2027-01-03")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["escala"]), 2)

    def test_rejects_static_path_traversal(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(self.base_url + "/static/../app.py", timeout=3)
        self.assertEqual(context.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
