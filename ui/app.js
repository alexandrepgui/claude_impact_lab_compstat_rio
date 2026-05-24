const state = {
  steps: [],
  run: null,
  poll: null,
  lastRunStatus: null,
  lab: {
    original: null,
    draft: null,
    path: "",
    loaded: false,
    diff: { current: null, previous: null },
    statusKind: "idle",
  },
  relatorios: {
    loaded: false,
    items: [],
    loading: false,
  },
};

const STRUCTURAL_KEYS = [
  { key: "janela_semanas", label: "Janela (sem.)", type: "int", min: 1, step: 1 },
  { key: "grade_m", label: "Grade (m)", type: "int", min: 50, step: 50 },
  { key: "cobertura", label: "Cobertura", type: "float", min: 0, max: 1, step: 0.05 },
  { key: "min_share_zona", label: "Min share zona", type: "float", min: 0, max: 1, step: 0.005 },
  { key: "n_agentes", label: "Nº agentes", type: "int", min: 1, step: 10 },
];

const els = {
  navItems: document.querySelectorAll(".nav-item"),
  pagePanels: document.querySelectorAll(".app-page"),
  jobs: document.querySelector("#jobs"),
  deps: document.querySelector("#deps"),
  runBadge: document.querySelector("#runBadge"),
  runButton: document.querySelector("#runButton"),
  stopButton: document.querySelector("#stopButton"),
  fromStep: document.querySelector("#fromStep"),
  skipStub: document.querySelector("#skipStub"),
  dryRun: document.querySelector("#dryRun"),
  selectedSteps: document.querySelector("#selectedSteps"),
  scorePanel: document.querySelector("#scorePanel"),
  console: document.querySelector("#console"),
  auditLog: document.querySelector("#auditLog"),
  labRunBadge: document.querySelector("#labRunBadge"),
  labConfigPath: document.querySelector("#labConfigPath"),
  labSave: document.querySelector("#labSave"),
  labRerun: document.querySelector("#labRerun"),
  labReset: document.querySelector("#labReset"),
  labStatus: document.querySelector("#labStatus"),
  labStructural: document.querySelector("#labStructural"),
  labLayersBody: document.querySelector("#labLayersBody"),
  labDiffPanel: document.querySelector("#labDiffPanel"),
  labConsole: document.querySelector("#labConsole"),
  relatoriosGrid: document.querySelector("#relatoriosGrid"),
  relatoriosStatus: document.querySelector("#relatoriosStatus"),
  relatoriosRefresh: document.querySelector("#relatoriosRefresh"),
};

function showPage(page) {
  els.navItems.forEach((item) => {
    const active = item.dataset.page === page;
    item.classList.toggle("active", active);
    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });

  els.pagePanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.pagePanel === page);
  });

  if (page === "lab" && !state.lab.loaded) {
    loadLabConfig();
    loadLabSnapshot();
  }
  if (page === "relatorio") {
    loadRelatorios();
  }
}

async function loadRelatorios() {
  if (state.relatorios.loading) return;
  state.relatorios.loading = true;
  if (els.relatoriosStatus) {
    els.relatoriosStatus.textContent = "Carregando relatorios...";
  }
  try {
    const r = await fetch("/api/relatorios");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    state.relatorios.items = data.relatorios || [];
    state.relatorios.loaded = true;
    renderRelatorios();
  } catch (e) {
    if (els.relatoriosStatus) {
      els.relatoriosStatus.textContent = `Falha ao carregar: ${e.message}`;
    }
  } finally {
    state.relatorios.loading = false;
  }
}

function renderRelatorios() {
  const items = state.relatorios.items;
  if (!els.relatoriosGrid) return;
  els.relatoriosGrid.innerHTML = "";

  if (items.length === 0) {
    if (els.relatoriosStatus) {
      els.relatoriosStatus.textContent =
        "Nenhum relatorio gerado ainda. Rode o step 6 (pipeline) para gerar.";
    }
    return;
  }

  if (els.relatoriosStatus) {
    els.relatoriosStatus.textContent = `${items.length} relatorio(s) prontos.`;
  }

  for (const item of items) {
    const card = document.createElement("article");
    card.className = "relatorio-card";

    if (item.mapPng) {
      const img = document.createElement("img");
      img.src = `/api/relatorios/file/${encodeURIComponent(item.mapPng)}`;
      img.alt = `Mapa ${item.displayName}`;
      img.loading = "lazy";
      card.appendChild(img);
    } else {
      const noimg = document.createElement("div");
      noimg.className = "relatorio-noimg";
      noimg.textContent = "(sem mapa)";
      card.appendChild(noimg);
    }

    const body = document.createElement("div");
    body.className = "relatorio-card-body";

    const title = document.createElement("h3");
    title.textContent = item.displayName;
    body.appendChild(title);

    const meta = document.createElement("p");
    meta.className = "muted";
    const mtime = item.mtime ? new Date(item.mtime).toLocaleString() : "?";
    meta.textContent = `${item.sizeKB} KB · ${mtime}`;
    body.appendChild(meta);

    const dl = document.createElement("a");
    dl.className = "primary";
    dl.href = `/api/relatorios/file/${encodeURIComponent(item.name)}`;
    dl.textContent = "Baixar .docx";
    dl.setAttribute("download", item.name);
    body.appendChild(dl);

    card.appendChild(body);
    els.relatoriosGrid.appendChild(card);
  }
}

