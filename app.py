from datetime import date, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import json
import mimetypes
import re
import sqlite3
import sys


def obter_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = obter_base_dir()
DATA_DIR = BASE_DIR / "Data"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "escalas.db"
HOST = "127.0.0.1"
PORT = 5100

DATA_DIR.mkdir(exist_ok=True)

TIPOS = {
    "regular": "Regular",
    "especial": "Especial",
    "prioritaria": "Prioritaria",
}

MESES = [
    "Janeiro",
    "Fevereiro",
    "Marco",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]


class ConexaoSQLite(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def conectar():
    conn = sqlite3.connect(DB_PATH, factory=ConexaoSQLite)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def normalizar_data(valor):
    valor = (valor or "").strip()
    if not valor:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", valor):
        return valor
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", valor)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return valor


def ler_data(valor):
    try:
        return date.fromisoformat(valor)
    except Exception:
        return None


def somente_digitos(valor):
    return re.sub(r"\D+", "", valor or "")


def formatar_telefone(valor):
    digitos = somente_digitos(valor)
    if not digitos:
        return ""
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    return valor.strip()


def titulo_nome(valor):
    valor = re.sub(r"\s+", " ", (valor or "").strip())
    if not valor:
        return ""
    partes = []
    for palavra in valor.split(" "):
        if "." in palavra and len(palavra.replace(".", "")) <= 3:
            partes.append(palavra.upper())
        else:
            partes.append("-".join(p[:1].upper() + p[1:].lower() for p in palavra.split("-") if p))
    return " ".join(partes)


def easter_date(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def intervalo_datas(inicio, fim):
    atual = inicio
    while atual <= fim:
        yield atual
        atual += timedelta(days=1)


def criar_banco():
    with conectar() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS colaboradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_exibicao INTEGER NOT NULL DEFAULT 0,
                ordem_rotacao INTEGER NOT NULL DEFAULT 0,
                funcao TEXT NOT NULL DEFAULT '',
                nome_curto TEXT NOT NULL DEFAULT '',
                nome_completo TEXT NOT NULL DEFAULT '',
                telefone TEXT NOT NULL DEFAULT '',
                ativo INTEGER NOT NULL DEFAULT 1,
                participa_escala INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ferias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                colaborador_id INTEGER NOT NULL,
                periodo INTEGER NOT NULL DEFAULT 1,
                inicio TEXT NOT NULL DEFAULT '',
                fim TEXT NOT NULL DEFAULT '',
                dias INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS indisponibilidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                colaborador_id INTEGER NOT NULL,
                inicio TEXT NOT NULL DEFAULT '',
                fim TEXT NOT NULL DEFAULT '',
                motivo TEXT NOT NULL DEFAULT '',
                categorias TEXT NOT NULL DEFAULT 'regular,especial,prioritaria',
                observacao TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feriados_custom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL DEFAULT '',
                tipo TEXT NOT NULL DEFAULT 'especial'
            );

            CREATE TABLE IF NOT EXISTS escala (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL DEFAULT '',
                colaborador_id INTEGER,
                origem TEXT NOT NULL DEFAULT '',
                observacao TEXT NOT NULL DEFAULT '',
                editado INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS turnos_semana (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horario TEXT NOT NULL DEFAULT '',
                colaborador_id INTEGER,
                equipe TEXT NOT NULL DEFAULT '',
                inicio TEXT NOT NULL DEFAULT '',
                fim TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (colaborador_id) REFERENCES colaboradores(id) ON DELETE SET NULL
            );
            """
        )
        total = conn.execute("SELECT COUNT(*) AS total FROM colaboradores").fetchone()["total"]
        if total == 0:
            inserir_dados_iniciais(conn)
        garantir_configuracoes(conn)


def colaborador_nome(row):
    if not row:
        return ""
    return f"{row['funcao']} {row['nome_curto']}".strip()


def inserir_colaborador(conn, ordem_exibicao, ordem_rotacao, funcao, nome_curto, completo, telefone):
    cursor = conn.execute(
        """
        INSERT INTO colaboradores (
            ordem_exibicao, ordem_rotacao, funcao, nome_curto, nome_completo, telefone, ativo, participa_escala
        ) VALUES (?, ?, ?, ?, ?, ?, 1, 1)
        """,
        (ordem_exibicao, ordem_rotacao, funcao, nome_curto, completo, formatar_telefone(telefone)),
    )
    return cursor.lastrowid


def inserir_dados_iniciais(conn):
    dados = [
        (1, 1, "Atendimento", "Ana", "Ana Souza Demo", "(00) 90000-0001"),
        (2, 2, "Operacoes", "Bruno", "Bruno Lima Demo", "(00) 90000-0002"),
        (3, 3, "Logistica", "Carla", "Carla Mendes Demo", "(00) 90000-0003"),
        (4, 4, "Suporte", "Diego", "Diego Rocha Demo", "(00) 90000-0004"),
        (5, 5, "Atendimento", "Eduarda", "Eduarda Alves Demo", "(00) 90000-0005"),
        (6, 6, "Operacoes", "Felipe", "Felipe Nunes Demo", "(00) 90000-0006"),
        (7, 7, "Logistica", "Gabriela", "Gabriela Reis Demo", "(00) 90000-0007"),
        (8, 8, "Suporte", "Henrique", "Henrique Melo Demo", "(00) 90000-0008"),
    ]
    ids = {}
    for item in dados:
        ids[item[3]] = inserir_colaborador(conn, *item)

    conn.execute(
        "INSERT INTO ferias (colaborador_id, periodo, inicio, fim, dias) VALUES (?, 1, '2026-06-08', '2026-06-17', 10)",
        (ids["Bruno"],),
    )
    conn.execute(
        "INSERT INTO ferias (colaborador_id, periodo, inicio, fim, dias) VALUES (?, 1, '2026-06-18', '2026-07-02', 15)",
        (ids["Felipe"],),
    )

    junho = [
        ("2026-06-04", "especial", "Gabriela", "Marco especial de demonstracao"),
        ("2026-06-06", "regular", "Gabriela", ""),
        ("2026-06-07", "regular", "Felipe", ""),
        ("2026-06-13", "regular", "Eduarda", ""),
        ("2026-06-14", "regular", "Diego", ""),
        ("2026-06-20", "regular", "Carla", ""),
        ("2026-06-21", "regular", "Bruno", ""),
        ("2026-06-27", "regular", "Henrique", ""),
        ("2026-06-28", "regular", "Gabriela", ""),
    ]
    for data, tipo, nome, obs in junho:
        conn.execute(
            """
            INSERT INTO escala (data, tipo, colaborador_id, origem, observacao, editado)
            VALUES (?, ?, ?, 'dados de demonstracao', ?, 1)
            """,
            (data, tipo, ids[nome], obs),
        )

    turnos = [
        ("06:00-12:00", "Eduarda", "Equipe Alpha", "2026-06-01", ""),
        ("08:00-14:00", "Felipe", "Equipe Beta", "2026-06-01", "2026-06-17"),
        ("08:00-14:00", "Gabriela", "Equipe Beta", "2026-06-18", ""),
        ("12:00-18:00", "Gabriela", "Equipe Gamma", "2026-06-01", "2026-06-17"),
        ("14:00-20:00", "Henrique", "Equipe Gamma", "2026-06-01", ""),
    ]
    for horario, nome, equipe, inicio, fim in turnos:
        conn.execute(
            "INSERT INTO turnos_semana (horario, colaborador_id, equipe, inicio, fim) VALUES (?, ?, ?, ?, ?)",
            (horario, ids[nome], equipe, inicio, fim),
        )


def set_config(conn, chave, valor):
    conn.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, str(valor or "")),
    )


def garantir_configuracoes(conn):
    existentes = {row["chave"]: row["valor"] for row in conn.execute("SELECT chave, valor FROM configuracoes")}
    def id_por_nome(nome):
        row = conn.execute("SELECT id FROM colaboradores WHERE nome_curto = ?", (nome,)).fetchone()
        return row["id"] if row else ""

    hoje = date.today().isoformat()
    defaults = {
        "last_regular_id": id_por_nome("Gabriela"),
        "last_especial_id": id_por_nome("Gabriela"),
        "last_prioritaria_id": "",
        "marco_regular_id": existentes.get("last_regular_id", id_por_nome("Gabriela")),
        "marco_regular_data": hoje,
        "marco_especial_id": existentes.get("last_especial_id", id_por_nome("Gabriela")),
        "marco_especial_data": hoje,
        "marco_prioritaria_id": existentes.get("last_prioritaria_id", ""),
        "marco_prioritaria_data": "",
    }
    for chave, valor in defaults.items():
        if chave not in existentes:
            set_config(conn, chave, valor)


def get_config(conn):
    return {row["chave"]: row["valor"] for row in conn.execute("SELECT chave, valor FROM configuracoes")}


def get_marcos(conn):
    config = get_config(conn)
    marcos = {}
    for tipo in TIPOS:
        colaborador_id = config.get(f"marco_{tipo}_id") or config.get(f"last_{tipo}_id") or ""
        data = normalizar_data(config.get(f"marco_{tipo}_data") or "")
        marcos[tipo] = {"colaborador_id": colaborador_id, "data": data}
    return marcos


def listar_colaboradores(conn=None):
    fechar = False
    if conn is None:
        conn = conectar()
        fechar = True
    rows = conn.execute("SELECT * FROM colaboradores ORDER BY ordem_exibicao, id").fetchall()
    resultado = [dict(row) | {"nome": colaborador_nome(row)} for row in rows]
    if fechar:
        conn.close()
    return resultado


def feriados_fixos(data):
    ano = data.year
    pascoa = easter_date(ano)
    feriados = {}

    def add(dia, nome, tipo="especial"):
        feriados[dia.isoformat()] = {"nome": nome, "tipo": tipo}

    add(date(ano, 1, 1), "Ano Novo", "prioritaria")
    add(date(ano, 4, 21), "Tiradentes", "especial")
    add(date(ano, 5, 1), "Dia do Trabalho", "especial")
    add(date(ano, 9, 7), "Independencia do Brasil", "especial")
    add(date(ano, 10, 12), "Nossa Senhora Aparecida", "especial")
    add(date(ano, 11, 2), "Finados", "especial")
    add(date(ano, 11, 15), "Proclamacao da Republica", "especial")
    add(date(ano, 11, 20), "Consciencia Negra", "especial")
    add(date(ano, 12, 24), "Vespera de Natal", "prioritaria")
    add(date(ano, 12, 25), "Natal", "prioritaria")
    add(date(ano, 12, 31), "Vespera de Ano Novo", "prioritaria")

    add(pascoa - timedelta(days=48), "Carnaval", "prioritaria")
    add(pascoa - timedelta(days=47), "Carnaval", "prioritaria")
    add(pascoa - timedelta(days=2), "Sexta-feira Santa", "especial")
    add(pascoa - timedelta(days=1), "Sabado de Pascoa", "especial")
    add(pascoa, "Pascoa", "especial")
    add(pascoa + timedelta(days=60), "Corpus Christi", "especial")

    return feriados.get(data.isoformat())


def feriado_custom(conn, data):
    row = conn.execute("SELECT * FROM feriados_custom WHERE data = ?", (data.isoformat(),)).fetchone()
    return dict(row) if row else None


def classificar_dia(conn, data):
    custom = feriado_custom(conn, data)
    if custom:
        return custom["tipo"], custom["nome"], "feriado customizado"

    fixo = feriados_fixos(data)
    if fixo:
        return fixo["tipo"], fixo["nome"], "calendario automatico"

    if data.weekday() >= 5:
        return "regular", "Final de semana", "fim de semana"

    return "", "", ""


def esta_indisponivel(conn, colaborador_id, data, tipo):
    data_texto = data.isoformat()
    ferias = conn.execute(
        """
        SELECT id FROM ferias
        WHERE colaborador_id = ? AND inicio <> '' AND fim <> '' AND inicio <= ? AND fim >= ?
        LIMIT 1
        """,
        (colaborador_id, data_texto, data_texto),
    ).fetchone()
    if ferias:
        return True, "Ferias"

    indisponibilidade = conn.execute(
        """
        SELECT motivo FROM indisponibilidades
        WHERE colaborador_id = ? AND inicio <= ? AND fim >= ?
        """,
        (colaborador_id, data_texto, data_texto),
    ).fetchall()
    for row in indisponibilidade:
        categorias = conn.execute(
            """
            SELECT categorias FROM indisponibilidades
            WHERE colaborador_id = ? AND inicio <= ? AND fim >= ? AND motivo = ?
            LIMIT 1
            """,
            (colaborador_id, data_texto, data_texto, row["motivo"]),
        ).fetchone()
        if categorias and (tipo in categorias["categorias"].split(",") or "todas" in categorias["categorias"].split(",")):
            return True, row["motivo"] or "Indisponibilidade"

    return False, ""


def participantes_rotacao(conn):
    return conn.execute(
        """
        SELECT * FROM colaboradores
        WHERE ativo = 1 AND participa_escala = 1
        ORDER BY ordem_rotacao, id
        """
    ).fetchall()


def proximo_colaborador(conn, tipo, data, last_id):
    participantes = participantes_rotacao(conn)
    if not participantes:
        return None, "Sem colaboradores ativos na escala."

    ids = [row["id"] for row in participantes]
    if last_id and int(last_id) in ids:
        inicio = (ids.index(int(last_id)) + 1) % len(ids)
    else:
        inicio = 0

    pulados = []
    for passo in range(len(participantes)):
        idx = (inicio + passo) % len(participantes)
        colaborador = participantes[idx]
        indisponivel, motivo = esta_indisponivel(conn, colaborador["id"], data, tipo)
        if indisponivel:
            pulados.append(f"{colaborador_nome(colaborador)} ({motivo})")
            continue
        return colaborador, "; ".join(pulados)

    return None, "Todos indisponiveis: " + "; ".join(pulados)


def ultimos_por_tipo_antes(conn, inicio):
    marcos = get_marcos(conn)
    ultimos = {tipo: dados.get("colaborador_id", "") for tipo, dados in marcos.items()}
    for tipo in TIPOS:
        row = conn.execute(
            """
            SELECT colaborador_id
            FROM escala
            WHERE tipo = ? AND colaborador_id IS NOT NULL AND data < ?
            ORDER BY data DESC
            LIMIT 1
            """,
            (tipo, inicio.isoformat()),
        ).fetchone()
        marco_data = ler_data(marcos[tipo].get("data"))
        if row and row["colaborador_id"] and (not marco_data or row["data"] >= marco_data.isoformat()):
            ultimos[tipo] = row["colaborador_id"]
    return ultimos


def inicio_calculo_por_marcos(conn, inicio):
    datas = []
    for dados in get_marcos(conn).values():
        marco_data = ler_data(dados.get("data"))
        if marco_data:
            datas.append(marco_data + timedelta(days=1))
    if not datas:
        return inicio
    return min(min(datas), inicio)


def linha_rotacao(row):
    if not row:
        return None
    d = ler_data(row["data"])
    return {
        "data": row["data"],
        "data_br": f"{d.day:02d}/{d.month:02d}/{d.year}" if d else row["data"],
        "colaborador_id": row["colaborador_id"],
        "colaborador_nome": colaborador_nome(row),
        "origem": row["origem"],
        "editado": row["editado"],
    }


def status_rotacao(conn):
    hoje = date.today().isoformat()
    marcos = get_marcos(conn)
    status = {"hoje": hoje, "tipos": {}}
    for tipo in TIPOS:
        realizada = conn.execute(
            """
            SELECT e.*, m.funcao, m.nome_curto
            FROM escala e
            LEFT JOIN colaboradores m ON m.id = e.colaborador_id
            WHERE e.tipo = ? AND e.colaborador_id IS NOT NULL AND e.data <= ?
            ORDER BY e.data DESC
            LIMIT 1
            """,
            (tipo, hoje),
        ).fetchone()
        prevista = conn.execute(
            """
            SELECT e.*, m.funcao, m.nome_curto
            FROM escala e
            LEFT JOIN colaboradores m ON m.id = e.colaborador_id
            WHERE e.tipo = ? AND e.colaborador_id IS NOT NULL AND e.data > ?
            ORDER BY e.data ASC
            LIMIT 1
            """,
            (tipo, hoje),
        ).fetchone()
        marco = None
        marco_id = marcos[tipo].get("colaborador_id")
        if marco_id:
            marco = conn.execute("SELECT * FROM colaboradores WHERE id = ?", (marco_id,)).fetchone()

        status["tipos"][tipo] = {
            "label": TIPOS[tipo],
            "realizada": linha_rotacao(realizada),
            "prevista": linha_rotacao(prevista),
            "marco": {
                "colaborador_id": marco_id,
                "colaborador_nome": colaborador_nome(marco),
                "data": marcos[tipo].get("data"),
            } if marco else None,
        }
    return status


def gerar_escala(inicio_texto, fim_texto, overwrite=True):
    inicio = ler_data(normalizar_data(inicio_texto))
    fim = ler_data(normalizar_data(fim_texto))
    if not inicio or not fim or fim < inicio:
        raise ValueError("Periodo invalido.")

    gerados = []
    with conectar() as conn:
        marcos = get_marcos(conn)
        last = {tipo: dados.get("colaborador_id", "") for tipo, dados in marcos.items()}
        calculo_inicio = inicio_calculo_por_marcos(conn, inicio)
        for dia in intervalo_datas(calculo_inicio, fim):
            tipo, nome_dia, origem = classificar_dia(conn, dia)
            if not tipo:
                continue

            marco_data = ler_data(marcos.get(tipo, {}).get("data"))
            if marco_data and dia <= marco_data:
                existente = conn.execute("SELECT * FROM escala WHERE data = ? AND tipo = ?", (dia.isoformat(), tipo)).fetchone()
                if existente and existente["colaborador_id"]:
                    last[tipo] = existente["colaborador_id"]
                continue

            existente = conn.execute("SELECT * FROM escala WHERE data = ?", (dia.isoformat(),)).fetchone()
            if existente and (existente["editado"] == 1 or not overwrite):
                if existente["colaborador_id"]:
                    last[existente["tipo"]] = existente["colaborador_id"]
                continue

            colaborador, obs_skip = proximo_colaborador(conn, tipo, dia, last.get(tipo))
            colaborador_id = colaborador["id"] if colaborador else None
            obs = obs_skip if obs_skip else ""
            conn.execute(
                """
                INSERT INTO escala (data, tipo, colaborador_id, origem, observacao, editado, atualizado_em)
                VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(data) DO UPDATE SET
                    tipo = excluded.tipo,
                    colaborador_id = excluded.colaborador_id,
                    origem = excluded.origem,
                    observacao = excluded.observacao,
                    editado = 0,
                    atualizado_em = CURRENT_TIMESTAMP
                """,
                (dia.isoformat(), tipo, colaborador_id, f"{nome_dia} - {origem}", obs),
            )
            if colaborador_id:
                last[tipo] = colaborador_id
            if dia >= inicio:
                gerados.append({"data": dia.isoformat(), "tipo": tipo, "colaborador_id": colaborador_id})

        for tipo in TIPOS:
            set_config(conn, f"last_{tipo}_id", last.get(tipo, ""))

    return {"gerados": gerados, "total": len(gerados)}


def completar_periodo_para_consulta(inicio_texto, fim_texto):
    inicio = ler_data(normalizar_data(inicio_texto))
    fim = ler_data(normalizar_data(fim_texto))
    if not inicio or not fim or fim < inicio:
        return {"total": 0, "gerados": []}
    return gerar_escala(inicio.isoformat(), fim.isoformat(), overwrite=False)


def escala_periodo(inicio_texto, fim_texto):
    inicio = ler_data(normalizar_data(inicio_texto))
    fim = ler_data(normalizar_data(fim_texto))
    if not inicio or not fim:
        return []
    with conectar() as conn:
        rows = conn.execute(
            """
            SELECT e.*, m.funcao, m.nome_curto
            FROM escala e
            LEFT JOIN colaboradores m ON m.id = e.colaborador_id
            WHERE e.data BETWEEN ? AND ?
            ORDER BY e.data
            """,
            (inicio.isoformat(), fim.isoformat()),
        ).fetchall()
        resultado = []
        for row in rows:
            d = ler_data(row["data"])
            item = dict(row)
            item["colaborador_nome"] = colaborador_nome(row) if row["colaborador_id"] else ""
            item["dia_semana"] = DIAS_SEMANA[d.weekday()] if d else ""
            item["tipo_label"] = TIPOS.get(item["tipo"], item["tipo"])
            resultado.append(item)
        return resultado


def salvar_linha_escala(payload):
    data = normalizar_data(payload.get("data"))
    tipo = payload.get("tipo") or ""
    colaborador_id = payload.get("colaborador_id") or None
    observacao = payload.get("observacao") or ""
    if colaborador_id == "":
        colaborador_id = None
    with conectar() as conn:
        origem = payload.get("origem") or "edicao manual"
        conn.execute(
            """
            INSERT INTO escala (data, tipo, colaborador_id, origem, observacao, editado, atualizado_em)
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(data) DO UPDATE SET
                tipo = excluded.tipo,
                colaborador_id = excluded.colaborador_id,
                origem = excluded.origem,
                observacao = excluded.observacao,
                editado = 1,
                atualizado_em = CURRENT_TIMESTAMP
            """,
            (data, tipo, colaborador_id, origem, observacao),
        )
    return True


def salvar_colaborador(payload):
    colaborador_id = payload.get("id")
    dados = {
        "funcao": (payload.get("funcao") or "").strip().upper(),
        "nome_curto": titulo_nome(payload.get("nome_curto")),
        "nome_completo": titulo_nome(payload.get("nome_completo")),
        "telefone": formatar_telefone(payload.get("telefone")),
        "ativo": 1 if payload.get("ativo", True) else 0,
        "participa_escala": 1 if payload.get("participa_escala", True) else 0,
    }
    with conectar() as conn:
        if colaborador_id:
            conn.execute(
                """
                UPDATE colaboradores SET funcao=?, nome_curto=?, nome_completo=?, telefone=?, ativo=?, participa_escala=?
                WHERE id=?
                """,
                (dados["funcao"], dados["nome_curto"], dados["nome_completo"], dados["telefone"], dados["ativo"], dados["participa_escala"], colaborador_id),
            )
        else:
            ordem_ant = conn.execute("SELECT COALESCE(MAX(ordem_exibicao), 0) + 1 AS n FROM colaboradores").fetchone()["n"]
            ordem_rot = conn.execute("SELECT COALESCE(MAX(ordem_rotacao), 0) + 1 AS n FROM colaboradores").fetchone()["n"]
            conn.execute(
                """
                INSERT INTO colaboradores (ordem_exibicao, ordem_rotacao, funcao, nome_curto, nome_completo, telefone, ativo, participa_escala)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ordem_ant, ordem_rot, dados["funcao"], dados["nome_curto"], dados["nome_completo"], dados["telefone"], dados["ativo"], dados["participa_escala"]),
            )
    return True


