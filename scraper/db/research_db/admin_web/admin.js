const state = {
  q: "",
  visibility: "all",
  provider: "",
  source: "",
  page: 1,
  pageSize: 30,
  total: 0,
  items: [],
  selectedId: null,
  summary: null,
  loading: false,
};

const $ = (selector) => document.querySelector(selector);

const els = {
  q: $("#q"),
  visibility: $("#visibility"),
  provider: $("#provider"),
  source: $("#source"),
  refresh: $("#refresh"),
  list: $("#project-list"),
  detail: $("#project-detail"),
  pageMeta: $("#page-meta"),
  prev: $("#prev-page"),
  next: $("#next-page"),
  total: $("#summary-total"),
  visible: $("#summary-visible"),
  hidden: $("#summary-hidden"),
  providers: $("#summary-providers"),
};

const esc = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const text = (value, fallback = "-") => {
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.length ? value.join("、") : fallback;
  return String(value);
};

const money = (value) => {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (Number.isFinite(n)) return `¥${n.toLocaleString("zh-CN")}`;
  return String(value);
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json();
}

function params() {
  const search = new URLSearchParams();
  search.set("page", state.page);
  search.set("page_size", state.pageSize);
  if (state.q.trim()) search.set("q", state.q.trim());
  if (state.visibility !== "all") search.set("visibility", state.visibility);
  if (state.provider) search.set("provider", state.provider);
  if (state.source) search.set("source", state.source);
  return search.toString();
}

function renderSummary() {
  const summary = state.summary || {};
  els.total.textContent = Number(summary.total_projects || 0).toLocaleString("zh-CN");
  els.visible.textContent = Number(summary.visible_projects || 0).toLocaleString("zh-CN");
  els.hidden.textContent = Number(summary.hidden_projects || 0).toLocaleString("zh-CN");
  els.providers.textContent = Number(summary.provider_count || 0).toLocaleString("zh-CN");

  const providers = summary.providers || [];
  const sources = summary.sources || [];

  const currentProvider = state.provider;
  els.provider.innerHTML = `<option value="">全部项目方</option>${providers
    .map((item) => `<option value="${esc(item.provider)}">${esc(item.provider)} (${item.count})</option>`)
    .join("")}`;
  els.provider.value = currentProvider;

  const currentSource = state.source;
  els.source.innerHTML = `<option value="">全部来源</option>${sources
    .map((item) => `<option value="${esc(item.source_system)}">${esc(item.source_system)} (${item.count})</option>`)
    .join("")}`;
  els.source.value = currentSource;
}

function renderList() {
  const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
  els.pageMeta.textContent = `第 ${state.page} / ${totalPages} 页，共 ${state.total.toLocaleString("zh-CN")} 个项目`;
  els.prev.disabled = state.page <= 1 || state.loading;
  els.next.disabled = state.page >= totalPages || state.loading;

  if (state.loading) {
    els.list.innerHTML = `<div class="empty">正在加载项目...</div>`;
    return;
  }

  if (!state.items.length) {
    els.list.innerHTML = `<div class="empty">没有匹配的项目</div>`;
    renderDetail(null);
    return;
  }

  if (!state.selectedId || !state.items.some((item) => item.id === state.selectedId)) {
    state.selectedId = state.items[0].id;
  }

  els.list.innerHTML = state.items
    .map((item) => {
      const active = item.id === state.selectedId ? " is-active" : "";
      const visible = item.is_visible;
      return `
        <button class="project-item${active}" data-id="${esc(item.id)}">
          <span class="project-item__main">
            <span class="project-item__title">${esc(item.title)}</span>
            <span class="project-item__meta">${esc(text(item.provider))} / ${esc(text(item.school_name))} / ${esc(text(item.country))}</span>
            <span class="project-item__tags">
              <span>${esc(text(item.project_type))}</span>
              <span>${esc(text(item.primary_subject))}</span>
              <span>${esc(text(item.difficulty))}</span>
            </span>
          </span>
          <span class="status ${visible ? "status--visible" : "status--hidden"}">${visible ? "前端显示" : "未显示"}</span>
        </button>
      `;
    })
    .join("");

  renderDetail(state.items.find((item) => item.id === state.selectedId));
}

function section(title, content) {
  return `
    <section class="detail-section">
      <h3>${esc(title)}</h3>
      ${content}
    </section>
  `;
}

function field(label, value) {
  return `
    <div class="field">
      <span class="field__label">${esc(label)}</span>
      <span class="field__value">${esc(text(value))}</span>
    </div>
  `;
}