function statusLabel(status) {
  const labels = {
    queued: "na fila",
    running: "rodando",
    success: "ok",
    failed: "falhou",
    skipped: "pulado",
    stopped: "parado",
    blocked: "bloqueado",
    planned: "planejado",
  };
  return labels[status] || status || "idle";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function selectedIds() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  let ids = state.steps.map((step) => step.id);
  if (mode === "from") {
    const start = els.fromStep.value;
    ids = ids.slice(ids.indexOf(start));
  }
  if (mode === "only") {
    ids = Array.from(document.querySelectorAll(".step-check:checked")).map((input) => input.value);
  }
  if (els.skipStub.checked) {
    ids = ids.filter((id) => id !== "3");
  }
  return ids;
}

function renderJobs() {
  const selected = new Set(selectedIds());
  const runSteps = state.run?.steps || {};

  els.jobs.innerHTML = state.steps
    .map((step) => {
      const runStatus = runSteps[step.id]?.status;
      const status = runStatus || (selected.has(step.id) ? "queued" : "skipped");
      const outputs = step.outputs.map((out) => `<code>${out}</code>`).join("");
      return `
        <article class="job">
          <div class="job-id">${step.id}</div>
          <div>
            <div class="job-title">
              <label>
                <input class="step-check" type="checkbox" value="${step.id}" ${selected.has(step.id) ? "checked" : ""} />
              </label>
              <strong>${step.name}</strong>
              ${step.critical ? '<span class="critical">critico</span>' : ""}
            </div>
            <p>${step.hint}</p>
            <p>Owner: ${step.owner} · Script: ${step.script}</p>
            <div class="outputs">${outputs}</div>
          </div>
          <div class="status ${status}">${statusLabel(status)}</div>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".step-check").forEach((input) => {
    input.addEventListener("change", () => {
      document.querySelector("input[name='mode'][value='only']").checked = true;
      renderAll();
    });
  });
}

function renderSelection() {
  const ids = selectedIds();
  els.selectedSteps.innerHTML = ids
    .map((id) => {
      const step = state.steps.find((item) => item.id === id);
      return `<div class="selected-pill"><span>${id}. ${step.name}</span><span>${step.critical ? "critico" : "nao critico"}</span></div>`;
    })
    .join("");
}

function renderRun(run) {
  state.run = run;
  const active = ["starting", "running", "stopping"].includes(run?.status);
  els.runButton.disabled = active;
  els.stopButton.disabled = !active;
  els.runBadge.className = `run-badge ${run?.status || ""}`;
  els.runBadge.textContent = run ? run.status : "sem execucao";

  if (!run?.logs?.length) {
    els.console.textContent = "Aguardando execucao...";
  } else {
    els.console.textContent = run.logs.map((entry) => entry.line).join("\n");
    els.console.scrollTop = els.console.scrollHeight;
  }

  renderLabRun(run, active);
}

function renderLabRun(run, active) {
  if (!els.labRunBadge) return;
  const isLabKind = run?.kind === "lab_rescore";

  els.labRunBadge.className = `run-badge ${isLabKind ? run?.status || "" : ""}`;
  els.labRunBadge.textContent = isLabKind ? run.status : "sem execucao";

  if (els.labConsole) {
    if (isLabKind && run.logs?.length) {
      els.labConsole.textContent = run.logs.map((entry) => entry.line).join("\n");
      els.labConsole.scrollTop = els.labConsole.scrollHeight;
    } else if (!isLabKind && !run) {
      els.labConsole.textContent = "Aguardando execucao...";
    }
  }

  if (els.labRerun && els.labSave) {
    els.labRerun.disabled = active;
    els.labSave.disabled = isLabKind && active;
  }

  if (isLabKind) {
    if (run.status === "starting" || run.status === "running") {
      setLabStatus("Re-executando motor + step 5...", "running");
    } else if (run.status === "success") {
      setLabStatus("Score atualizado.", "ok");
    } else if (run.status === "failed") {
      setLabStatus("Falha na re-execucao. Veja os logs.", "failed");
    } else if (run.status === "stopped") {
      setLabStatus("Re-execucao interrompida.", "failed");
    }
  } else if (active) {
    setLabStatus("Pipeline rodando em outra aba; aguarde.", "running");
  }
}

function renderScore(score) {
  if (!score?.ranking?.length) {
    els.scorePanel.innerHTML = `<p class="muted">Ainda sem score_ranking.json.</p>`;
    return;
  }
  const meta = [score.version, score.scoreField, score.total ? `${score.total} linhas` : null]
    .filter(Boolean)
    .map(escapeHtml)
    .join(" · ");
  const rows = score.ranking
    .map((row) => {
      const label = row.week ? `${row.name} · sem. ${row.week}` : row.name;
      return `
        <div class="score-row">
          <span>#${row.rank}</span>
          <strong title="${escapeHtml(label)}">${escapeHtml(label)}</strong>
          <span>${Number(row.score).toFixed(3)}</span>
        </div>
      `;
    })
    .join("");
  els.scorePanel.innerHTML = `
    ${meta ? `<p class="score-meta">${meta}</p>` : ""}
    ${rows}
  `;
}

function renderAll() {
  renderJobs();
  renderSelection();
}

async function loadPipeline() {
  const response = await fetch("/api/pipeline");
  const data = await response.json();
  state.steps = data.steps;
  renderRun(data.run);
  renderScore(data.score);
  els.deps.textContent = `deps: ${Object.keys(data.requiredDeps).join(", ")} · LLM: ${data.llmMode}`;
  els.auditLog.textContent = data.auditLog;
  els.fromStep.innerHTML = state.steps.map((step) => `<option value="${step.id}">${step.id}</option>`).join("");
  renderAll();
  ensurePolling();
}

function payloadFromControls() {
  const mode = document.querySelector("input[name='mode']:checked").value;
  const payload = {
    mode,
    fromStep: els.fromStep.value,
    dryRun: els.dryRun.checked,
    skip: els.skipStub.checked ? ["3"] : [],
  };
  if (mode === "only") {
    payload.steps = selectedIds();
  }
  return payload;
}

async function pollRun() {
  try {
    const response = await fetch("/api/runs/current");
    const data = await response.json();
    const previousStatus = state.lastRunStatus;
    const nextStatus = data.run?.status || null;
    const wasActive = ["starting", "running", "stopping"].includes(previousStatus);
    const isActive = ["starting", "running", "stopping"].includes(nextStatus);
    const isLabKind = data.run?.kind === "lab_rescore";

    renderRun(data.run);
    renderAll();
    state.lastRunStatus = nextStatus;

    if (wasActive && !isActive) {
      await refreshScore();
      if (isLabKind || state.lab.loaded) {
        await loadLabSnapshot();
      }
    }
  } catch (error) {
    els.runBadge.className = "run-badge failed";
    els.runBadge.textContent = "offline";
  }
}

async function refreshScore() {
  const response = await fetch("/api/pipeline");
  const data = await response.json();
  renderScore(data.score);
}

function ensurePolling() {
  if (state.poll) return;
  state.poll = setInterval(pollRun, 900);
}

async function startRun() {
  const response = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payloadFromControls()),
  });
  const data = await response.json();
  if (!response.ok) {
    els.console.textContent = data.error || "Erro ao iniciar.";
    return;
  }
  renderRun(data.run);
  renderAll();
  state.lastRunStatus = data.run?.status || null;
  ensurePolling();
}

async function stopRun() {
  await fetch("/api/runs/current/stop", { method: "POST" });
  await pollRun();
}

document.querySelectorAll("input[name='mode']").forEach((input) => {
  input.addEventListener("change", renderAll);
});
els.fromStep.addEventListener("change", renderAll);
els.skipStub.addEventListener("change", renderAll);
els.dryRun.addEventListener("change", renderAll);
els.runButton.addEventListener("click", startRun);
els.stopButton.addEventListener("click", stopRun);
els.navItems.forEach((item) => {
  item.addEventListener("click", () => showPage(item.dataset.page));
});

// ---- Lab page ----------------------------------------------------------

function deepClone(value) {
  return JSON.parse(JSON.stringify(value));
}

function setLabStatus(message, kind = "idle") {
  if (!els.labStatus) return;
  els.labStatus.textContent = message;
  els.labStatus.className = `lab-status ${kind}`;
  state.lab.statusKind = kind;
}

function isDirty() {
  return (
    state.lab.original &&
    state.lab.draft &&
    JSON.stringify(state.lab.original) !== JSON.stringify(state.lab.draft)
  );
}

function refreshDirtyIndicator() {
  const dirty = isDirty();
  if (state.lab.statusKind !== "running" && state.lab.statusKind !== "saving") {
    setLabStatus(
      dirty ? "Alteracoes nao salvas." : "Sem alteracoes.",
      dirty ? "dirty" : "idle",
    );
  }
  if (!state.lab.draft || !state.lab.original) return;
  document.querySelectorAll("[data-lab-field]").forEach((node) => {
    const fieldPath = node.dataset.labField;
    const dirtyField = fieldDirty(fieldPath);
    node.classList.toggle("dirty", dirtyField);
  });
}

function fieldDirty(path) {
  const a = getPath(state.lab.original, path);
  const b = getPath(state.lab.draft, path);
  return JSON.stringify(a) !== JSON.stringify(b);
}

function getPath(obj, path) {
  return path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
}

function setPath(obj, path, value) {
  const keys = path.split(".");
  let cursor = obj;
  for (let i = 0; i < keys.length - 1; i += 1) {
    if (cursor[keys[i]] == null) cursor[keys[i]] = {};
    cursor = cursor[keys[i]];
  }
  cursor[keys[keys.length - 1]] = value;
}

function renderLab() {
  if (!state.lab.draft) return;
  renderLabStructural();
  renderLabLayers();
  refreshDirtyIndicator();
}

function renderLabStructural() {
  if (!els.labStructural) return;
  const html = STRUCTURAL_KEYS.map(({ key, label, type, min, max, step }) => {
    const value = state.lab.draft[key];
    if (value === undefined) return "";
    const attrs = [
      `data-lab-field="${key}"`,
      `data-lab-type="${type}"`,
      `type="number"`,
      `step="${step ?? (type === "int" ? 1 : 0.01)}"`,
      min !== undefined ? `min="${min}"` : "",
      max !== undefined ? `max="${max}"` : "",
      `value="${escapeHtml(value)}"`,
    ]
      .filter(Boolean)
      .join(" ");
    return `
      <div class="lab-field" data-lab-field="${key}">
        <label for="lab-input-${key}">${label}</label>
        <input id="lab-input-${key}" ${attrs} />
      </div>
    `;
  }).join("");
  els.labStructural.innerHTML = html;
  els.labStructural.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", onStructuralInput);
  });
}

function onStructuralInput(event) {
  const target = event.target;
  const path = target.dataset.labField;
  const type = target.dataset.labType;
  const raw = target.value;
  if (raw === "") return;
  const parsed = type === "int" ? parseInt(raw, 10) : parseFloat(raw);
  if (Number.isNaN(parsed)) return;
  setPath(state.lab.draft, path, parsed);
  refreshDirtyIndicator();
}

function renderLabLayers() {
  if (!els.labLayersBody) return;
  const camadas = state.lab.draft.camadas || {};
  els.labLayersBody.innerHTML = Object.entries(camadas)
    .map(([name, layer]) => renderLayerCard(name, layer))
    .join("");

  els.labLayersBody.querySelectorAll("[data-lab-action='toggle-active']").forEach((input) => {
    input.addEventListener("change", (event) => {
      const layerName = event.target.dataset.layer;
      setPath(state.lab.draft, `camadas.${layerName}.ativa`, event.target.checked);
      renderLabLayers();
      refreshDirtyIndicator();
    });
  });

  els.labLayersBody.querySelectorAll("[data-lab-action='layer-number']").forEach((input) => {
    input.addEventListener("input", (event) => {
      const path = event.target.dataset.labField;
      const value = parseFloat(event.target.value);
      if (Number.isNaN(value)) return;
      setPath(state.lab.draft, path, value);
      refreshDirtyIndicator();
    });
  });

  els.labLayersBody.querySelectorAll("[data-lab-action='cat-key']").forEach((input) => {
    input.addEventListener("change", (event) => onCatKeyChange(event));
  });

  els.labLayersBody.querySelectorAll("[data-lab-action='cat-value']").forEach((input) => {
    input.addEventListener("input", (event) => {
      const layer = event.target.dataset.layer;
      const cat = event.target.dataset.cat;
      const value = parseFloat(event.target.value);
      if (Number.isNaN(value)) return;
      state.lab.draft.camadas[layer].pesos_categoria[cat] = value;
      refreshDirtyIndicator();
    });
  });

  els.labLayersBody.querySelectorAll("[data-lab-action='cat-remove']").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const layer = event.currentTarget.dataset.layer;
      const cat = event.currentTarget.dataset.cat;
      delete state.lab.draft.camadas[layer].pesos_categoria[cat];
      renderLabLayers();
      refreshDirtyIndicator();
    });
  });

  els.labLayersBody.querySelectorAll("[data-lab-action='cat-add']").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const layer = event.currentTarget.dataset.layer;
      const next = state.lab.draft.camadas[layer];
      next.pesos_categoria = next.pesos_categoria || {};
      let key = "Nova categoria";
      let i = 1;
      while (key in next.pesos_categoria) {
        i += 1;
        key = `Nova categoria ${i}`;
      }
      next.pesos_categoria[key] = 1.0;
      renderLabLayers();
      refreshDirtyIndicator();
    });
  });
}

function onCatKeyChange(event) {
  const layer = event.target.dataset.layer;
  const oldKey = event.target.dataset.cat;
  const newKey = event.target.value.trim();
  const camada = state.lab.draft.camadas[layer];
  if (!newKey || newKey === oldKey) {
    event.target.value = oldKey;
    return;
  }
  if (newKey in camada.pesos_categoria) {
    setLabStatus(`Categoria "${newKey}" ja existe em ${layer}.`, "failed");
    event.target.value = oldKey;
    return;
  }
  const value = camada.pesos_categoria[oldKey];
  delete camada.pesos_categoria[oldKey];
  camada.pesos_categoria[newKey] = value;
  renderLabLayers();
  refreshDirtyIndicator();
}

function renderLayerCard(name, layer) {
  const ativa = layer.ativa !== false;
  const peso = layer.peso ?? 1.0;
  const campoCategoria = layer.campo_categoria ?? "";
  const pesoDefault = layer.peso_categoria_default ?? 1.0;
  const pesos = layer.pesos_categoria || {};
  const catsHtml = Object.entries(pesos)
    .map(([cat, val]) => {
      return `
        <div class="lab-cat-row" data-lab-field="camadas.${name}.pesos_categoria.${cat}">
          <input
            type="text"
            value="${escapeHtml(cat)}"
            data-lab-action="cat-key"
            data-layer="${name}"
            data-cat="${escapeHtml(cat)}"
            aria-label="Categoria"
          />
          <input
            type="number"
            step="0.1"
            value="${val}"
            data-lab-action="cat-value"
            data-layer="${name}"
            data-cat="${escapeHtml(cat)}"
            aria-label="Peso da categoria"
          />
          <button
            type="button"
            class="lab-cat-remove"
            data-lab-action="cat-remove"
            data-layer="${name}"
            data-cat="${escapeHtml(cat)}"
            aria-label="Remover categoria"
            title="Remover"
          >×</button>
        </div>
      `;
    })
    .join("");

  return `
    <article class="lab-layer" data-layer="${name}">
      <header class="lab-layer-head">
        <div class="lab-layer-name">
          <span>${escapeHtml(name)}</span>
          <span class="lab-source">${escapeHtml(campoCategoria)}</span>
        </div>
        <label class="lab-toggle ${ativa ? "active" : ""}">
          <input
            type="checkbox"
            data-lab-action="toggle-active"
            data-layer="${name}"
            ${ativa ? "checked" : ""}
          />
          <span>${ativa ? "Ativa" : "Inativa"}</span>
        </label>
      </header>

      <div class="lab-layer-grid">
        <div class="lab-field" data-lab-field="camadas.${name}.peso">
          <label>Peso da camada</label>
          <input
            type="number"
            step="0.05"
            min="0"
            value="${peso}"
            data-lab-action="layer-number"
            data-lab-field="camadas.${name}.peso"
          />
        </div>
        <div class="lab-field" data-lab-field="camadas.${name}.peso_categoria_default">
          <label>Peso default (categoria)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            value="${pesoDefault}"
            data-lab-action="layer-number"
            data-lab-field="camadas.${name}.peso_categoria_default"
          />
        </div>
      </div>

      <div class="lab-cats">
        <div class="lab-cats-head">
          <p>Pesos por categoria</p>
          <button
            type="button"
            class="lab-cat-add"
            data-lab-action="cat-add"
            data-layer="${name}"
          >+ adicionar</button>
        </div>
        ${catsHtml || `<p class="muted">Nenhuma categoria customizada — usando peso default.</p>`}
      </div>
    </article>
  `;
}

async function loadLabConfig() {
  setLabStatus("Carregando config...", "running");
  try {
    const response = await fetch("/api/lab/config");
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${response.status}`);
    }
    const data = await response.json();
    state.lab.original = deepClone(data.config);
    state.lab.draft = deepClone(data.config);
    state.lab.path = data.path || "";
    state.lab.loaded = true;
    if (els.labConfigPath && data.path) {
      els.labConfigPath.textContent = data.path;
    }
    renderLab();
    setLabStatus("Sem alteracoes.", "idle");
  } catch (error) {
    setLabStatus(`Erro: ${error.message}`, "failed");
  }
}

