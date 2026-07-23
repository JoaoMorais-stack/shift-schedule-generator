# Workforce Scheduling Demo

A local-first workforce scheduling application built with Python, SQLite, HTML, CSS, and vanilla JavaScript. It demonstrates employee rotation, availability constraints, planned leave, local holidays, weekly shifts, manual adjustments, and operational summaries without relying on external services.

> Project status: functional public demonstration. The bundled records are fictional and intended only for evaluation and learning.

## Features

- Maintain employees, roles, teams, display order, and rotation order.
- Generate assignments for weekends and configured holiday categories.
- Skip employees during planned leave or category-specific unavailability.
- Preserve manual adjustments when filling only missing dates.
- Rebuild a selected period when a complete recalculation is needed.
- Register recurring weekly shifts and highlight scheduling conflicts.
- Review totals, rankings, assignments, and employee-specific constraints.
- Store all application data locally in SQLite.

## Architecture

The project intentionally uses a small, dependency-free architecture:

- `app.py` contains the domain rules, SQLite persistence, JSON API, and local HTTP server.
- `static/` contains the responsive browser interface.
- `Data/` receives the local database created at runtime.
- `tests/` contains automated domain, persistence, and HTTP tests.

The application binds to the local machine only. It has no cloud integration, telemetry, analytics, or remote data transfer.

## Requirements

- Python 3.9 or newer.
- A modern web browser.

No third-party Python packages are required.

## Run locally

```powershell
python app.py
```

Open `http://localhost:5100` in a browser. On Windows, `iniciar_gerador.bat` performs the same startup flow and opens the page automatically.

The first launch creates `Data/escalas.db` and fills it with fictional demonstration records. Delete that generated database while the application is stopped to restore a fresh demo state.

## Tests

Run the complete automated suite from the project root:

```powershell
python -m unittest discover -s tests -v
```

The suite verifies date classification, employee rotation, availability rules, preservation of manual changes, database persistence, the JSON API, static file delivery, and path traversal protection.

## API overview

- `GET /api/bootstrap` returns employees, settings, leave, unavailability, holidays, and shifts.
- `GET /api/escala` returns assignments for a selected period.
- `GET /api/consulta` returns totals, ranking, assignments, and applicable constraints.
- `POST /api/gerar` generates or rebuilds assignments.
- Other `POST` routes maintain the local operational records used by the interface.

The API is designed for the included local interface and is not hardened for exposure to a public network.

## Privacy and security

- All included people, phone numbers, dates, and scenarios are fictional.
- Runtime databases, environment files, logs, caches, and generated artifacts are excluded from version control.
- The server listens only on the local machine by default.
- Static file delivery rejects paths outside the public asset directory.
- Do not use real personal or operational data in a public demonstration repository.

## Limitations

- Scheduling rules are illustrative and are not an optimization engine.
- Authentication and multi-user access are outside this demo's scope.
- Concurrent editing across several browser sessions is not coordinated.
- Holiday rules are tailored to the included demonstration calendar and can be extended in code or through local entries.

## Roadmap

- Separate the domain, persistence, and transport layers into dedicated modules.
- Add configurable rotation policies and fairness metrics.
- Add import and export for sanitized CSV templates.
- Expand accessibility and end-to-end browser coverage.
- Package an optional standalone desktop build.

## Project structure

```text
.
|-- app.py
|-- iniciar_gerador.bat
|-- requirements.txt
|-- static/
|   |-- index.html
|   |-- script.js
|   `-- style.css
|-- Data/
|   `-- .gitkeep
|-- tests/
|   `-- test_app.py
|-- README.md
|-- LICENSE
`-- .gitignore
```

## Contributing

This repository is published as a portfolio demonstration. Suggestions and issue reports are welcome. Reuse, redistribution, and derivative distribution require prior written permission from the copyright holder; see `LICENSE`.

---

# Demonstracao de Gerador de Escalas

Aplicacao local para planejamento de equipes, desenvolvida com Python, SQLite, HTML, CSS e JavaScript puro. O projeto demonstra rotacao de colaboradores, restricoes de disponibilidade, ferias planejadas, feriados locais, turnos semanais, ajustes manuais e resumos operacionais sem depender de servicos externos.