def mover_colaborador(colaborador_id, campo, direcao):
    if campo not in ["ordem_exibicao", "ordem_rotacao"]:
        return
    with conectar() as conn:
        atual = conn.execute(f"SELECT id, {campo} AS ordem FROM colaboradores WHERE id = ?", (colaborador_id,)).fetchone()
        if not atual:
            return
        operador = "<" if direcao == "up" else ">"
        ordenacao = "DESC" if direcao == "up" else "ASC"
        vizinho = conn.execute(
            f"SELECT id, {campo} AS ordem FROM colaboradores WHERE {campo} {operador} ? ORDER BY {campo} {ordenacao} LIMIT 1",
            (atual["ordem"],),
        ).fetchone()
        if not vizinho:
            return
        conn.execute(f"UPDATE colaboradores SET {campo} = ? WHERE id = ?", (vizinho["ordem"], atual["id"]))
        conn.execute(f"UPDATE colaboradores SET {campo} = ? WHERE id = ?", (atual["ordem"], vizinho["id"]))


def excluir_colaborador(colaborador_id):
    with conectar() as conn:
        conn.execute("DELETE FROM colaboradores WHERE id = ?", (colaborador_id,))


def salvar_ferias(payload):
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO ferias (colaborador_id, periodo, inicio, fim, dias)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.get("colaborador_id"),
                int(payload.get("periodo") or 1),
                normalizar_data(payload.get("inicio")),
                normalizar_data(payload.get("fim")),
                int(payload.get("dias") or 0),
            ),
        )