async function loadLabSnapshot() {
  try {
    const response = await fetch("/api/lab/snapshot");
    if (!response.ok) return;
    const data = await response.json();
    state.lab.diff = data;
    renderLabDiff();
  } catch (error) {
    // silent — snapshot is optional
  }
}

function renderLabDiff() {
  if (!els.labDiffPanel) return;
  const cur = state.lab.diff?.current?.ranking || [];
  const prev = state.lab.diff?.previous?.ranking || [];
  if (!cur.length && !prev.length) {
    els.labDiffPanel.innerHTML = `<p class="muted">Execute uma vez para gerar a baseline.</p>`;
    return;
  }
  const prevMap = new Map(prev.map((r) => [r.name, r.rank]));
  const rows = cur.slice(0, 8).map((row) => {
    const prevRank = prevMap.get(row.name);
    let delta = "—";
    let cls = "";
    if (prevRank === undefined) {
      delta = "novo";
      cls = "new";
    } else if (prevRank > row.rank) {
      delta = `▲${prevRank - row.rank}`;
      cls = "up";
    } else if (prevRank < row.rank) {
      delta = `▼${row.rank - prevRank}`;
      cls = "down";
    } else {
      delta = "=";
    }
    const label = row.week ? `${row.name} · sem. ${row.week}` : row.name;
    return `
      <div class="lab-diff-row">
        <span>#${row.rank}</span>
        <strong title="${escapeHtml(label)}">${escapeHtml(label)}</strong>
        <span class="lab-diff-score">${Number(row.score).toFixed(3)}</span>
        <span class="lab-diff-delta ${cls}">${delta}</span>
      </div>
    `;
  });
  const head = state.lab.diff?.previous
    ? `<p class="score-meta muted">vs. baseline anterior</p>`
    : `<p class="score-meta muted">Sem baseline anterior — primeira execucao</p>`;
  els.labDiffPanel.innerHTML = head + rows.join("");
}

