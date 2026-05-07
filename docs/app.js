const state = {
  dashboard: null,
  search: "",
  filters: {
    roles: new Set(),
    states: new Set(),
    flags: new Set(),
    subjects: new Set(),
  },
};

const els = {
  updatedAt: document.getElementById("updatedAt"),
  summary: document.getElementById("summary"),
  statusBox: document.getElementById("statusBox"),
  content: document.getElementById("content"),
  searchInput: document.getElementById("searchInput"),
};

const KPI_CONFIG = [
  { key: "total", label: "Всього ВП", type: "all", value: null },
  { key: "debtors", label: "Боржники", type: "role", value: "debtor" },
  { key: "creditors", label: "Стягувачі", type: "role", value: "creditor" },

  { key: "active", label: "Активні", type: "state", value: "active" },
  { key: "completed", label: "Завершені", type: "state", value: "completed" },
  { key: "stopped", label: "Зупинені", type: "state", value: "stopped" },
  { key: "refused", label: "Відмовлено", type: "state", value: "refused" },
  { key: "other", label: "Інші стани", type: "state", value: "other" },

  { key: "new_14d", label: "Нові 14 днів", type: "flag", value: "is_new_14d" },
  { key: "changed_14d", label: "Зміни 14 днів", type: "flag", value: "is_changed_14d" },
];

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

function formatDateOnly(value) {
  if (!value) return "—";

  const text = String(value).trim();

  const match = text.match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  if (match) {
    return `${match[1]}.${match[2]}.${match[3]}`;
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;

  return date.toLocaleDateString("uk-UA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function normalize(value) {
  return String(value ?? "").toLowerCase();
}

function roleLabel(role) {
  if (role === "debtor") return "Боржник";
  if (role === "creditor") return "Стягувач";
  return role || "—";
}

function stateLabel(category) {
  const labels = {
    active: "Активне",
    completed: "Завершене",
    stopped: "Зупинене",
    refused: "Відмовлено",
    other: "Інше",
  };

  return labels[category] || category || "—";
}

function stateClass(category) {
  if (category === "active") return "creditor";
  if (category === "completed") return "partial";
  if (category === "stopped") return "state";
  if (category === "refused") return "debtor";
  return "partial";
}

function recordSearchText(record) {
  return normalize([
    record.vp_ordernum,
    record.subject?.name,
    record.subject?.code,
    record.subject?.role,
    record.state?.current,
    record.state?.category,
    record.parties?.debtor_name,
    record.parties?.debtor_code,
    record.parties?.creditor_name,
    record.parties?.creditor_code,
    record.dvs?.org_name,
    record.dvs?.dvs_code,
  ].join(" "));
}

function getSubjectsMap() {
  const subjects = new Map();

  for (const record of state.dashboard?.records || []) {
    const id = record.subject?.id;
    const name = record.subject?.name;

    if (id && name) {
      subjects.set(id, name);
    }
  }

  return subjects;
}

function toggleFilter(type, value) {
  if (type === "all") {
    state.filters.roles.clear();
    state.filters.states.clear();
    state.filters.flags.clear();
    state.filters.subjects.clear();
    render();
    return;
  }

  const target =
    type === "role"
      ? state.filters.roles
      : type === "state"
        ? state.filters.states
        : type === "subject"
          ? state.filters.subjects
          : state.filters.flags;

  if (target.has(value)) {
    target.delete(value);
  } else {
    target.add(value);
  }

  render();
}

function isKpiActive(item) {
  if (item.type === "all") {
    return (
      state.filters.roles.size === 0 &&
      state.filters.states.size === 0 &&
      state.filters.flags.size === 0 &&
      state.filters.subjects.size === 0
    );
  }

  if (item.type === "role") return state.filters.roles.has(item.value);
  if (item.type === "state") return state.filters.states.has(item.value);
  if (item.type === "flag") return state.filters.flags.has(item.value);

  return false;
}

function renderSummary() {
  const kpi = state.dashboard?.kpi || {};

  els.summary.innerHTML = KPI_CONFIG.map((item) => {
    const active = isKpiActive(item) ? " is-active" : "";

    return `
      <button
        class="summary-card${active}"
        data-filter-type="${escapeHtml(item.type)}"
        data-filter-value="${escapeHtml(item.value || "")}"
      >
        <div class="summary-value">${kpi[item.key] ?? 0}</div>
        <div class="summary-label">${escapeHtml(item.label)}</div>
      </button>
    `;
  }).join("");

  els.summary.querySelectorAll(".summary-card").forEach((button) => {
    button.addEventListener("click", () => {
      toggleFilter(button.dataset.filterType, button.dataset.filterValue || null);
    });
  });
}

function recordMatchesFilters(record) {
  if (
    state.filters.roles.size > 0 &&
    !state.filters.roles.has(record.subject?.role)
  ) {
    return false;
  }

  if (
    state.filters.states.size > 0 &&
    !state.filters.states.has(record.state?.category)
  ) {
    return false;
  }

  if (
    state.filters.subjects.size > 0 &&
    !state.filters.subjects.has(record.subject?.id)
  ) {
    return false;
  }

  if (state.filters.flags.size > 0) {
    for (const flag of state.filters.flags) {
      if (!record.flags?.[flag]) return false;
    }
  }

  const q = normalize(state.search).trim();
  if (q && !recordSearchText(record).includes(q)) {
    return false;
  }

  return true;
}

function filteredRecords() {
  return (state.dashboard?.records || []).filter(recordMatchesFilters);
}

function renderSubjectFilters() {
  const subjects = getSubjectsMap();

  if (!subjects.size) return "";

  return `
    <div class="subject-filters">
      ${Array.from(subjects.entries()).map(([id, name]) => {
        const active = state.filters.subjects.has(id) ? " is-active" : "";

        return `
          <button
            class="subject-filter${active}"
            data-subject-id="${escapeHtml(id)}"
          >
            ${escapeHtml(name)}
          </button>
        `;
      }).join("")}
    </div>
  `;
}

function renderActiveFilters() {
  const chips = [];
  const subjects = getSubjectsMap();

  for (const subjectId of state.filters.subjects) {
    chips.push({
      type: "subject",
      value: subjectId,
      label: subjects.get(subjectId) || subjectId,
    });
  }

  for (const role of state.filters.roles) {
    chips.push({ type: "role", value: role, label: roleLabel(role) });
  }

  for (const category of state.filters.states) {
    chips.push({ type: "state", value: category, label: stateLabel(category) });
  }

  for (const flag of state.filters.flags) {
    chips.push({
      type: "flag",
      value: flag,
      label: flag === "is_new_14d" ? "Нові 14 днів" : "Зміни 14 днів",
    });
  }

  if (!chips.length) return "";

  return `
    <div class="filter-chips">
      ${chips.map((chip) => `
        <button
          class="filter-chip"
          data-type="${escapeHtml(chip.type)}"
          data-value="${escapeHtml(chip.value)}"
        >
          ${escapeHtml(chip.label)} ×
        </button>
      `).join("")}
    </div>
  `;
}

function bindSubjectFilters() {
  document.querySelectorAll(".subject-filter").forEach((button) => {
    button.addEventListener("click", () => {
      toggleFilter("subject", button.dataset.subjectId);
    });
  });
}

function bindFilterChips() {
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      toggleFilter(chip.dataset.type, chip.dataset.value);
    });
  });
}

