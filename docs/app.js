const state = {
  current: null,
  changes: null,
  tab: "current",
  search: "",
};

const els = {
  updatedAt: document.getElementById("updatedAt"),
  summary: document.getElementById("summary"),
  statusBox: document.getElementById("statusBox"),
  content: document.getElementById("content"),
  searchInput: document.getElementById("searchInput"),
  tabs: document.querySelectorAll(".tab"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDateTime(value) {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString("uk-UA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalize(value) {
  return String(value ?? "").toLowerCase();
}

function recordSearchText(record) {
  return normalize([
    record.subject_name,
    record.subject_code,
    record.role,
    record.vp_ordernum,
    record.vp_state,
    record.debtor_name,
    record.debtor_code,
    record.creditor_name,
    record.creditor_code,
    record.org_name,
    record.dvs_code,
  ].join(" "));
}

function filterRecords(records) {
  const q = normalize(state.search).trim();
  if (!q) return records;

  return records.filter((record) => recordSearchText(record).includes(q));
}

function roleLabel(role) {
  if (role === "debtor") return "Боржник";
  if (role === "creditor") return "Стягувач";
  return role || "—";
}

function roleClass(role) {
  if (role === "debtor") return "debtor";
  if (role === "creditor") return "creditor";
  return "partial";
}

function renderSummary() {
  const records = state.current?.records || [];
  const changes = state.changes || {};

  const debtorTotal = records.filter((r) => r.role === "debtor").length;
  const creditorTotal = records.filter((r) => r.role === "creditor").length;

  els.summary.innerHTML = `
    <div class="summary-card">
      <div class="summary-value">${records.length}</div>
      <div class="summary-label">Поточних збігів</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${debtorTotal}</div>
      <div class="summary-label">Як боржник</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${creditorTotal}</div>
      <div class="summary-label">Як стягувач</div>
    </div>
    <div class="summary-card">
      <div class="summary-value">${changes.added_total ?? 0}</div>
      <div class="summary-label">Нових з останнього run</div>
    </div>
  `;
}

function renderRecord(record, extraHtml = "") {
  const role = record.role;

  return `
    <article class="case-card">
      <div class="case-head">
        <div>
          <h2 class="case-title">${escapeHtml(record.subject_name || "—")}</h2>
          <div class="meta">
            ID: ${escapeHtml(record.subject_id)} · Код: ${escapeHtml(record.subject_code || "—")}
            <br />
            ВП № ${escapeHtml(record.vp_ordernum || "—")} · Дата відкриття: ${escapeHtml(record.vp_begindate || "—")}
          </div>
        </div>

        <div class="badges">
          <span class="badge ${roleClass(role)}">${escapeHtml(roleLabel(role))}</span>
          <span class="badge state">${escapeHtml(record.vp_state || "—")}</span>
        </div>
      </div>

      <section class="details">
        <div class="details-grid">
          <div class="label">Боржник</div>
          <div>${escapeHtml(record.debtor_name || "—")} ${record.debtor_code ? `· ${escapeHtml(record.debtor_code)}` : ""}</div>

          <div class="label">Дата народження боржника</div>
          <div>${escapeHtml(record.debtor_birthdate || "—")}</div>

          <div class="label">Стягувач</div>
          <div>${escapeHtml(record.creditor_name || "—")} ${record.creditor_code ? `· ${escapeHtml(record.creditor_code)}` : ""}</div>

          <div class="label">Орган ДВС</div>
          <div>${escapeHtml(record.org_name || "—")}</div>

          <div class="label">Код ДВС</div>
          <div>${escapeHtml(record.dvs_code || "—")}</div>
        </div>
      </section>

      ${extraHtml}
    </article>
  `;
}

function renderCurrent() {
  const records = filterRecords(state.current?.records || []);

  if (!records.length) {
    els.content.innerHTML = `<div class="empty">Нічого не знайдено.</div>`;
    return;
  }

  els.content.innerHTML = records.map((record) => renderRecord(record)).join("");
}

function renderAdded() {
  const records = filterRecords(state.changes?.added || []);

  if (!records.length) {
    els.content.innerHTML = `<div class="empty">Нових записів немає.</div>`;
    return;
  }

  els.content.innerHTML = records.map((record) => renderRecord(record)).join("");
}

function renderChanged() {
  const stateChanged = state.changes?.state_changed || [];
  const detailsChanged = state.changes?.details_changed || [];

  const items = [
    ...stateChanged.map((item) => ({ type: "state", ...item })),
    ...detailsChanged.map((item) => ({ type: "details", ...item })),
  ];

  const q = normalize(state.search).trim();

  const filtered = !q
    ? items
    : items.filter((item) => {
        const record = item.current || {};
        return recordSearchText(record).includes(q);
      });

  if (!filtered.length) {
    els.content.innerHTML = `<div class="empty">Змін немає.</div>`;
    return;
  }

  els.content.innerHTML = filtered.map((item) => {
    if (item.type === "state") {
      const extra = `
        <section class="change-box">
          <strong>Зміна статусу ВП</strong>
          <div class="change-row">
            <div class="label">Було</div>
            <div>${escapeHtml(item.previous?.vp_state || "—")}</div>
          </div>
          <div class="change-row">
            <div class="label">Стало</div>
            <div>${escapeHtml(item.current?.vp_state || "—")}</div>
          </div>
        </section>
      `;

      return renderRecord(item.current, extra);
    }

    const changes = item.changes || {};
    const rows = Object.entries(changes).map(([field, value]) => `
      <div class="change-row">
        <div class="label">${escapeHtml(field)}</div>
        <div>
          <span>${escapeHtml(value.old || "—")}</span>
          →
          <strong>${escapeHtml(value.new || "—")}</strong>
        </div>
      </div>
    `).join("");

    const extra = `
      <section class="change-box">
        <strong>Зміна деталей</strong>
        ${rows}
      </section>
    `;

    return renderRecord(item.current, extra);
  }).join("");
}

function render() {
  renderSummary();

  if (state.current?.generated_at) {
    const partial = state.current?.is_partial ? " · partial snapshot" : "";
    els.updatedAt.textContent = `Оновлення: ${formatDateTime(state.current.generated_at)}${partial}`;
  }

  if (state.current?.is_partial) {
    els.statusBox.classList.remove("hidden");
    els.statusBox.textContent =
      "Увага: джерельний ZIP має CRC-помилку, тому snapshot позначено як partial. REMOVED-зміни тимчасово не враховуються.";
  } else {
    els.statusBox.classList.add("hidden");
  }

  if (state.tab === "current") renderCurrent();
  if (state.tab === "added") renderAdded();
  if (state.tab === "changed") renderChanged();
}

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Не вдалося завантажити ${path}: ${response.status}`);
  }
  return response.json();
}

async function init() {
  try {
    const [current, changes] = await Promise.all([
      loadJson("./data/current.json"),
      loadJson("./data/changes.json"),
    ]);

    state.current = current;
    state.changes = changes;

    render();
  } catch (error) {
    els.statusBox.classList.remove("hidden");
    els.statusBox.textContent = String(error.message || error);
  }
}

els.searchInput.addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});

els.tabs.forEach((button) => {
  button.addEventListener("click", () => {
    els.tabs.forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");
    state.tab = button.dataset.tab;
    render();
  });
});

init();
