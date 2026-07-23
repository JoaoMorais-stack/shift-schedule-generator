let state = {
    colaboradores: [],
    config: {},
    rotacao_status: {},
    escala: [],
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const inicioInput = $("#inicio");
const fimInput = $("#fim");
const escalaBody = $("#escalaBody");
const toast = $("#toast");
const modal = $("#modal");
const formLinha = $("#formLinha");

function hojeISO() {
    return new Date().toISOString().slice(0, 10);
}

function fimMesISO() {
    const hoje = new Date();
    return new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).toISOString().slice(0, 10);
}

function periodoDemonstracao() {
    inicioInput.value = "2026-06-01";
    fimInput.value = "2026-06-30";
    $("#formConsulta").elements.inicio.value = "2026-06-01";
    $("#formConsulta").elements.fim.value = "2026-06-30";
}

function toastMsg(texto, erro = false) {
    toast.textContent = texto;
    toast.classList.toggle("erro", erro);
    toast.classList.remove("oculto");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => toast.classList.add("oculto"), 2600);
}

async function api(url, opts = {}) {
    const resp = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...opts,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.erro || "Nao foi possivel concluir.");
    return data;
}

function esc(v) {
    return String(v ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function dataBR(iso) {
    if (!iso) return "-";
    const p = iso.split("-");
    return p.length === 3 ? `${p[2]}/${p[1]}/${p[0]}` : iso;
}

function nomeColaborador(m) {
    return `${m.funcao || ""} ${m.nome_curto || ""}`.trim();
}

function optionsColaboradores(valor = "", vazio = true) {
    const first = vazio ? `<option value="">Nenhum / escolher</option>` : "";
    return (
        first +
        state.colaboradores
            .map((m) => `<option value="${m.id}" ${String(valor) === String(m.id) ? "selected" : ""}>${esc(nomeColaborador(m))}</option>`)
            .join("")
    );
}

function hydrateSelects() {
    ["marco_regular_id", "marco_especial_id", "marco_prioritaria_id"].forEach((id) => {
        $(`#${id}`).innerHTML = optionsColaboradores(state.config[id] || "", true);
    });
    ["marco_regular_data", "marco_especial_data", "marco_prioritaria_data"].forEach((id) => {
        const input = $(`#${id}`);
        if (input) input.value = state.config[id] || "";
    });
    $$("select[name='colaborador_id']").forEach((sel) => {
        const atual = sel.value;
        sel.innerHTML = optionsColaboradores(atual, true);
    });
}

function renderRotacao() {
    const rot = [...state.colaboradores].filter((m) => m.participa_escala).sort((a, b) => a.ordem_rotacao - b.ordem_rotacao);
    $("#listaRotacao").innerHTML = rot
        .map(
            (m, idx) => `
            <div class="mini-row">
                <span>${idx + 1}</span>
                <strong>${esc(nomeColaborador(m))}</strong>
                <div class="ordem-actions">
                    <button class="icon-btn mover" data-id="${m.id}" data-campo="ordem_rotacao" data-dir="up" title="Subir">↑</button>
                    <button class="icon-btn mover" data-id="${m.id}" data-campo="ordem_rotacao" data-dir="down" title="Descer">↓</button>
                </div>
            </div>
        `
        )
        .join("");
}

function renderRotacaoStatus() {
    const tipos = state.rotacao_status?.tipos || {};
    const ordem = ["regular", "especial", "prioritaria"];
    $("#rotacaoStatus").innerHTML = ordem
        .map((tipo) => {
            const item = tipos[tipo] || {};
            const realizada = item.realizada
                ? `${item.realizada.colaborador_nome} em ${item.realizada.data_br}`
                : "Nenhuma realizada até hoje";
            const prevista = item.prevista
                ? `${item.prevista.colaborador_nome} em ${item.prevista.data_br}`
                : "Nenhuma futura salva";
            const marco = item.marco?.colaborador_nome && item.marco?.data
                ? `${item.marco.colaborador_nome} em ${dataBR(item.marco.data)}`
                : "Não definido";
            return `
                <div class="rotacao-card ${tipo}">
                    <strong>${esc(item.label || tipo)}</strong>
                    <span><b>Marco confirmado:</b> ${esc(marco)}</span>
                    <span><b>Já realizado:</b> ${esc(realizada)}</span>
                    <span><b>Próximo salvo:</b> ${esc(prevista)}</span>
                </div>
            `;
        })
        .join("");
}

function renderColaboradores() {
    const ordemExibicao = [...state.colaboradores].sort((a, b) => a.ordem_exibicao - b.ordem_exibicao);
    $("#colaboradoresEditor").innerHTML = ordemExibicao
        .map(
            (m) => `
            <details class="colaborador-card">
                <summary class="top">
                    <div>
                        <strong>${esc(nomeColaborador(m))}</strong>
                        <small>${esc(m.nome_completo || "")}</small>
                    </div>
                    <div class="ordem-actions">
                        <button class="icon-btn mover" data-id="${m.id}" data-campo="ordem_exibicao" data-dir="up" title="Mover para cima">↑</button>
                        <button class="icon-btn mover" data-id="${m.id}" data-campo="ordem_exibicao" data-dir="down" title="Mover para baixo">↓</button>
                    </div>
                </summary>
                <form class="colaborador-form" data-id="${m.id}">
                    <div class="duo">
                        <input name="funcao" value="${esc(m.funcao)}" placeholder="Função">
                        <input name="nome_curto" value="${esc(m.nome_curto)}" placeholder="Nome curto">
                    </div>
                    <input name="nome_completo" value="${esc(m.nome_completo)}" placeholder="Nome completo">
                    <input name="telefone" value="${esc(m.telefone)}" placeholder="Telefone">
                    <div class="flags">
                        <label><input name="ativo" type="checkbox" ${m.ativo ? "checked" : ""}> Ativo</label>
                        <label><input name="participa_escala" type="checkbox" ${m.participa_escala ? "checked" : ""}> Entra na escala</label>
                    </div>
                    <div class="duo">
                        <button class="btn small" type="submit">Salvar</button>
                        <button class="btn small danger remover-colaborador" type="button" data-id="${m.id}">Remover</button>
                    </div>
                </form>
            </details>
        `
        )
        .join("");
}

function chip(texto, detalhe, tabela, id) {
    return `
        <div class="chip">
            <strong>${esc(texto)}</strong>
            <span>${esc(detalhe)}</span>
            <div class="chip-actions">
                <button class="btn small danger remover-item" data-tabela="${tabela}" data-id="${id}" type="button">Remover</button>
            </div>
        </div>
    `;
}

function renderListasExtras(data) {
    renderFeriasAgrupadas(data.ferias);
    $("#indisponibilidadesLista").innerHTML = data.indisponibilidades
        .map((b) => chip(b.colaborador_nome, `${dataBR(b.inicio)} a ${dataBR(b.fim)} | ${b.motivo} | ${b.categorias}`, "indisponibilidades", b.id))
        .join("");
    $("#feriadosLista").innerHTML = data.feriados
        .map((f) => chip(f.nome, `${dataBR(f.data)} | ${f.tipo}`, "feriados_custom", f.id))
        .join("");
    renderTurnos(data.turnos);
}

function renderFeriasAgrupadas(ferias) {
    const grupos = new Map();
    ferias.forEach((f) => {
        const key = f.colaborador_id;
        if (!grupos.has(key)) grupos.set(key, { nome: f.colaborador_nome, itens: [] });
        grupos.get(key).itens.push(f);
    });

    $("#feriasLista").innerHTML = [...grupos.values()]
        .map((grupo) => {
            const itens = grupo.itens
                .sort((a, b) => (a.periodo || 0) - (b.periodo || 0) || String(a.inicio).localeCompare(String(b.inicio)))
                .map(
                    (f) => `
                    <div class="periodo-ferias">
                        <div>
                            <strong>${f.periodo}º período</strong>
                            <span>${dataBR(f.inicio)} a ${dataBR(f.fim)} (${f.dias || 0} dias)</span>
                        </div>
                        <button class="btn small danger remover-item" data-tabela="ferias" data-id="${f.id}" type="button">Remover</button>
                    </div>
                `
                )
                .join("");
            return `
                <details class="grupo-ferias">
                    <summary>
                        <strong>${esc(grupo.nome)}</strong>
                        <span>${grupo.itens.length} período(s)</span>
                    </summary>
                    <div class="grupo-ferias-body">${itens}</div>
                </details>
            `;
        })
        .join("");
}

function renderTurnos(turnos) {
    const grupos = new Map();
    turnos.forEach((p) => {
        const chave = `${p.horario} | ${p.equipe}`;
        grupos.set(chave, (grupos.get(chave) || 0) + 1);
    });

    $("#resumoTurnos").innerHTML = [...grupos.entries()]
        .map(([chave, total]) => `<span>${esc(chave)}: <strong>${total}</strong></span>`)
        .join("");

    $("#turnosSemana").innerHTML = turnos
        .map((p) => {
            const periodo = `${dataBR(p.inicio)}${p.fim ? " a " + dataBR(p.fim) : " em diante"}`;
            const conflitos = p.conflitos?.length
                ? `<div class="alerta-turno">${p.conflitos.map((c) => esc(c)).join("<br>")}</div>`
                : "";
            return `
                <div class="chip turno-chip ${p.conflitos?.length ? "com-conflito" : ""}">
                    <strong>${esc(p.horario)} - ${esc(p.equipe)}</strong>
                    <span>${esc(p.colaborador_nome || "Sem colaborador")} | ${periodo}</span>
                    ${conflitos}
                    <div class="chip-actions">
                        <button class="btn small editar-turno" data-turno='${esc(JSON.stringify(p))}' type="button">Editar</button>
                        <button class="btn small danger remover-item" data-tabela="turnos_semana" data-id="${p.id}" type="button">Remover</button>
                    </div>
                </div>
            `;
        })
        .join("");
}

function renderEscala() {
    $("#resumoEscala").textContent = state.escala.length
        ? `${state.escala.length} serviço(s) no período.`
        : "Nenhum serviço salvo neste período.";
    escalaBody.innerHTML = state.escala
        .map(
            (e) => `
            <tr class="${e.tipo} ${e.editado ? "editado" : ""}">
                <td><strong>${dataBR(e.data)}</strong></td>
                <td>${esc(e.dia_semana)}</td>
                <td><span class="badge ${e.tipo}">${esc(e.tipo_label)}</span></td>
                <td>${esc(e.colaborador_nome || "Sem colaborador")}</td>
                <td>${esc(e.origem || "")}</td>
                <td>${esc(e.observacao || "")}</td>
                <td><button class="btn small editar-linha" data-data="${e.data}" type="button">Editar</button></td>
            </tr>
        `
        )
        .join("");
}

async function carregarBootstrap() {
    const data = await api("/api/bootstrap");
    state.colaboradores = data.colaboradores;
    state.config = data.config;
    state.rotacao_status = data.rotacao_status;
    hydrateSelects();
    renderRotacaoStatus();
    renderRotacao();
    renderColaboradores();
    renderListasExtras(data);
}

async function carregarEscala() {
    const data = await api(`/api/escala?inicio=${inicioInput.value}&fim=${fimInput.value}`);
    state.escala = data.escala;
    renderEscala();
}

async function recarregarTudo() {
    await carregarBootstrap();
    await carregarEscala();
}

function abrirModal(linha) {
    formLinha.elements.data.value = linha.data;
    formLinha.elements.tipo.value = linha.tipo;
    formLinha.elements.colaborador_id.innerHTML = optionsColaboradores(linha.colaborador_id || "", true);
    formLinha.elements.origem.value = linha.origem || "";
    formLinha.elements.observacao.value = linha.observacao || "";
    modal.classList.remove("oculto");
}

function fecharModal() {
    modal.classList.add("oculto");
}

function totaisHTML(t) {
    return `
        <div class="total-card"><span>Total</span><strong>${t.total || 0}</strong></div>
        <div class="total-card"><span>Regular</span><strong>${t.regular || 0}</strong></div>
        <div class="total-card"><span>Especial</span><strong>${t.especial || 0}</strong></div>
        <div class="total-card"><span>Prioritaria</span><strong>${t.prioritaria || 0}</strong></div>
    `;
}

function renderConsulta(data) {
    $("#totaisConsulta").innerHTML = totaisHTML(data.totais);
    const ranking = data.ranking
        .map((r) => `<div class="resultado-row"><strong>${esc(r.nome)}</strong><span>Regular ${r.regular || 0} | Especial ${r.especial || 0} | Prioritaria ${r.prioritaria || 0} | Total ${r.total || 0}</span></div>`)
        .join("");
    const itens = data.itens
        .map((i) => `<div class="resultado-row"><strong>${dataBR(i.data)} - ${esc(i.colaborador_nome || "Sem colaborador")}</strong><span>${esc(i.tipo)} | ${esc(i.origem || "")}</span></div>`)
        .join("");
    const indisponibilidades = data.indisponibilidades.length
        ? `<h2>Indisponibilidades no período</h2>` +
          data.indisponibilidades
              .map((l) => `<div class="resultado-row"><strong>${esc(l.motivo)}</strong><span>${dataBR(l.inicio)} a ${dataBR(l.fim)} | ${esc(l.categorias)}</span></div>`)
              .join("")
        : "";
    $("#resultadoConsulta").innerHTML = `${ranking ? "<h2>Ranking</h2>" + ranking : ""}${itens ? "<h2>Serviços</h2>" + itens : ""}${indisponibilidades}`;
}

$("#btnMontarFaltantes").addEventListener("click", async () => {
    try {
        const res = await api("/api/gerar", {
            method: "POST",
            body: JSON.stringify({ inicio: inicioInput.value, fim: fimInput.value, overwrite: false }),
        });
        await recarregarTudo();
        toastMsg(`${res.total} serviço(s) conferidos no período.`);
    } catch (err) {
        toastMsg(err.message, true);
    }
});

$("#btnVerEscala").addEventListener("click", () => carregarEscala().catch((err) => toastMsg(err.message, true)));

$("#btnRefazerPeriodo").addEventListener("click", async () => {
    const ok = confirm("Refazer este período do zero? Isso pode trocar serviços gerados e edições manuais desse período.");
    if (!ok) return;
    try {
        const res = await api("/api/gerar", {
            method: "POST",
            body: JSON.stringify({ inicio: inicioInput.value, fim: fimInput.value, overwrite: true }),
        });
        await recarregarTudo();
        toastMsg(`${res.total} serviço(s) recalculados.`);
    } catch (err) {
        toastMsg(err.message, true);
    }
});

$("#btnSalvarConfig").addEventListener("click", async () => {
    try {
        await api("/api/config", {
            method: "POST",
            body: JSON.stringify({
                marco_regular_id: $("#marco_regular_id").value,
                marco_regular_data: $("#marco_regular_data").value,
                marco_especial_id: $("#marco_especial_id").value,
                marco_especial_data: $("#marco_especial_data").value,
                marco_prioritaria_id: $("#marco_prioritaria_id").value,
                marco_prioritaria_data: $("#marco_prioritaria_data").value,
            }),
        });
        await carregarBootstrap();
        toastMsg("Marcos confirmados salvos.");
    } catch (err) {
        toastMsg(err.message, true);
    }
});

$("#btnNovoColaborador").addEventListener("click", async () => {
    await api("/api/colaboradores", {
        method: "POST",
        body: JSON.stringify({ funcao: "Equipe", nome_curto: "Novo", nome_completo: "Novo Colaborador", ativo: true, participa_escala: true }),
    });
    await carregarBootstrap();
    toastMsg("Colaborador criado.");
});

document.body.addEventListener("click", async (event) => {
    const mover = event.target.closest(".mover");
    if (mover) {
        await api("/api/mover", { method: "POST", body: JSON.stringify({ id: mover.dataset.id, campo: mover.dataset.campo, direcao: mover.dataset.dir }) });
        await carregarBootstrap();
        return;
    }

    const removerColaborador = event.target.closest(".remover-colaborador");
    if (removerColaborador && confirm("Remover este colaborador?")) {
        await api(`/api/colaboradores?id=${removerColaborador.dataset.id}`, { method: "DELETE" });
        await recarregarTudo();
        return;
    }

    const removerItem = event.target.closest(".remover-item");
    if (removerItem) {
        await api(`/api/item?tabela=${removerItem.dataset.tabela}&id=${removerItem.dataset.id}`, { method: "DELETE" });
        await carregarBootstrap();
        return;
    }

    const editarTurno = event.target.closest(".editar-turno");
    if (editarTurno) {
        const turno = JSON.parse(editarTurno.dataset.turno);
        const form = $("#formTurno");
        form.elements.id.value = turno.id || "";
        form.elements.colaborador_id.value = turno.colaborador_id || "";
        form.elements.horario.value = turno.horario || "";
        form.elements.equipe.value = turno.equipe || "";
        form.elements.inicio.value = turno.inicio || "";
        form.elements.fim.value = turno.fim || "";
        form.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
    }

    const editar = event.target.closest(".editar-linha");
    if (editar) {
        const linha = state.escala.find((e) => e.data === editar.dataset.data);
        if (linha) abrirModal(linha);
    }
});

document.body.addEventListener("submit", async (event) => {
    const colaboradorForm = event.target.closest(".colaborador-form");
    if (colaboradorForm) {
        event.preventDefault();
        const fd = new FormData(colaboradorForm);
        await api("/api/colaboradores", {
            method: "POST",
            body: JSON.stringify({
                id: colaboradorForm.dataset.id,
                funcao: fd.get("funcao"),
                nome_curto: fd.get("nome_curto"),
                nome_completo: fd.get("nome_completo"),
                telefone: fd.get("telefone"),
                ativo: fd.get("ativo") === "on",
                participa_escala: fd.get("participa_escala") === "on",
            }),
        });
        await carregarBootstrap();
        toastMsg("Colaborador salvo.");
    }
});

$("#formIndisponibilidade").addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.target);
    await api("/api/indisponibilidades", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) });
    event.target.reset();
    await carregarBootstrap();
    toastMsg("Indisponibilidade adicionada.");
});

