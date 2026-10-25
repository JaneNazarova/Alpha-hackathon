const state = {
  companies: [],
  companyId: "",
  role: "ceo",
  feed: [],
  activeArticle: null,
  activeInsightId: null,
};

const elements = {
  main: document.querySelector(".main-content"),
  companySelect: document.querySelector("#company-select"),
  connection: document.querySelector("#connection-label"),
  connectionStatus: document.querySelector(".system-status"),
  feed: document.querySelector("#feed-list"),
  feedCount: document.querySelector("#feed-count"),
  search: document.querySelector("#search-input"),
  dialog: document.querySelector("#article-dialog"),
  dialogContent: document.querySelector("#dialog-content"),
  toastRegion: document.querySelector("#toast-region"),
};

const formatDate = (value) => {
  if (!value) return "Дата не указана";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Дата не указана";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" }).format(date);
};

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined && text !== null) element.textContent = text;
  return element;
}

function showToast(message, isError = false) {
  const toast = makeElement("div", `toast${isError ? " error" : ""}`, message);
  elements.toastRegion.append(toast);
  window.setTimeout(() => toast.remove(), 5200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });
  if (!response.ok) {
    let detail = `Ошибка сервера (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail?.message || body.error?.message || body.detail || body.error?.code || detail;
      if (typeof detail !== "string") detail = JSON.stringify(detail);
    } catch {
      // Keep the HTTP status as a useful message when the response is not JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function setConnection(isOnline, label) {
  elements.connection.textContent = label;
  elements.connectionStatus.classList.toggle("online", isOnline);
}

function setText(selector, value, fallback = "—") {
  const element = document.querySelector(selector);
  if (element) element.textContent = value ?? fallback;
}

function formatRevenue(value) {
  if (value === null || value === undefined || value === "") return "Нет данных";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(number) + " ₽";
}

function updateCompanyCard(company) {
  setText("#company-name", company.company_id);
  setText("#company-industry", company.industry || "Профиль бизнеса");
  setText("#company-region", [company.city, company.region].filter(Boolean).join(", ") || "Нет данных");
  setText("#company-revenue", formatRevenue(company.revenue));
  setText("#company-okved", company.okved_code || "Нет данных");
  const percent = Math.round((Number(company.profile_completeness) || 0) * 100);
  setText("#profile-percent", `${percent}%`);
  setText("#metric-profile", String(percent));
  const progress = document.querySelector("#profile-progress");
  progress.style.width = `${Math.min(100, Math.max(0, percent))}%`;
  const avatar = document.querySelector("#company-avatar");
  avatar.textContent = company.industry?.trim()?.charAt(0)?.toLocaleUpperCase("ru-RU") || "А";
  const factorLabels = {
    industry: "Отрасль",
    region: "Регион",
    revenue: "Выручка",
    has_loans: "Кредиты",
    has_leasing: "Лизинг",
    has_guarantees: "Гарантии",
    has_foreign_trade: "Внешняя торговля",
  };
  for (const [id, value] of Object.entries({
    "detail-loans": company.has_loans,
    "detail-leasing": company.has_leasing,
    "detail-guarantees": company.has_guarantees,
    "detail-trade": company.has_foreign_trade,
  })) {
    setText(`#${id}`, value === null || value === undefined ? "Нет данных" : value ? "Да" : "Нет");
  }
  setText("#detail-countries", company.trade_countries?.length ? company.trade_countries.join(", ") : "Не указаны");
  setText("#detail-group", company.group_id || "Не указана");
  for (const [selector, values, emptyText] of [
    ["#known-fields", company.known_fields || [], "Нет известных полей"],
    ["#missing-fields", company.missing_fields || [], "Все основные поля заполнены"],
  ]) {
    const container = document.querySelector(selector);
    container.replaceChildren();
    if (!values.length) {
      container.append(makeElement("span", "field-tag", emptyText));
      continue;
    }
    for (const field of values) {
      container.append(makeElement("span", "field-tag", factorLabels[field] || field));
    }
  }
  document.querySelector("#metric-role").textContent = state.role.toUpperCase();
  document.querySelector("#metric-role-description").textContent = state.role === "cfo" ? "финансы и риски" : "стратегия и рост";
}

function categoryName(category) {
  if (!category) return "Экономика";
  const labels = {
    economy: "Экономика",
    finance: "Финансы",
    rates: "Денежная политика",
    currency: "Валюты",
    business: "Бизнес",
  };
  return labels[category.toLowerCase()] || category;
}