def salvar_indisponibilidade(payload):
    categorias = payload.get("categorias") or ["regular", "especial", "prioritaria"]
    if isinstance(categorias, list):
        categorias = ",".join(categorias)
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO indisponibilidades (colaborador_id, inicio, fim, motivo, categorias, observacao)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("colaborador_id"),
                normalizar_data(payload.get("inicio")),
                normalizar_data(payload.get("fim")),
                payload.get("motivo") or "Indisponibilidade",
                categorias,
                payload.get("observacao") or "",
            ),
        )


def salvar_feriado(payload):
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO feriados_custom (data, nome, tipo)
            VALUES (?, ?, ?)
            ON CONFLICT(data) DO UPDATE SET nome=excluded.nome, tipo=excluded.tipo
            """,
            (normalizar_data(payload.get("data")), payload.get("nome") or "Feriado local", payload.get("tipo") or "especial"),
        )


def salvar_turno(payload):
    turno_id = payload.get("id")
    colaborador_id = payload.get("colaborador_id") or None
    dados = (
        (payload.get("horario") or "").strip(),
        colaborador_id,
        (payload.get("equipe") or "").strip(),
        normalizar_data(payload.get("inicio")),
        normalizar_data(payload.get("fim")),
    )
    if not dados[0] or not dados[2]:
        raise ValueError("Informe horario e equipe do turno.")

    with conectar() as conn:
        if turno_id:
            conn.execute(
                """
                UPDATE turnos_semana
                SET horario = ?, colaborador_id = ?, equipe = ?, inicio = ?, fim = ?
                WHERE id = ?
                """,
                (*dados, turno_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO turnos_semana (horario, colaborador_id, equipe, inicio, fim)
                VALUES (?, ?, ?, ?, ?)
                """,
                dados,
            )


