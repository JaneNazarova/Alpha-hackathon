import { askQuestion, createInsight, getCompanies, getCompany, getFeed, getMlQuality, refreshNews } from "./js/api.js";
import { makeElement, setText } from "./js/dom.js";
import { renderArticleDialog, renderCompany, renderFeed, renderInsightDialog, renderMlQuality } from "./js/render.js";

const state = {
  companies: [],
  companyId: "",
  role: "ceo",
  feed: [],
  weights: null,
};

const dialog = document.querySelector("#article-dialog");
const dialogContent = document.querySelector("#dialog-content");
const feedList = document.querySelector("#feed-list");
const refreshButton = document.querySelector("#refresh-button");
const toastRegion = document.querySelector("#toast-region");
let loadSequence = 0;
let companySearchTimer;
let activeArticle = null;
let qualityReportLoaded = false;

function setServiceStatus(status, label) {
  const node = document.querySelector("#service-state");
  node.classList.toggle("online", status === "online");
  node.classList.toggle("offline", status === "offline");
  setText("#connection-label", label);
}

function showToast(message, kind = "success") {
  const toast = makeElement("div", `toast ${kind}`, message);
  const close = makeElement("button", "toast-close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть сообщение");
  close.addEventListener("click", () => toast.remove());
  toast.append(close);
  toastRegion.append(toast);
  if (kind !== "error") window.setTimeout(() => toast.remove(), 4000);
}

function showFeedMessage(title, description, { isError = false, withRetry = false } = {}) {
  feedList.replaceChildren();
  feedList.setAttribute("aria-busy", "false");
  const empty = makeElement("div", "empty-state");
  empty.append(makeElement("h3", "", title));
  empty.append(makeElement("p", "", description));
  if (withRetry) {
    const retry = makeElement("button", "button button-primary", "Повторить загрузку");
    retry.type = "button";
    retry.addEventListener("click", () => loadCompanies());
    empty.append(retry);
  }
  feedList.append(empty);
  if (isError) setServiceStatus("offline", "Нет соединения");
}

function renderCurrentFeed() {
  renderFeed(state.feed, document.querySelector("#search-input").value, {
    onOpen: openArticle,
    onRefresh: handleRefresh,
  });
}

async function loadCompanies(query = "") {
  feedList.replaceChildren();
  feedList.setAttribute("aria-busy", "true");
  feedList.append(makeElement("div", "loading-state", "Загружаем список компаний…"));
  try {
    state.companies = await getCompanies(query);
    const select = document.querySelector("#company-select");
    select.replaceChildren();
    for (const company of state.companies) {
      const option = makeElement("option", "", company.industry
        ? `${company.company_id} · ${company.industry}`
        : company.company_id);
      option.value = company.company_id;
      select.append(option);
    }

    if (!state.companies.length) {
      select.append(new Option("Компании не найдены", ""));
      if (query) {
        showFeedMessage("Компаний по запросу не найдено", "Попробуйте искать по ID, названию отрасли или региону.");
      } else {
        state.companyId = "";
        state.feed = [];
        showFeedMessage("Нет доступных компаний", "Проверьте CSV-файл компаний и настройки сервиса.");
      }
      return;
    }

    const currentExists = state.companies.some((company) => company.company_id === state.companyId);
    state.companyId = currentExists ? state.companyId : state.companies[0].company_id;
    select.value = state.companyId;
    await loadProfileAndFeed();
  } catch (error) {
    document.querySelector("#company-select").replaceChildren(new Option("Не удалось загрузить список", ""));
    showFeedMessage("Не удалось подключиться к сервису", error.message, { isError: true, withRetry: true });
  }
}

async function loadProfileAndFeed() {
  if (!state.companyId) return;
  const sequence = ++loadSequence;
  feedList.replaceChildren();
  feedList.setAttribute("aria-busy", "true");
  feedList.append(makeElement("div", "loading-state", "Загружаем профиль и ленту…"));
  try {
    const [company, feed] = await Promise.all([
      getCompany(state.companyId, state.role),
      getFeed(state.companyId, state.role, state.weights),
    ]);
    if (sequence !== loadSequence) return;
    state.feed = feed;
    renderCompany(company, state.role);
    renderCurrentFeed();
    setServiceStatus("online", "Сервис работает");
    return true;
  } catch (error) {
    if (sequence !== loadSequence) return;
    state.feed = [];
    showFeedMessage("Не удалось загрузить данные", `${error.message} Проверьте подключение и повторите попытку.`, { isError: true });
    showToast(error.message, "error");
    return false;
  }
}