function createNewsCard(article) {
  const card = makeElement("article", "news-card");
  const top = makeElement("div", "news-card-top");
  const meta = makeElement("div", "news-meta");
  const mark = makeElement("span", "source-mark", article.source_name?.trim()?.charAt(0)?.toLocaleUpperCase("ru-RU") || "Н");
  meta.append(mark, makeElement("span", "", article.source_name || "Источник"), makeElement("span", "meta-separator", "·"), makeElement("span", "", formatDate(article.published_at || article.fetched_at)));
  const relevance = Number(article.relevance_score);
  const badgeClass = relevance >= 0.7 ? "relevance-badge" : relevance >= 0.4 ? "relevance-badge medium" : "relevance-badge low";
  const score = Number.isFinite(relevance) ? `${Math.round(relevance * 100)}%` : "Новая";
  const relevanceBadge = makeElement("span", badgeClass, `✳ ${score}`);
  top.append(meta, relevanceBadge);

  const title = makeElement("h3", "news-title", article.title);
  const summary = makeElement("p", "news-summary", article.summary || article.content || "Откройте материал, чтобы узнать подробности.");
  const reasonText = article.relevance_reasons?.[0];
  card.append(top, makeElement("div", "category-tag", categoryName(article.category)), title, summary);
  if (reasonText) {
    const reason = makeElement("div", "news-reason");
    reason.append(makeElement("span", "", "✳"), makeElement("span", "", reasonText));
    card.append(reason);
  }

  const bottom = makeElement("div", "news-card-bottom");
  const factors = makeElement("div", "news-factors");
  for (const factor of (article.matched_factors || []).slice(0, 3)) {
    factors.append(makeElement("span", "factor-tag", factor));
  }
  const openButton = makeElement("button", "read-link", "Подробнее  ↗");
  openButton.type = "button";
  openButton.addEventListener("click", () => openArticle(article));
  bottom.append(factors, openButton);
  card.append(bottom);
  return card;
}

function renderFeed() {
  const query = elements.search.value.trim().toLocaleLowerCase("ru-RU");
  const visibleArticles = state.feed.filter((article) =>
    `${article.title} ${article.summary} ${article.source_name}`.toLocaleLowerCase("ru-RU").includes(query),
  );
  elements.feed.replaceChildren();
  elements.feedCount.textContent = String(state.feed.length);
  setText("#metric-news", String(state.feed.length), "0");
  setText("#metric-relevant", String(state.feed.filter((article) => Number(article.relevance_score) >= 0.7).length), "0");
  if (!visibleArticles.length) {
    const empty = makeElement("div", "empty-state");
    empty.append(makeElement("span", "empty-icon", query ? "⌕" : "◷"));
    empty.append(makeElement("strong", "", query ? "Ничего не найдено" : "Пока нет новостей в ленте"));
    empty.append(makeElement("p", "", query
      ? "Попробуйте изменить запрос."
      : "Обновите новости, чтобы загрузить свежие материалы из RSS. Профиль компании уже подготовлен для персонализации."));
    elements.feed.append(empty);
    return;
  }
  for (const article of visibleArticles) elements.feed.append(createNewsCard(article));
}

async function loadProfileAndFeed() {
  if (!state.companyId) return;
  elements.feed.replaceChildren(makeElement("div", "loading-state", "Загружаем персональную ленту…"));
  try {
    const [company, feed] = await Promise.all([
      api(`/api/companies/${encodeURIComponent(state.companyId)}?role=${encodeURIComponent(state.role)}`),
      api(`/api/feed?company_id=${encodeURIComponent(state.companyId)}&role=${encodeURIComponent(state.role)}`),
    ]);
    state.feed = feed;
    updateCompanyCard(company);
    setConnection(true, "Сервис работает");
    renderFeed();
  } catch (error) {
    elements.feed.replaceChildren();
    const message = makeElement("div", "empty-state");
    message.append(makeElement("span", "empty-icon", "!"));
    message.append(makeElement("strong", "", "Не удалось загрузить данные"));
    message.append(makeElement("p", "", error.message));
    elements.feed.append(message);
    setConnection(false, "Нет соединения");
    showToast(error.message, true);
  }
}