def excluir_tabela_item(tabela, item_id):
    if tabela not in ["ferias", "indisponibilidades", "feriados_custom", "escala", "turnos_semana"]:
        return
    with conectar() as conn:
        conn.execute(f"DELETE FROM {tabela} WHERE id = ?", (item_id,))


def salvar_config(payload):
    with conectar() as conn:
        for chave in [
            "last_regular_id",
            "last_especial_id",
            "last_prioritaria_id",
            "marco_regular_id",
            "marco_regular_data",
            "marco_especial_id",
            "marco_especial_data",
            "marco_prioritaria_id",
            "marco_prioritaria_data",
        ]:
            if chave in payload:
                valor = normalizar_data(payload.get(chave)) if chave.endswith("_data") else payload.get(chave)
                set_config(conn, chave, valor or "")


def consultar(inicio_texto, fim_texto, colaborador_id=""):
    inicio = normalizar_data(inicio_texto)
    fim = normalizar_data(fim_texto)
    completar_periodo_para_consulta(inicio, fim)
    params = [inicio, fim]
    filtro = ""
    if colaborador_id:
        filtro = "AND e.colaborador_id = ?"
        params.append(colaborador_id)
    with conectar() as conn:
        rows = conn.execute(
            f"""
            SELECT e.*, m.funcao, m.nome_curto
            FROM escala e
            LEFT JOIN colaboradores m ON m.id = e.colaborador_id
            WHERE e.data BETWEEN ? AND ? {filtro}
            ORDER BY e.data
            """,
            params,
        ).fetchall()
        totais = {"regular": 0, "especial": 0, "prioritaria": 0, "total": 0}
        itens = []
        for row in rows:
            tipo = row["tipo"]
            if tipo in totais:
                totais[tipo] += 1
            totais["total"] += 1
            d = ler_data(row["data"])
            itens.append(dict(row) | {"colaborador_nome": colaborador_nome(row), "dia_semana": DIAS_SEMANA[d.weekday()] if d else ""})

        ranking_rows = conn.execute(
            """
            SELECT e.colaborador_id, m.funcao, m.nome_curto,
                SUM(CASE WHEN e.tipo='regular' THEN 1 ELSE 0 END) AS regular,
                SUM(CASE WHEN e.tipo='especial' THEN 1 ELSE 0 END) AS especial,
                SUM(CASE WHEN e.tipo='prioritaria' THEN 1 ELSE 0 END) AS prioritaria,
                COUNT(*) AS total
            FROM escala e
            JOIN colaboradores m ON m.id = e.colaborador_id
            WHERE e.data BETWEEN ? AND ?
            GROUP BY e.colaborador_id
            ORDER BY total DESC, m.ordem_exibicao
            """,
            (inicio, fim),
        ).fetchall()
        ranking = [dict(row) | {"nome": colaborador_nome(row)} for row in ranking_rows]

        indisponibilidades = []
        if colaborador_id:
            indisponibilidades = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT b.*, m.funcao, m.nome_curto
                    FROM indisponibilidades b
                    JOIN colaboradores m ON m.id = b.colaborador_id
                    WHERE b.colaborador_id = ? AND b.inicio <= ? AND b.fim >= ?
                    ORDER BY b.inicio
                    """,
                    (colaborador_id, fim, inicio),
                )
            ]

    return {"totais": totais, "itens": itens, "ranking": ranking, "indisponibilidades": indisponibilidades}


def conflitos_turno(conn, turno):
    if not turno["colaborador_id"] or not turno["inicio"]:
        return []
    inicio = turno["inicio"]
    fim = turno["fim"] or "9999-12-31"
    conflitos = []

    ferias = conn.execute(
        """
        SELECT inicio, fim FROM ferias
        WHERE colaborador_id = ? AND inicio <> '' AND fim <> '' AND inicio <= ? AND fim >= ?
        ORDER BY inicio
        """,
        (turno["colaborador_id"], fim, inicio),
    ).fetchall()
    for row in ferias:
        conflitos.append(f"Ferias: {row['inicio']} a {row['fim']}")

    indisponibilidades = conn.execute(
        """
        SELECT inicio, fim, motivo FROM indisponibilidades
        WHERE colaborador_id = ? AND inicio <= ? AND fim >= ?
        ORDER BY inicio
        """,
        (turno["colaborador_id"], fim, inicio),
    ).fetchall()
    for row in indisponibilidades:
        conflitos.append(f"{row['motivo'] or 'Indisponibilidade'}: {row['inicio']} a {row['fim']}")

    return conflitos


def bootstrap():
    with conectar() as conn:
        colaboradores = listar_colaboradores(conn)
        config = get_config(conn)
        ferias = [
            dict(row) | {"colaborador_nome": colaborador_nome(row)}
            for row in conn.execute(
                """
                SELECT f.*, m.funcao, m.nome_curto
                FROM ferias f JOIN colaboradores m ON m.id = f.colaborador_id
                ORDER BY f.inicio, m.ordem_exibicao
                """
            )
        ]
        indisponibilidades = [
            dict(row) | {"colaborador_nome": colaborador_nome(row)}
            for row in conn.execute(
                """
                SELECT b.*, m.funcao, m.nome_curto
                FROM indisponibilidades b JOIN colaboradores m ON m.id = b.colaborador_id
                ORDER BY b.inicio, m.ordem_exibicao
                """
            )
        ]
        feriados = [dict(row) for row in conn.execute("SELECT * FROM feriados_custom ORDER BY data")]
        turnos = []
        for row in conn.execute(
            """
            SELECT p.*, m.funcao, m.nome_curto
            FROM turnos_semana p LEFT JOIN colaboradores m ON m.id = p.colaborador_id
            ORDER BY p.horario, p.equipe, p.inicio, p.id
            """
        ):
            item = dict(row) | {"colaborador_nome": colaborador_nome(row)}
            item["conflitos"] = conflitos_turno(conn, item)
            turnos.append(item)
        return {
            "colaboradores": colaboradores,
            "config": config,
            "rotacao_status": status_rotacao(conn),
            "ferias": ferias,
            "indisponibilidades": indisponibilidades,
            "feriados": feriados,
            "turnos": turnos,
        }


def resposta_json(handler, status, payload):
    corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(corpo)))
    handler.end_headers()
    handler.wfile.write(corpo)


class Handler(BaseHTTPRequestHandler):
    server_version = "GeradorEscalas/1.0"

    def log_message(self, formato, *args):
        print("%s - %s" % (self.address_string(), formato % args))

    def do_GET(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        if path == "/":
            return self.enviar_arquivo(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path.startswith("/static/"):
            return self.enviar_arquivo(STATIC_DIR / path.replace("/static/", "", 1))
        if path == "/api/bootstrap":
            return resposta_json(self, 200, bootstrap())
        if path == "/api/escala":
            return resposta_json(self, 200, {"escala": escala_periodo(qs.get("inicio", [""])[0], qs.get("fim", [""])[0])})
        if path == "/api/consulta":
            return resposta_json(
                self,
                200,
                consultar(qs.get("inicio", [""])[0], qs.get("fim", [""])[0], qs.get("colaborador_id", [""])[0]),
            )
        return resposta_json(self, 404, {"erro": "Caminho nao encontrado."})

    def do_POST(self):
        path = urlparse(self.path).path
        payload = self.ler_json()
        try:
            if path == "/api/gerar":
                return resposta_json(self, 200, gerar_escala(payload.get("inicio"), payload.get("fim"), payload.get("overwrite", True)))
            if path == "/api/escala":
                salvar_linha_escala(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/colaboradores":
                salvar_colaborador(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/ferias":
                salvar_ferias(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/indisponibilidades":
                salvar_indisponibilidade(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/feriados":
                salvar_feriado(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/turnos":
                salvar_turno(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/config":
                salvar_config(payload)
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/mover":
                mover_colaborador(int(payload.get("id")), payload.get("campo"), payload.get("direcao"))
                return resposta_json(self, 200, {"ok": True})
        except Exception as exc:
            return resposta_json(self, 400, {"erro": str(exc)})
        return resposta_json(self, 404, {"erro": "Caminho nao encontrado."})

    def do_DELETE(self):
        path = urlparse(self.path).path
        qs = parse_qs(urlparse(self.path).query)
        try:
            if path == "/api/colaboradores":
                excluir_colaborador(int(qs.get("id", ["0"])[0]))
                return resposta_json(self, 200, {"ok": True})
            if path == "/api/item":
                excluir_tabela_item(qs.get("tabela", [""])[0], int(qs.get("id", ["0"])[0]))
                return resposta_json(self, 200, {"ok": True})
        except Exception as exc:
            return resposta_json(self, 400, {"erro": str(exc)})
        return resposta_json(self, 404, {"erro": "Caminho nao encontrado."})

    def enviar_arquivo(self, caminho, content_type=None):
        caminho = caminho.resolve()
        base = STATIC_DIR.resolve()
        if base not in caminho.parents or not caminho.exists() or not caminho.is_file():
            return resposta_json(self, 404, {"erro": "Arquivo nao encontrado."})
        dados = caminho.read_bytes()
        tipo = content_type or mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def ler_json(self):
        tamanho = int(self.headers.get("Content-Length", "0") or "0")
        if not tamanho:
            return {}
        return json.loads(self.rfile.read(tamanho).decode("utf-8") or "{}")


def main():
    criar_banco()
    servidor = ThreadingHTTPServer((HOST, PORT), Handler)
    print("")
    print("Gerador de Escalas rodando.")
    print(f"Abra no navegador: http://localhost:{PORT}")
    print("")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
