const state = {
  steps: [],
  run: null,
  poll: null,
  lastRunStatus: null,
  audit: null,
};

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
  console: document.querySelector("#console"),
  auditLog: document.querySelector("#auditLog"),
  auditBadge: document.querySelector("#auditBadge"),
  auditMetrics: document.querySelector("#auditMetrics"),
  auditArtifacts: document.querySelector("#auditArtifacts"),
  auditEvents: document.querySelector("#auditEvents"),
  auditSteps: document.querySelector("#auditSteps"),
  auditRuns: document.querySelector("#auditRuns"),
  auditTopEvents: document.querySelector("#auditTopEvents"),
  refreshAuditButton: document.querySelector("#refreshAuditButton"),
};

const routes = {
  "/": "pipeline",
  "/pipeline": "pipeline",
  "/auditoria": "auditoria",
  "/relatorio": "relatorio",
  "/lab": "lab",
};

const pagePaths = Object.fromEntries(
  Object.entries(routes).map(([path, page]) => [page, page === "pipeline" ? "/pipeline" : path])
);

function pageFromPath(pathname) {
  const normalized = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  return routes[normalized] || "pipeline";
}

function showPage(page, options = {}) {
  const targetPage = pagePaths[page] ? page : "pipeline";
  els.navItems.forEach((item) => {
    const active = item.dataset.page === targetPage;
    item.classList.toggle("active", active);
    if (active) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  });

  els.pagePanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.pagePanel === targetPage);
  });

  if (options.updateHistory !== false) {
    const nextPath = pagePaths[targetPage];
    if (window.location.pathname !== nextPath) {
      window.history.pushState({ page: targetPage }, "", nextPath);
    }
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

function formatDateTime(value) {
  if (!value) return "sem registro";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "em aberto";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes}m ${rest}s`;
}

function compactJson(value) {
  const text = JSON.stringify(value || {}, null, 2);
  return escapeHtml(text.length > 900 ? `${text.slice(0, 900)}\n...` : text);
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
}

function renderAudit(data) {
  state.audit = data;
  els.auditBadge.textContent = data.path || "pipeline_audit.jsonl";

  const levels = data.levelCounts || {};
  els.auditMetrics.innerHTML = `
    <article class="metric-card">
      <span>Eventos</span>
      <strong>${Number(data.eventCount || 0).toLocaleString("pt-BR")}</strong>
      <small>${data.exists ? "audit log encontrado" : "arquivo ausente"}</small>
    </article>
    <article class="metric-card warn">
      <span>Alertas</span>
      <strong>${Number(levels.WARN || 0).toLocaleString("pt-BR")}</strong>
      <small>linhas WARN</small>
    </article>
    <article class="metric-card err">
      <span>Erros</span>
      <strong>${Number(levels.ERR || 0).toLocaleString("pt-BR")}</strong>
      <small>${data.malformedCount ? `${data.malformedCount} JSON invalido` : "sem JSON invalido"}</small>
    </article>
    <article class="metric-card ok">
      <span>Ultimo evento</span>
      <strong>${formatDateTime(data.lastTs)}</strong>
      <small>primeiro: ${formatDateTime(data.firstTs)}</small>
    </article>
  `;

  const review = data.reviewQueue || {};
  const extracted = data.extractedJsonl || {};
  els.auditArtifacts.innerHTML = `
    <p class="kicker">Artefatos</p>
    <div class="artifact-row">
      <div><strong>${escapeHtml(data.path || "pipeline_audit.jsonl")}</strong><span>JSONL principal</span></div>
      <code>${Number(data.eventCount || 0).toLocaleString("pt-BR")}</code>
    </div>
    <div class="artifact-row">
      <div><strong>${escapeHtml(extracted.path || "relato_estruturado.jsonl")}</strong><span>extracoes LLM</span></div>
      <code>${Number(extracted.count || 0).toLocaleString("pt-BR")}</code>
    </div>
    <div class="artifact-row">
      <div><strong>${escapeHtml(review.path || "review_queue.json")}</strong><span>${escapeHtml(review.status || "sem status")}</span></div>
      <code>${Number(review.pendingCount || 0).toLocaleString("pt-BR")}</code>
    </div>
  `;

  const stepCounts = data.stepCounts || {};
  els.auditSteps.innerHTML = state.steps
    .map((step) => {
      const counts = stepCounts[step.id] || {};
      const latest = data.latestByStep?.[step.id];
      const total = Number(counts.total || 0);
      const err = Number(counts.ERR || 0);
      const warn = Number(counts.WARN || 0);
      const status = err ? "err" : warn ? "warn" : total ? "ok" : "";
      return `
        <div class="audit-step ${status}">
          <div>
            <strong>${step.id}. ${escapeHtml(step.name)}</strong>
            <span>${latest ? escapeHtml(latest.event) : "sem evento"}</span>
          </div>
          <code>${total}</code>
        </div>
      `;
    })
    .join("");

  els.auditRuns.innerHTML = (data.runs || [])
    .map((run) => {
      const levels = run.levels || {};
      const status = run.status === "success" ? "ok" : "warn";
      return `
        <div class="audit-run ${status}">
          <strong>${formatDateTime(run.startedAt)}</strong>
          <span>${escapeHtml((run.steps || []).join(", ") || "sem steps")} · ${formatDuration(run.durationS)}</span>
          <small>${run.events} eventos · ${levels.ERR || 0} err · ${levels.WARN || 0} warn</small>
        </div>
      `;
    })
    .join("") || `<p class="muted">Ainda sem execucoes registradas.</p>`;

  els.auditTopEvents.innerHTML = (data.topEvents || [])
    .map((item) => {
      return `
        <div class="top-event">
          <span title="${escapeHtml(item.event)}">${escapeHtml(item.event)}</span>
          <code>${item.count}</code>
        </div>
      `;
    })
    .join("") || `<p class="muted">Sem eventos para sumarizar.</p>`;

  els.auditEvents.innerHTML = (data.recentEvents || [])
    .map((event) => {
      const payload = event.data && Object.keys(event.data).length ? compactJson(event.data) : "";
      return `
        <article class="audit-event level-${escapeHtml(event.level.toLowerCase())}">
          <div class="audit-event-main">
            <span class="event-level">${escapeHtml(event.level)}</span>
            <div>
              <strong>${escapeHtml(event.event)}</strong>
              <span>${formatDateTime(event.ts)}${event.step ? ` · step ${escapeHtml(event.step)}` : ""} · linha ${event.line}</span>
            </div>
          </div>
          ${payload ? `<pre>${payload}</pre>` : ""}
        </article>
      `;
    })
    .join("") || `<div class="empty-state">Nenhum evento de auditoria encontrado.</div>`;
}

async function loadAudit() {
  const response = await fetch("/api/audit");
  const data = await response.json();
  renderAudit(data);
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

    renderRun(data.run);
    renderAll();
    state.lastRunStatus = nextStatus;

    if (wasActive && !isActive) {
      await loadAudit();
    }
  } catch (error) {
    els.runBadge.className = "run-badge failed";
    els.runBadge.textContent = "offline";
  }
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
els.refreshAuditButton.addEventListener("click", loadAudit);
els.navItems.forEach((item) => {
  item.addEventListener("click", () => showPage(item.dataset.page));
});
window.addEventListener("popstate", () => {
  showPage(pageFromPath(window.location.pathname), { updateHistory: false });
});

showPage(pageFromPath(window.location.pathname), { updateHistory: false });
loadPipeline();
loadAudit();