async function loadCompanies() {
  try {
    state.companies = await api("/api/companies");
    elements.companySelect.replaceChildren();
    for (const company of state.companies) {
      const option = document.createElement("option");
      option.value = company.company_id;
      option.textContent = company.industry
        ? `${company.company_id} · ${company.industry}`
        : company.company_id;
      elements.companySelect.append(option);
    }
    if (!state.companies.length) {
      elements.companySelect.append(new Option("Компании не найдены", ""));
      state.companyId = "";
      state.feed = [];
      renderFeed();
      return;
    }
    state.companyId = state.companies[0].company_id;
    elements.companySelect.value = state.companyId;
    await loadProfileAndFeed();
  } catch (error) {
    elements.companySelect.replaceChildren(new Option("Нет соединения с API", ""));
    setConnection(false, "Нет соединения");
    elements.feed.replaceChildren();
    const message = makeElement("div", "empty-state");
    message.append(makeElement("span", "empty-icon", "!"));
    message.append(makeElement("strong", "", "Сервис пока недоступен"));
    message.append(makeElement("p", "", `Не удалось получить список компаний: ${error.message}`));
    elements.feed.append(message);
  }
}

function makeInsightBlock(title, value) {
  const section = makeElement("section", "insight-block");
  section.append(makeElement("h4", "", title));
  if (Array.isArray(value)) {
    const list = makeElement("ul");
    for (const item of value) {
      const text = typeof item === "string" ? item : item?.text || item?.description || JSON.stringify(item);
      list.append(makeElement("li", "", text));
    }
    section.append(list);
  } else {
    const text = typeof value === "string" ? value : value?.text || JSON.stringify(value || "Нет данных");
    section.append(makeElement("p", "", text));
  }
  return section;
}