function renderDetail(project) {
  if (!project) {
    els.detail.innerHTML = `<div class="empty">从左侧选择一个项目</div>`;
    return;
  }

  const visible = project.is_visible;
  const action = visible ? "隐藏，不在前端展示" : "设为前端显示";
  const sourceLinks = (project.source_urls || [])
    .filter(Boolean)
    .slice(0, 4)
    .map((url) => `<a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url)}</a>`)
    .join("");

  els.detail.innerHTML = `
    <div class="detail-head">
      <div>
        <div class="detail-kicker">${esc(text(project.provider))}</div>
        <h2>${esc(project.title)}</h2>
      </div>
      <button class="primary-action ${visible ? "danger" : ""}" id="toggle-visible">${esc(action)}</button>
    </div>
    <div class="detail-status">
      <span class="status ${visible ? "status--visible" : "status--hidden"}">${visible ? "前端显示" : "未显示"}</span>
      <span>${esc(text(project.status))}</span>
      <span>${esc(text(project.readiness_status))}</span>
    </div>
    ${section(
      "项目字段",
      `<div class="field-grid">
        ${field("网页链接", project.web_url)}
        ${field("优先级", project.priority)}
        ${field("周期", project.duration)}
        ${field("适合学生方向", project.suitable_student_direction)}
        ${field("二级学科", project.secondary_subject)}
        ${field("难度", project.difficulty)}
        ${field("专业方向", project.major_direction)}
        ${field("适合专业", project.suitable_majors)}
        ${field("建议先修课程", project.prerequisites)}
        ${field("教授所在学校", project.school_name)}
        ${field("教授级别", project.professor_level)}
        ${field("国家", project.country)}
        ${field("售价", money(project.price_amount))}
        ${field("适合年级", project.suitable_grades)}
        ${field("教授姓名", project.professor_name)}
        ${field("开课日期", project.start_date)}
        ${field("招生状态", project.enrollment_status)}
        ${field("项目类型", project.project_type)}
        ${field("一级学科", project.primary_subject)}
      </div>`
    )}
    ${section("课题简介", `<p>${esc(text(project.project_intro))}</p>`)}
    ${section("课题信息", `<p>${esc(text(project.topic_info))}</p>`)}
    ${section("教授简介", `<p>${esc(text(project.professor_bio_edited || project.professor_bio))}</p>`)}
    ${section("教授论文指导范围", `<p>${esc(text(project.thesis_supervision_scope))}</p>`)}
    ${section("来源版本", `<div class="link-list">${sourceLinks || "暂无链接"}</div>`)}
  `;

  $("#toggle-visible").addEventListener("click", () => setVisibility(project, !visible));
}

async function loadSummary() {
  state.summary = await api("/api/admin/summary");
  renderSummary();
}

async function loadProjects() {
  state.loading = true;
  renderList();
  try {
    const data = await api(`/api/admin/projects?${params()}`);
    state.items = data.items || [];
    state.total = data.total || 0;
  } finally {
    state.loading = false;
  }
  renderList();
}

async function refreshAll() {
  await loadSummary();
  await loadProjects();
}

async function setVisibility(project, visible) {
  const button = $("#toggle-visible");
  if (button) {
    button.disabled = true;
    button.textContent = visible ? "正在设置显示..." : "正在隐藏...";
  }
  await api(`/api/admin/projects/${project.id}/visibility`, {
    method: "POST",
    body: JSON.stringify({ visible }),
  });
  state.selectedId = project.id;
  await refreshAll();
}

let searchTimer = null;
function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.q = els.q.value;
    state.page = 1;
    loadProjects().catch(showError);
  }, 180);
}

function showError(error) {
  console.error(error);
  els.detail.innerHTML = `<div class="empty error">操作失败：${esc(error.message)}</div>`;
}

els.q.addEventListener("input", scheduleSearch);
els.visibility.addEventListener("change", () => {
  state.visibility = els.visibility.value;
  state.page = 1;
  loadProjects().catch(showError);
});
els.provider.addEventListener("change", () => {
  state.provider = els.provider.value;
  state.page = 1;
  loadProjects().catch(showError);
});
els.source.addEventListener("change", () => {
  state.source = els.source.value;
  state.page = 1;
  loadProjects().catch(showError);
});
els.refresh.addEventListener("click", () => refreshAll().catch(showError));
els.prev.addEventListener("click", () => {
  state.page = Math.max(1, state.page - 1);
  loadProjects().catch(showError);
});
els.next.addEventListener("click", () => {
  state.page += 1;
  loadProjects().catch(showError);
});
els.list.addEventListener("click", (event) => {
  const item = event.target.closest(".project-item");
  if (!item) return;
  state.selectedId = item.dataset.id;
  renderList();
});

refreshAll().catch(showError);
