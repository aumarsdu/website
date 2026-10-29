const state = {
  projects: [],
  filtered: [],
  selectedId: null,
  visibleCount: 120,
};

const els = {
  summaryText: document.getElementById("summaryText"),
  searchInput: document.getElementById("searchInput"),
  providerFilter: document.getElementById("providerFilter"),
  sourceFilter: document.getElementById("sourceFilter"),
  taxonomyFilter: document.getElementById("taxonomyFilter"),
  issueFilter: document.getElementById("issueFilter"),
  resetButton: document.getElementById("resetButton"),
  resultCount: document.getElementById("resultCount"),
  visibleRange: document.getElementById("visibleRange"),
  projectList: document.getElementById("projectList"),
  detailEmpty: document.getElementById("detailEmpty"),
  detailContent: document.getElementById("detailContent"),
};

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function asArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : [];
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "zh-CN"));
}

function textOfProject(project) {
  const taxonomy = asArray(project.taxonomy).map((item) => `${item.type || ""} ${item.name || ""}`).join(" ");
  return normalizeText([
    project.title,
    project.provider,
    project.source,
    project.project_type,
    project.summary,
    project.topic_info,
    asArray(project.instructors).join(" "),
    asArray(project.institutions).join(" "),
    taxonomy,
    asArray(project.suitable_grades).join(" "),
    asArray(project.prerequisite_courses).join(" "),
  ].join(" "));
}

async function loadData() {
  const [summaryResponse, projectsResponse] = await Promise.all([
    fetch("./data/summary.json"),
    fetch("./data/projects.jsonl"),
  ]);
  const summary = await summaryResponse.json();
  const projectText = await projectsResponse.text();
  state.projects = projectText
    .split(/\n+/)
    .filter(Boolean)
    .map((line) => {
      const project = JSON.parse(line);
      project.searchText = textOfProject(project);
      return project;
    });
  state.filtered = state.projects;
  els.summaryText.textContent = `已加载 ${summary.project_count.toLocaleString("zh-CN")} 个项目，${summary.asset_count.toLocaleString("zh-CN")} 个资产，${summary.quality_issue_count.toLocaleString("zh-CN")} 个待补全项`;
  hydrateFilters();
  applyFilters();
}

function option(value, label) {
  const opt = document.createElement("option");
  opt.value = value;
  opt.textContent = label;
  return opt;
}

function hydrateSelect(select, values, allLabel) {
  select.innerHTML = "";
  select.appendChild(option("", allLabel));
  values.forEach((value) => select.appendChild(option(value, value)));
}

function hydrateFilters() {
  hydrateSelect(els.providerFilter, uniq(state.projects.map((project) => project.provider)), "全部项目方");
  hydrateSelect(els.sourceFilter, uniq(state.projects.map((project) => project.source)), "全部来源");
  hydrateSelect(
    els.taxonomyFilter,
    uniq(state.projects.flatMap((project) => asArray(project.taxonomy).map((item) => item.name))),
    "全部学科"
  );
}

function applyFilters() {
  const query = normalizeText(els.searchInput.value);
  const provider = els.providerFilter.value;
  const source = els.sourceFilter.value;
  const taxonomy = els.taxonomyFilter.value;
  const issue = els.issueFilter.value;

  state.filtered = state.projects.filter((project) => {
    if (query && !project.searchText.includes(query)) return false;
    if (provider && project.provider !== provider) return false;
    if (source && project.source !== source) return false;
    if (taxonomy && !asArray(project.taxonomy).some((item) => item.name === taxonomy)) return false;
    if (issue === "has" && Number(project.quality_issue_count || 0) === 0) return false;
    if (issue === "none" && Number(project.quality_issue_count || 0) > 0) return false;
    return true;
  });

  if (!state.filtered.some((project) => project.id === state.selectedId)) {
    state.selectedId = state.filtered[0]?.id || null;
  }

  renderList();
  renderDetail();
}

function renderList() {
  els.resultCount.textContent = `${state.filtered.length.toLocaleString("zh-CN")} 个项目`;
  const visible = state.filtered.slice(0, state.visibleCount);
  els.visibleRange.textContent = state.filtered.length > visible.length ? `显示前 ${visible.length.toLocaleString("zh-CN")} 个` : "已显示全部";
  els.projectList.innerHTML = "";

  if (!visible.length) {
    const empty = document.createElement("div");
    empty.className = "detail-empty";
    empty.textContent = "没有匹配的项目";
    els.projectList.appendChild(empty);
    return;
  }

  visible.forEach((project) => {
    const item = document.createElement("button");
    item.className = `project-item${project.id === state.selectedId ? " active" : ""}`;
    item.type = "button";
    item.addEventListener("click", () => {
      state.selectedId = project.id;
      renderList();
      renderDetail();
    });

    const title = document.createElement("h3");
    title.className = "project-title";
    title.textContent = project.title || "未命名项目";

    const meta = document.createElement("div");
    meta.className = "project-meta";
    [project.provider, project.source, project.duration, project.start_date_text].filter(Boolean).forEach((value) => {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = value;
      meta.appendChild(pill);
    });
    if (Number(project.quality_issue_count || 0) > 0) {
      const warn = document.createElement("span");
      warn.className = "pill warn";
      warn.textContent = `${project.quality_issue_count} 项待补全`;
      meta.appendChild(warn);
    }

    const submeta = document.createElement("div");
    submeta.className = "project-submeta";
    const instructor = asArray(project.instructors)[0];
    const institution = asArray(project.institutions)[0];
    submeta.textContent = [instructor, institution].filter(Boolean).join(" · ") || "暂无教授/学校信息";

    item.append(title, meta, submeta);
    els.projectList.appendChild(item);
  });
}

