const state = {
  q: "",
  page: 1,
  pageSize: 24,
  total: 0,
  items: [],
  loading: false,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  q: $("#public-q"),
  list: $("#public-list"),
  meta: $("#public-meta"),
  prev: $("#public-prev"),
  next: $("#public-next"),
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

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function params() {
  const search = new URLSearchParams();
  search.set("page", state.page);
  search.set("page_size", state.pageSize);
  if (state.q.trim()) search.set("q", state.q.trim());
  return search.toString();
}

function render() {
  const totalPages = Math.max(1, Math.ceil(state.total / state.pageSize));
  els.meta.textContent = `已上架 ${state.total.toLocaleString("zh-CN")} 个项目，第 ${state.page} / ${totalPages} 页`;
  els.prev.disabled = state.page <= 1 || state.loading;
  els.next.disabled = state.page >= totalPages || state.loading;

  if (state.loading) {
    els.list.innerHTML = `<div class="empty">正在加载已上架项目...</div>`;
    return;
  }

  if (!state.items.length) {
    els.list.innerHTML = `<div class="empty">当前没有前端可见项目。请在后台把项目设为“前端显示”。</div>`;
    return;
  }

  els.list.innerHTML = state.items
    .map(
      (item) => `
        <article class="public-card">
          <div class="public-card__top">
            <span>${esc(text(item.provider))}</span>
            <span>${esc(text(item.project_type))}</span>
          </div>
          <h2>${esc(item.title)}</h2>
          <p>${esc(text(item.project_intro || item.topic_info))}</p>
          <div class="public-card__grid">
            <span>学校：${esc(text(item.school_name))}</span>
            <span>国家：${esc(text(item.country))}</span>
            <span>方向：${esc(text(item.primary_subject))} / ${esc(text(item.secondary_subject))}</span>
            <span>难度：${esc(text(item.difficulty))}</span>
            <span>适合专业：${esc(text(item.suitable_majors))}</span>
            <span>招生状态：${esc(text(item.enrollment_status))}</span>
          </div>
        </article>
      `
    )
    .join("");
}

async function load() {
  state.loading = true;
  render();
  try {
    const data = await api(`/api/public/projects?${params()}`);
    state.items = data.items || [];
    state.total = data.total || 0;
  } finally {
    state.loading = false;
  }
  render();
}

let searchTimer = null;
els.q.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    state.q = els.q.value;
    state.page = 1;
    load().catch(showError);
  }, 180);
});
els.prev.addEventListener("click", () => {
  state.page = Math.max(1, state.page - 1);
  load().catch(showError);
});
els.next.addEventListener("click", () => {
  state.page += 1;
  load().catch(showError);
});

function showError(error) {
  console.error(error);
  els.list.innerHTML = `<div class="empty error">加载失败：${esc(error.message)}</div>`;
}

load().catch(showError);