$("#formFeriado").addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.target);
    await api("/api/feriados", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) });
    event.target.reset();
    await carregarBootstrap();
    toastMsg("Feriado local salvo.");
});

$("#formFerias").addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.target);
    await api("/api/ferias", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) });
    event.target.reset();
    await carregarBootstrap();
    toastMsg("Férias adicionadas.");
});

$("#formTurno").addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.target);
    await api("/api/turnos", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) });
    event.target.reset();
    await carregarBootstrap();
    toastMsg("Turno salvo.");
});

$("#btnLimparTurno").addEventListener("click", () => $("#formTurno").reset());

$("#formConsulta").addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(event.target);
    const data = await api(`/api/consulta?inicio=${fd.get("inicio")}&fim=${fd.get("fim")}&colaborador_id=${fd.get("colaborador_id") || ""}`);
    renderConsulta(data);
});

formLinha.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(formLinha);
    await api("/api/escala", { method: "POST", body: JSON.stringify(Object.fromEntries(fd.entries())) });
    fecharModal();
    await carregarEscala();
    toastMsg("Dia salvo.");
});

$("#btnFecharModal").addEventListener("click", fecharModal);

[inicioInput, fimInput].forEach((input) => {
    input.addEventListener("change", () => carregarEscala().catch((err) => toastMsg(err.message, true)));
});

periodoDemonstracao();
recarregarTudo().catch((err) => toastMsg(err.message, true));