function eventLabel(event) {
  if (event.event_type === "new_case") return "Нове ВП";

  if (event.event_type === "state_changed") {
    return `Стан: ${event.old_state || "—"} → ${event.new_state || "—"}`;
  }

  if (event.event_type === "details_changed") return "Зміна реквізитів";

  return event.event_type || "Подія";
}

function renderTimeline(record) {
  const events = record.recent_events || record.events || [];

  if (!events.length) return "";

  return `
    <section class="change-box">
      <strong>Події</strong>
      ${events.slice().reverse().map((event) => `
        <div class="change-row">
          <div class="label">${escapeHtml(formatDateTime(event.detected_at))}</div>
          <div>${escapeHtml(eventLabel(event))}</div>
        </div>
      `).join("")}
    </section>
  `;
}

function renderRecord(record) {
  return `
    <article class="case-card">
      <div class="case-head">
        <div>
          <h2 class="case-title">ВП № ${escapeHtml(record.vp_ordernum || "—")}</h2>
          <div class="meta">
            ${escapeHtml(record.subject?.name || "—")} · код ${escapeHtml(record.subject?.code || "—")}
            <br />
            Дата відкриття: ${escapeHtml(formatDateOnly(record.dates?.vp_begin))}
          </div>
        </div>

        <div class="badges">
          <span class="badge ${record.subject?.role === "debtor" ? "debtor" : "creditor"}">
            ${escapeHtml(roleLabel(record.subject?.role))}
          </span>
          <span class="badge ${stateClass(record.state?.category)}">
            ${escapeHtml(record.state?.current || "—")}
          </span>
          ${record.flags?.is_new_14d ? `<span class="badge creditor">Нове 14д</span>` : ""}
          ${record.flags?.is_changed_14d ? `<span class="badge state">Зміни 14д</span>` : ""}
        </div>
      </div>

      <section class="details">
        <div class="details-grid">
          <div class="label">Боржник</div>
          <div>${escapeHtml(record.parties?.debtor_name || "—")} ${record.parties?.debtor_code ? `· ${escapeHtml(record.parties.debtor_code)}` : ""}</div>

          <div class="label">Дата народження боржника</div>
          <div>${escapeHtml(formatDateOnly(record.parties?.debtor_birthdate))}</div>

          <div class="label">Стягувач</div>
          <div>${escapeHtml(record.parties?.creditor_name || "—")} ${record.parties?.creditor_code ? `· ${escapeHtml(record.parties.creditor_code)}` : ""}</div>

          <div class="label">Орган / виконавець</div>
          <div>${escapeHtml(record.dvs?.org_name || "—")}</div>

          <div class="label">Код ДВС</div>
          <div>${escapeHtml(record.dvs?.dvs_code || "—")}</div>

          <div class="label">Перше виявлення</div>
          <div>${escapeHtml(formatDateTime(record.dates?.first_seen))}</div>

          <div class="label">Остання зміна</div>
          <div>${escapeHtml(formatDateTime(record.dates?.last_changed))}</div>
        </div>
      </section>

      ${renderTimeline(record)}
    </article>
  `;
}

function renderRecords() {
  const records = filteredRecords();

  if (!records.length) {
    els.content.innerHTML = `
      ${renderSubjectFilters()}
      ${renderActiveFilters()}
      <div class="empty">Нічого не знайдено.</div>
    `;

    bindSubjectFilters();
    bindFilterChips();
    return;
  }

  els.content.innerHTML = `
    ${renderSubjectFilters()}
    ${renderActiveFilters()}
    ${records.map(renderRecord).join("")}
  `;

  bindSubjectFilters();
  bindFilterChips();
}

function render() {
  renderSummary();

  const generatedAt = state.dashboard?.generated_at;

  els.updatedAt.textContent = generatedAt
    ? `Оновлення: ${formatDateTime(generatedAt)}`
    : "Оновлення: —";

  els.statusBox.classList.add("hidden");
  els.statusBox.textContent = "";

  renderRecords();
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
    state.dashboard = await loadJson("./data/dashboard.json");
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

init();