function field(label, value) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  const labelEl = document.createElement("p");
  labelEl.className = "field-label";
  labelEl.textContent = label;
  const valueEl = document.createElement("p");
  valueEl.className = "field-value";
  valueEl.textContent = value || "暂无";
  wrap.append(labelEl, valueEl);
  return wrap;
}

function renderTags(values, className = "pill") {
  const wrap = document.createElement("div");
  wrap.className = "tag-list";
  values.filter(Boolean).forEach((value) => {
    const tag = document.createElement("span");
    tag.className = className;
    tag.textContent = value;
    wrap.appendChild(tag);
  });
  if (!wrap.children.length) {
    const muted = document.createElement("span");
    muted.className = "field-value";
    muted.textContent = "暂无";
    wrap.appendChild(muted);
  }
  return wrap;
}

function section(title, content) {
  const fragment = document.createDocumentFragment();
  const heading = document.createElement("h3");
  heading.className = "section-title";
  heading.textContent = title;
  fragment.appendChild(heading);
  fragment.appendChild(content);
  return fragment;
}

function renderDetail() {
  const project = state.projects.find((item) => item.id === state.selectedId);
  if (!project) {
    els.detailEmpty.classList.remove("hidden");
    els.detailContent.classList.add("hidden");
    els.detailContent.innerHTML = "";
    return;
  }

  els.detailEmpty.classList.add("hidden");
  els.detailContent.classList.remove("hidden");
  els.detailContent.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = project.title || "未命名项目";
  els.detailContent.appendChild(title);

  const meta = document.createElement("div");
  meta.className = "project-meta";
  [project.provider, project.source, project.status, project.readiness].filter(Boolean).forEach((value) => {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = value;
    meta.appendChild(pill);
  });
  if (Number(project.quality_issue_count || 0) > 0) {
    const warn = document.createElement("span");
    warn.className = "pill warn";
    warn.textContent = `${project.quality_issue_count} 项待补全`;
    meta.appendChild(warn);
  }
  els.detailContent.appendChild(meta);

  const grid = document.createElement("div");
  grid.className = "detail-grid";
  grid.append(
    field("教授", asArray(project.instructors).join("、")),
    field("学校", asArray(project.institutions).join("、")),
    field("周期", project.duration),
    field("开课日期", project.start_date_text),
    field("招生状态", project.enrollment_status),
    field("资产数量", String(project.asset_count || 0))
  );
  els.detailContent.appendChild(grid);

  const summary = document.createElement("div");
  summary.className = "summary-block";
  summary.textContent = project.summary || project.topic_info || "暂无课题简介";
  els.detailContent.appendChild(section("课题简介", summary));

  const taxonomy = asArray(project.taxonomy).map((item) => item.name);
  els.detailContent.appendChild(section("学科与方向", renderTags(uniq(taxonomy))));
  els.detailContent.appendChild(section("适合年级", renderTags(asArray(project.suitable_grades))));
  els.detailContent.appendChild(section("建议先修课程", renderTags(asArray(project.prerequisite_courses))));

  if (project.source_url) {
    const link = document.createElement("a");
    link.className = "source-link";
    link.href = project.source_url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = project.source_url;
    els.detailContent.appendChild(section("网页链接", link));
  }
}

function resetFilters() {
  els.searchInput.value = "";
  els.providerFilter.value = "";
  els.sourceFilter.value = "";
  els.taxonomyFilter.value = "";
  els.issueFilter.value = "";
  state.visibleCount = 120;
  applyFilters();
}

["input", "change"].forEach((eventName) => {
  els.searchInput.addEventListener(eventName, applyFilters);
});
[els.providerFilter, els.sourceFilter, els.taxonomyFilter, els.issueFilter].forEach((select) => {
  select.addEventListener("change", applyFilters);
});
els.resetButton.addEventListener("click", resetFilters);

els.projectList.addEventListener("scroll", () => {
  const remaining = els.projectList.scrollHeight - els.projectList.scrollTop - els.projectList.clientHeight;
  if (remaining < 240 && state.visibleCount < state.filtered.length) {
    state.visibleCount += 120;
    renderList();
  }
});

loadData().catch((error) => {
  els.summaryText.textContent = "项目数据读取失败";
  const empty = document.createElement("div");
  empty.className = "detail-empty";
  empty.textContent = error.message;
  els.projectList.appendChild(empty);
});