> Status do projeto: demonstracao publica funcional. Todos os registros incluidos sao ficticios e destinados apenas a avaliacao e aprendizado.

## Funcionalidades

- Cadastro de colaboradores, funcoes, equipes e ordens de exibicao e rotacao.
- Geracao de alocacoes para finais de semana e categorias de feriado configuradas.
- Exclusao automatica da rotacao durante ferias ou indisponibilidades aplicaveis.
- Preservacao de ajustes manuais ao preencher somente datas faltantes.
- Recálculo completo de um periodo selecionado quando necessario.
- Cadastro de turnos semanais com indicacao de conflitos.
- Consulta de totais, ranking, alocacoes e restricoes por colaborador.
- Persistencia inteiramente local em SQLite.

## Arquitetura

O projeto adota uma arquitetura pequena e sem dependencias de terceiros:

- `app.py` concentra regras de negocio, persistencia SQLite, API JSON e servidor HTTP local.
- `static/` contem a interface responsiva para navegador.
- `Data/` recebe o banco local criado durante a execucao.
- `tests/` contem testes automatizados de regras, persistencia e HTTP.

A aplicacao aceita conexoes apenas da propria maquina. Nao ha integracao em nuvem, telemetria, analytics ou envio remoto de dados.

## Requisitos

- Python 3.9 ou mais recente.
- Navegador moderno.

Nenhum pacote Python de terceiros e necessario.

## Executar localmente

```powershell
python app.py
```

Acesse `http://localhost:5100`. No Windows, `iniciar_gerador.bat` executa o mesmo fluxo e abre a pagina automaticamente.

Na primeira execucao, o sistema cria `Data/escalas.db` e inclui registros ficticios de demonstracao. Para restaurar o estado inicial, encerre a aplicacao e exclua esse banco gerado.

## Testes

Execute a suite completa a partir da raiz do projeto:

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem classificacao de datas, rotacao, disponibilidade, preservacao de alteracoes manuais, persistencia SQLite, API JSON, entrega de arquivos estaticos e protecao contra acesso indevido a caminhos.

## Visao geral da API

- `GET /api/bootstrap` retorna colaboradores, configuracoes, ferias, indisponibilidades, feriados e turnos.
- `GET /api/escala` retorna alocacoes do periodo selecionado.
- `GET /api/consulta` retorna totais, ranking, alocacoes e restricoes aplicaveis.
- `POST /api/gerar` gera ou recalcula alocacoes.
- As demais rotas `POST` mantem os registros locais usados pela interface.

A API foi projetada para a interface local incluida e nao deve ser exposta diretamente em uma rede publica.

## Privacidade e seguranca

- Todas as pessoas, telefones, datas e situacoes incluidas sao ficticias.
- Bancos gerados, arquivos de ambiente, logs, caches e artefatos de compilacao ficam fora do controle de versao.
- O servidor atende somente a propria maquina por padrao.
- A entrega de arquivos estaticos bloqueia caminhos fora da pasta publica.
- Nao utilize dados pessoais ou operacionais reais em uma demonstracao publica.

## Limitacoes

- As regras ilustram um fluxo de planejamento e nao formam um mecanismo de otimizacao.
- Autenticacao e acesso por varios usuarios nao fazem parte do escopo.
- Edicoes simultaneas em varias abas nao possuem coordenacao dedicada.
- O calendario incluido e demonstrativo e pode ser ampliado por codigo ou registros locais.

## Proximos passos

- Separar regras, persistencia e transporte em modulos dedicados.
- Adicionar politicas de rotacao configuraveis e metricas de equilibrio.
- Adicionar importacao e exportacao por modelos CSV sanitizados.
- Ampliar acessibilidade e testes de ponta a ponta no navegador.
- Criar um pacote desktop opcional.

## Contribuicao e uso

Este repositorio e publicado como demonstracao de portfolio. Sugestoes e relatos de problemas sao bem-vindos. Reutilizacao, redistribuicao e distribuicao de trabalhos derivados exigem autorizacao previa e escrita do titular; consulte `LICENSE`.