function renderInsight(insight) {
  state.activeInsightId = insight.insight_id;
  const result = makeElement("div", "insight-result");
  result.append(makeElement("h3", "", "Что это значит для бизнеса"));
  result.append(makeInsightBlock("Что произошло", insight.what_happened));
  result.append(makeInsightBlock("Почему это важно", insight.why_it_matters));
  result.append(makeInsightBlock("Риски", insight.risks));
  result.append(makeInsightBlock("Возможности", insight.opportunities));
  result.append(makeInsightBlock("Следующие шаги", insight.next_steps));
  result.append(makeElement("span", "validation-note", `Демонстрационный анализ · статус проверки: ${insight.validation_status}`));

  const form = makeElement("form", "question-form");
  const input = document.createElement("input");
  input.type = "text";
  input.name = "question";
  input.minLength = 2;
  input.maxLength = 1000;
  input.required = true;
  input.placeholder = "Спросите, как это повлияет на компанию";
  input.setAttribute("aria-label", "Ваш вопрос по инсайту");
  const submit = makeElement("button", "", "Спросить");
  submit.type = "submit";
  form.append(input, submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const answer = await api(`/api/insights/${encodeURIComponent(state.activeInsightId)}/questions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: input.value.trim() }),
      });
      result.append(makeElement("div", "question-answer", answer.answer));
      input.value = "";
    } catch (error) {
      showToast(error.message, true);
    } finally {
      submit.disabled = false;
    }
  });
  result.append(form);
  elements.dialogContent.append(result);
}

function openArticle(article) {
  state.activeArticle = article;
  state.activeInsightId = null;
  elements.dialogContent.replaceChildren();
  const source = makeElement("div", "dialog-source");
  source.append(
    makeElement("span", "category-tag", categoryName(article.category)),
    makeElement("span", "", article.source_name || "Источник"),
    makeElement("span", "meta-separator", "·"),
    makeElement("span", "", formatDate(article.published_at || article.fetched_at)),
  );
  elements.dialogContent.append(source, makeElement("h2", "", article.title));
  const copy = article.content || article.summary || "Полный текст материала в источнике.";
  elements.dialogContent.append(makeElement("p", "dialog-lead", copy));
  if (article.relevance_reasons?.length) {
    const reasons = makeElement("div", "dialog-reasons");
    for (const item of article.relevance_reasons.slice(0, 4)) {
      const reason = makeElement("div", "dialog-reason");
      reason.append(makeElement("span", "", "✳"), makeElement("span", "", item));
      reasons.append(reason);
    }
    elements.dialogContent.append(reasons);
  }
  const button = makeElement("button", "button insight-button", "✳  Получить инсайт для компании");
  button.type = "button";
  button.addEventListener("click", () => createInsight(button));
  elements.dialogContent.append(button);

  const sourceUrl = safeExternalUrl(article.source_url);
  if (sourceUrl) {
    const link = document.createElement("a");
    link.className = "read-link";
    link.href = sourceUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Открыть первоисточник ↗";
    link.style.marginTop = "13px";
    elements.dialogContent.append(link);
  }
  elements.dialog.showModal();
}

function safeExternalUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

async function createInsight(button) {
  const article = state.activeArticle;
  if (!article || !state.companyId) return;
  button.disabled = true;
  button.textContent = "Формируем анализ…";
  try {
    const insight = await api("/api/insights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_id: state.companyId,
        article_id: article.id,
        user_role: state.role,
      }),
    });
    renderInsight(insight);
  } catch (error) {
    showToast(error.message, true);
    button.disabled = false;
    button.textContent = "✳  Получить инсайт для компании";
  }
}

async function refreshNews() {
  const button = document.querySelector("#refresh-button");
  button.disabled = true;
  const label = button.querySelector("span:last-child");
  const originalLabel = label.textContent;
  label.textContent = "Обновляем…";
  try {
    const result = await api("/api/news/refresh", { method: "POST" });
    await loadProfileAndFeed();
    if (result.failures?.length && !result.inserted && !result.skipped) {
      showToast("RSS-источники временно недоступны. Сохранённые новости остаются в ленте.", true);
    } else {
      showToast(`Лента обновлена: добавлено ${result.inserted ?? 0}, пропущено ${result.skipped ?? 0}.`);
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    label.textContent = originalLabel;
  }
}

function setRole(role) {
  state.role = role;
  document.querySelectorAll(".role-option").forEach((button) => {
    const selected = button.dataset.role === role;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  if (state.companyId) loadProfileAndFeed();
}

function setView(view) {
  const views = {
    overview: {
      title: "Добро пожаловать",
      subtitle: "Важные новости и сигналы для решений — в одном месте.",
      kicker: "ВАШ БИЗНЕС, В ФОКУСЕ",
    },
    news: {
      title: "Новостная лента",
      subtitle: "Материалы, отсортированные по значимости для вашей компании и роли.",
      kicker: "ВАЖНОЕ ДЛЯ ВАС",
    },
    company: {
      title: "Профиль компании",
      subtitle: "Данные бизнеса, на которых строится персональная аналитика.",
      kicker: "ВАША КОМПАНИЯ",
    },
  };
  const selectedView = views[view] ? view : "overview";
  const config = views[selectedView];
  elements.main.dataset.view = selectedView;
  document.querySelector("#page-title").replaceChildren(
    document.createTextNode(config.title),
    makeElement("span", "heading-period", "."),
  );
  setText("#page-subtitle", config.subtitle);
  setText("#heading-kicker", config.kicker);
  setText(".breadcrumbs strong", selectedView === "overview" ? "Обзор" : config.title);
  document.querySelectorAll(".nav-link").forEach((link) => {
    const active = link.dataset.view === selectedView;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const activeLink = document.querySelector(`.nav-link[data-view="${selectedView}"]`);
  if (activeLink && window.location.hash !== activeLink.hash) {
    window.history.replaceState(null, "", activeLink.hash);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initialize() {
  const today = new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  setText("#today-date", today.charAt(0).toLocaleUpperCase("ru-RU") + today.slice(1));

  elements.companySelect.addEventListener("change", () => {
    state.companyId = elements.companySelect.value;
    loadProfileAndFeed();
  });
  document.querySelectorAll(".role-option").forEach((button) => {
    button.addEventListener("click", () => setRole(button.dataset.role));
  });
  elements.search.addEventListener("input", renderFeed);
  document.querySelector("#refresh-button").addEventListener("click", refreshNews);
  document.querySelector("#promo-news-button").addEventListener("click", () => setView("news"));
  document.querySelector("#close-dialog").addEventListener("click", () => elements.dialog.close());
  elements.dialog.addEventListener("click", (event) => {
    if (event.target === elements.dialog) elements.dialog.close();
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setView(link.dataset.view);
    });
  });

  const initialHash = window.location.hash;
  const initialLink = [...document.querySelectorAll(".nav-link")].find((link) => link.hash === initialHash);
  if (initialLink) setView(initialLink.dataset.view);
  loadCompanies();
}

initialize();