function openArticle(article) {
  activeArticle = article;
  document.querySelector("#dialog-subtitle").textContent = `${article.source_name || "Источник"} · ${state.companyId} · ${state.role.toUpperCase()}`;
  renderArticleDialog(dialogContent, article, { onCreateInsight: handleCreateInsight });
  dialog.showModal();
}

async function handleCreateInsight(button) {
  if (!activeArticle?.id) {
    showToast("Не удалось определить публикацию. Закройте разбор и откройте новость ещё раз.", "error");
    return;
  }

  button.disabled = true;
  button.textContent = "Формируем разбор…";
  try {
    const insight = await createInsight(state.companyId, activeArticle.id, state.role);
    renderInsightDialog(dialogContent, insight, askQuestion);
    dialogContent.scrollTop = 0;
  } catch (error) {
    button.disabled = false;
    button.textContent = "Сформировать инсайт для компании";
    showToast(error.message, "error");
  }
}

async function handleRefresh() {
  refreshButton.disabled = true;
  const buttonLabel = refreshButton.querySelector("span");
  const originalLabel = buttonLabel.textContent;
  buttonLabel.textContent = "Обновляем…";
  try {
    const result = await refreshNews();
    await loadProfileAndFeed();
    if (result.failures?.length && !result.inserted && !result.skipped) {
      showToast("RSS-источники временно недоступны. Сохранённые новости остаются в ленте.", "error");
    } else {
      showToast(`Новости обновлены: добавлено ${result.inserted ?? 0}, пропущено ${result.skipped ?? 0}.`);
    }
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    refreshButton.disabled = false;
    buttonLabel.textContent = originalLabel;
  }
}

function setRole(role) {
  if (!["ceo", "cfo"].includes(role) || role === state.role) return;
  state.role = role;
  document.querySelectorAll(".role-option").forEach((button) => {
    const selected = button.dataset.role === role;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  if (state.companyId) loadProfileAndFeed();
}

function setActiveNavigation() {
  const current = window.location.hash || "#overview";
  document.querySelectorAll(".nav-link").forEach((link) => {
    const active = link.hash === current;
    link.classList.toggle("is-active", active);
    if (active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}

async function loadMlQuality() {
  const button = document.querySelector("#ml-quality-button");
  const status = document.querySelector("#ml-quality-status");
  const report = document.querySelector("#ml-quality-report");
  button.disabled = true;
  button.textContent = "Проверяем…";
  status.classList.remove("error");
  status.textContent = "Проверяем CSV, профили и сохранённые новости. Первый расчёт полного набора может занять минуту и дольше; затем отчёт кэшируется до изменения файлов.";
  report.setAttribute("aria-busy", "true");
  try {
    const result = await getMlQuality();
    renderMlQuality(report, result, {
      onApplyWeights: async (weights) => {
        const previousWeights = state.weights;
        state.weights = weights;
        const loaded = await loadProfileAndFeed();
        if (loaded) showToast("Веса применены к ленте этой страницы.");
        else state.weights = previousWeights;
      },
    });
    status.textContent = "Отчёт готов. CSV и сохранённые новости проверены; оценка качества ранжирования рассчитана на синтетическом наборе.";
    qualityReportLoaded = true;
  } catch (error) {
    status.classList.add("error");
    status.textContent = `${error.message} Проверьте файлы CSV и повторите запрос.`;
  } finally {
    report.setAttribute("aria-busy", "false");
    button.disabled = false;
    button.textContent = qualityReportLoaded ? "Обновить отчёт" : "Проверить качество";
  }
}

function initialize() {
  const today = new Intl.DateTimeFormat("ru-RU", {
    weekday: "long", day: "numeric", month: "long",
  }).format(new Date());
  setText("#today-date", today.charAt(0).toLocaleUpperCase("ru-RU") + today.slice(1));
  document.querySelector("#company-select").addEventListener("change", (event) => {
    state.companyId = event.currentTarget.value;
    loadProfileAndFeed();
  });
  document.querySelector("#company-search").addEventListener("input", (event) => {
    const query = event.currentTarget.value.trim();
    window.clearTimeout(companySearchTimer);
    if (query.length === 1) return;
    companySearchTimer = window.setTimeout(() => loadCompanies(query), query ? 350 : 0);
  });
  document.querySelectorAll(".role-option").forEach((button) => {
    button.addEventListener("click", () => setRole(button.dataset.role));
  });
  document.querySelector("#search-input").addEventListener("input", renderCurrentFeed);
  refreshButton.addEventListener("click", handleRefresh);
  document.querySelector("#ml-quality-button").addEventListener("click", loadMlQuality);
  document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  window.addEventListener("hashchange", setActiveNavigation);
  setActiveNavigation();
  loadCompanies();
}

initialize();