async function saveLabConfig() {
  if (!state.lab.draft) return false;
  setLabStatus("Salvando...", "saving");
  try {
    const response = await fetch("/api/lab/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config: state.lab.draft }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    state.lab.original = deepClone(data.config);
    state.lab.draft = deepClone(data.config);
    renderLab();
    setLabStatus("Config salva.", "ok");
    return true;
  } catch (error) {
    setLabStatus(`Erro ao salvar: ${error.message}`, "failed");
    return false;
  }
}

async function saveAndRerun() {
  const saved = await saveLabConfig();
  if (!saved) return;
  setLabStatus("Iniciando re-execucao...", "running");
  try {
    const response = await fetch("/api/lab/rerun", { method: "POST" });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }
    state.lastRunStatus = data.run?.status || null;
    renderRun(data.run);
    ensurePolling();
  } catch (error) {
    setLabStatus(`Erro ao iniciar: ${error.message}`, "failed");
  }
}

function resetLab() {
  if (!state.lab.original) return;
  state.lab.draft = deepClone(state.lab.original);
  renderLab();
}

if (els.labSave) els.labSave.addEventListener("click", saveLabConfig);
if (els.labRerun) els.labRerun.addEventListener("click", saveAndRerun);
if (els.labReset) els.labReset.addEventListener("click", resetLab);
if (els.relatoriosRefresh) {
  els.relatoriosRefresh.addEventListener("click", () => {
    state.relatorios.loaded = false;
    loadRelatorios();
  });
}

loadPipeline();
