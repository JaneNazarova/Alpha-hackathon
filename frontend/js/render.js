import { formatDate, formatMoney, formatPaymentAmount, makeElement, safeExternalUrl, setText } from "./dom.js";

const FIELD_LABELS = {
  company_id: "Компания",
  industry: "Отрасль", okved_code: "ОКВЭД", region: "Регион", city: "Город",
  revenue: "Выручка", group_id: "Группа компаний", company_age: "Возраст компании",
  business_stage: "Стадия бизнеса", workers_fns: "Численность по ФНС",
  workers_spark: "Численность по СПАРК", has_loans: "Кредиты", has_leasing: "Лизинг",
  has_guarantees: "Гарантии", has_deposits: "Депозиты", has_factoring: "Факторинг",
  has_foreign_trade: "Внешняя торговля", trade_countries: "Страны торговли",
  industry_tags: "Отрасль", freshness: "Свежесть", published_at: "Свежесть",
  finance: "Финансовый профиль", geography: "География", relations: "Деловые связи",
  event: "Связь с событием", role: "Приоритет роли", user_role: "Приоритет роли",
};

const CATEGORY_LABELS = {
  monetary_policy: "Денежная политика", macro_stats: "Макроэкономика", macroeconomics: "Макроэкономика",
  industry: "Отрасли", company_news: "Новости компаний", corporate_events: "События компаний",
  tax_regulation: "Налоги и регулирование", logistics_trade: "Торговля и логистика",
  currency: "Валюты", commodities: "Сырьевые рынки", labor: "Рынок труда",
  other: "Экономика", economy: "Экономика",
};

function formatCategory(article) {
  const category = article.categories?.[0] || article.category;
  if (!category) return "Экономика";
  return CATEGORY_LABELS[String(category).toLowerCase()] || String(category).replaceAll("_", " ");
}

function displayRoleValue(value) {
  if (value === null || value === undefined || value === "") return "Нет данных";
  if (typeof value === "boolean") return value ? "Есть" : "Нет";
  return String(value);
}

function addTags(container, values, emptyMessage) {
  container.replaceChildren();
  if (!values?.length) {
    container.append(makeElement("span", "profile-tag", emptyMessage));
    return;
  }
  for (const value of values.slice(0, 8)) {
    container.append(makeElement("span", "profile-tag", FIELD_LABELS[value] || value));
  }
  if (values.length > 8) {
    container.append(makeElement("span", "profile-tag", `Ещё ${values.length - 8}`));
  }
}

export function renderCompany(company, role) {
  setText("#profile-title", company.company_id);
  setText("#company-industry", company.industry || "Отрасль не указана");
  setText("#company-region", [company.city, company.region].filter(Boolean).join(", ") || "Нет данных");
  setText("#company-revenue", formatMoney(company.revenue));
  setText("#company-okved", company.okved_code || "Нет данных");
  setText("#company-group", company.group_id || "Нет данных");
  setText("#company-trade-countries", company.trade_countries?.length ? company.trade_countries.join(", ") : "Нет данных");
  setText("#company-age", company.company_age || "Нет данных");
  setText("#company-stage", company.business_stage || "Нет данных");
  const workers = [
    company.workers_fns ? `ФНС: ${company.workers_fns}` : null,
    company.workers_spark ? `СПАРК: ${company.workers_spark}` : null,
  ].filter(Boolean);
  setText("#company-workers", workers.join(" · ") || "Нет данных");
  setText("#profile-percent", `${Math.round((Number(company.profile_completeness) || 0) * 100)}%`);

  const percent = Math.min(100, Math.max(0, Math.round((Number(company.profile_completeness) || 0) * 100)));
  setText("#metric-profile", String(percent));
  setText("#profile-percent-label", `${percent}%`);
  for (const selector of ["#profile-progress", "#profile-progress-detail"]) {
    const bar = document.querySelector(selector);
    if (bar) bar.style.width = `${percent}%`;
  }

  const roleLabels = {
    "#metric-role": role.toUpperCase(),
    "#metric-role-description": role === "cfo" ? "Финансы и риски" : "Стратегия и развитие",
  };
  for (const [selector, value] of Object.entries(roleLabels)) setText(selector, value);

  const productFields = {
    "#detail-loans": company.has_loans,
    "#detail-leasing": company.has_leasing,
    "#detail-guarantees": company.has_guarantees,
    "#detail-deposits": company.has_deposits,
    "#detail-factoring": company.has_factoring,
    "#detail-trade": company.has_foreign_trade,
  };
  for (const [selector, value] of Object.entries(productFields)) {
    setText(selector, displayRoleValue(value));
    const output = document.querySelector(selector);
    output?.classList.toggle("is-unknown", value === null || value === undefined);
  }

  const payments = company.payments;
  setText("#payment-incoming", formatPaymentAmount(payments?.incoming_amount));
  setText("#payment-outgoing", formatPaymentAmount(payments?.outgoing_amount));
  const counterpartyCount = company.counterparty_ids?.length;
  setText("#payment-counterparties", counterpartyCount === undefined ? "Нет данных" : String(counterpartyCount));
  const paymentIssues = Object.values(payments?.invalid_or_missing_cells || {}).reduce((sum, count) => sum + Number(count || 0), 0);
  setText("#payment-quality", payments ? (paymentIssues ? `Не удалось обработать ${paymentIssues} значений платежей.` : "Ошибок формата сумм и количества не найдено.") : "Данные платежей не подключены.");
  const relations = [
    ["#group-company-count", company.group_company_ids],
    ["#linked-company-count", company.linked_company_ids],
    ["#relation-counterparty-count", company.counterparty_ids],
  ];
  const relationIds = new Set();
  for (const [selector, ids] of relations) {
    setText(selector, ids === null || ids === undefined ? "Нет данных" : String(ids.length));
    (ids || []).forEach((id) => relationIds.add(id));
  }
  const relationTags = document.querySelector("#company-relations");
  relationTags.replaceChildren();
  if (relationIds.size) {
    for (const id of [...relationIds].sort()) {
      relationTags.append(makeElement("span", "profile-tag", id));
    }
  } else {
    relationTags.append(makeElement("span", "profile-tag", "Связи не указаны"));
  }
  const relationSourceNames = Object.values(company.relation_sources || {})
    .filter(Boolean)
    .map((source) => String(source).split(/[\\/]/).pop());
  setText("#relation-sources", relationSourceNames.length
    ? `Источники связей: ${[...new Set(relationSourceNames)].join(", ")}.`
    : "Источники связей не указаны.");
  addTags(document.querySelector("#known-fields"), company.known_fields || [], "Пока нет данных");
  addTags(document.querySelector("#missing-fields"), company.missing_fields || [], "Нет пропусков");
  setText("#missing-count", company.missing_fields?.length ? `(${company.missing_fields.length})` : "(нет)");

  const invalidFields = document.querySelector("#invalid-fields");
  invalidFields.textContent = company.invalid_fields?.length
    ? `Проверьте значения полей: ${company.invalid_fields.map((field) => FIELD_LABELS[field] || field).join(", ")}.`
    : "Некорректных значений не найдено.";
  const uncertainties = document.querySelector("#profile-uncertainties");
  uncertainties.replaceChildren();
  for (const uncertainty of company.uncertainties || []) uncertainties.append(makeElement("li", "", uncertainty));
  const sourceList = document.querySelector("#field-sources");
  sourceList.replaceChildren();
  for (const [field, origin] of Object.entries(company.field_sources || {})) {
    const row = makeElement("div");
    row.append(makeElement("dt", "", FIELD_LABELS[field] || field));
    const sourceName = origin.source === "derived" ? "Расчёт" : String(origin.source || "").split(/[\\/]/).pop();
    const provenance = [origin.column, origin.rule, sourceName].filter(Boolean).join(" · ");
    row.append(makeElement("dd", "", provenance || "Источник не указан"));
    sourceList.append(row);
  }
}

function renderReason(article) {
  const reason = article.relevance_reasons?.[0];
  if (!reason) return null;
  const row = makeElement("div", "news-reason");
  row.append(makeElement("span", "news-reason-label", "Связь с бизнесом"));
  row.append(makeElement("span", "", reason));
  return row;
}

function renderArticleCard(article, onOpen) {
  const card = makeElement("article", "news-card");
  const meta = makeElement("div", "news-meta");
  meta.append(makeElement("span", "source-name", article.source_name || "Источник"));
  meta.append(makeElement("span", "meta-separator", "·"));
  const date = makeElement("time", "", formatDate(article.published_at || article.fetched_at));
  if (article.published_at || article.fetched_at) date.dateTime = article.published_at || article.fetched_at;
  meta.append(date);

  const score = Number(article.relevance_score);
  if (Number.isFinite(score)) {
    const scoreLabel = makeElement("span", "score-label");
    scoreLabel.append(document.createTextNode("Релевантность "));
    scoreLabel.append(makeElement("strong", "", `${Math.round(score * 100)}%`));
    meta.append(scoreLabel);
  }

  card.append(meta, makeElement("p", "category-tag", formatCategory(article)));
  card.append(makeElement("h3", "news-title", article.title));
  if (article.summary || article.content) {
    card.append(makeElement("p", "news-summary", article.summary || article.content));
  }
  const reason = renderReason(article);
  if (reason) card.append(reason);

  const footer = makeElement("div", "news-footer");
  const factors = makeElement("div", "factor-list");
  for (const factor of (article.matched_factors || []).slice(0, 3)) {
    factors.append(makeElement("span", "factor-tag", FIELD_LABELS[factor] || String(factor).replaceAll("_", " ")));
  }
  footer.append(factors);
  if (article.additional_sources?.length) {
    footer.append(makeElement("span", "source-count", `Ещё источников: ${article.additional_sources.length}`));
  }
  const open = makeElement("button", "text-button", "Разобрать новость");
  open.type = "button";
  open.setAttribute("aria-label", `Открыть разбор: ${article.title}`);
  open.addEventListener("click", () => onOpen(article));
  open.append(makeElement("span", "", "↗"));
  footer.append(open);
  card.append(footer);
  return card;
}

export function renderFeed(articles, query, { onOpen, onRefresh }) {
  const feed = document.querySelector("#feed-list");
  const term = query.trim().toLocaleLowerCase("ru-RU");
  const visible = articles.filter((article) =>
    `${article.title} ${article.summary || ""} ${article.content || ""} ${article.source_name || ""}`
      .toLocaleLowerCase("ru-RU").includes(term),
  );
  feed.replaceChildren();
  feed.setAttribute("aria-busy", "false");
  setText("#feed-count", String(articles.length));
  setText("#metric-news", String(articles.length));
  setText("#metric-relevant", String(articles.filter((item) => Number(item.relevance_score) >= 0.7).length));

  if (!visible.length) {
    const empty = makeElement("div", "empty-state");
    const heading = term ? "Не нашли совпадений" : "В ленте пока нет новостей";
    const description = term
      ? "Измените запрос или очистите поле поиска, чтобы увидеть все материалы."
      : "Загрузите свежие публикации из настроенных RSS-источников.";
    empty.append(makeElement("h3", "", heading));
    empty.append(makeElement("p", "", description));
    if (!term) {
      const refresh = makeElement("button", "button button-primary", "Обновить новости");
      refresh.type = "button";
      refresh.addEventListener("click", onRefresh);
      empty.append(refresh);
    }
    feed.append(empty);
    return;
  }

  for (const article of visible) feed.append(renderArticleCard(article, onOpen));
}

function renderStringList(value, emptyMessage) {
  if (!value?.length) return makeElement("p", "", emptyMessage);
  const list = makeElement("ul", "insight-list");
  for (const item of value) {
    const text = typeof item === "string" ? item : item?.description || item?.text || "";
    if (text) list.append(makeElement("li", "", text));
  }
  return list.children.length ? list : makeElement("p", "", emptyMessage);
}

function insightBlock(title, value, { modifier = "", emptyMessage = "Подтверждённых данных нет." } = {}) {
  const section = makeElement("section", `insight-block ${modifier}`.trim());
  section.append(makeElement("h3", "", title));
  if (Array.isArray(value)) section.append(renderStringList(value, emptyMessage));
  else section.append(makeElement("p", "", value || emptyMessage));
  return section;
}

export function renderArticleDialog(content, article, { onCreateInsight, onAsk }) {
  content.replaceChildren();
  const meta = makeElement("div", "dialog-article-meta");
  meta.append(makeElement("span", "category-tag", formatCategory(article)));
  meta.append(makeElement("span", "meta-separator", "·"));
  meta.append(makeElement("span", "", article.source_name || "Источник"));
  meta.append(makeElement("span", "meta-separator", "·"));
  meta.append(makeElement("time", "", formatDate(article.published_at || article.fetched_at)));
  content.append(meta, makeElement("h2", "", article.title));
  content.lastElementChild.id = "dialog-title";
  content.append(makeElement("p", "dialog-lead", article.content || article.summary || "Текст публикации не предоставлен источником."));

  const sourceUrl = safeExternalUrl(article.source_url);
  if (sourceUrl) {
    const link = makeElement("a", "dialog-source-link", "Открыть первоисточник ↗");
    link.href = sourceUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    content.append(link);
  }

  const reasons = article.relevance_reasons || [];
  const factorValues = Object.entries(article.factor_contributions || {})
    .filter(([, value]) => Number(value) > 0)
    .sort((a, b) => b[1] - a[1]);
  const relevanceSection = makeElement("section", "dialog-section");
  relevanceSection.append(makeElement("h3", "", "Почему новость в ленте"));
  if (reasons.length) {
    const list = makeElement("ul", "reason-list");
    for (const reason of reasons) list.append(makeElement("li", "", reason));
    relevanceSection.append(list);
  } else {
    relevanceSection.append(makeElement("p", "", "Оценка связи с профилем недоступна для этого материала."));
  }
  if (factorValues.length) {
    const factors = makeElement("div", "factor-list profile-tags");
    for (const [name, contribution] of factorValues.slice(0, 7)) {
      factors.append(makeElement("span", "factor-tag", `${FIELD_LABELS[name] || name}: ${Math.round(Number(contribution) * 100)}%`));
    }
    relevanceSection.append(factors);
  }
  content.append(relevanceSection);

  const details = makeElement("details", "explain-details");
  details.append(makeElement("summary", "", "Показать детали оценки"));
  const weightValues = article.factor_weights || {};
  const signalValues = article.factor_values || {};
  const factorRows = Object.keys(weightValues).map((name) => ({
    name,
    signal: Number(signalValues[name] || 0),
    weight: Number(weightValues[name] || 0),
    contribution: Number(article.factor_contributions?.[name] || 0),
  }));
  if (factorRows.length) {
    const list = makeElement("ul", "evidence-list");
    for (const factor of factorRows.filter((item) => item.signal > 0).sort((a, b) => b.contribution - a.contribution)) {
      list.append(makeElement("li", "", `${FIELD_LABELS[factor.name] || factor.name}: сила сигнала ${Math.round(factor.signal * 100)}%, вес ${Math.round(factor.weight * 100)}%, вклад ${Math.round(factor.contribution * 100)}%.`));
    }
    if (!list.children.length) list.append(makeElement("li", "", "Факторы связи с компанией не сработали; оценка основана на временной и ролевой приоритизации."));
    details.append(list);
  }
  if (article.evidence?.length) {
    const list = makeElement("ul", "evidence-list");
    for (const item of article.evidence) {
      const field = FIELD_LABELS[item.company_field] || String(item.company_field || "Признак").replaceAll("_", " ");
      const value = Array.isArray(item.company_value)
        ? item.company_value.join(", ")
        : displayRoleValue(item.company_value);
      list.append(makeElement("li", "", `${FIELD_LABELS[item.factor] || item.factor}: ${item.reason || "Связь учтена"} (${field}: ${value}).`));
    }
    details.append(list);
  }
  const algorithm = makeElement("p", "profile-help", `Версия алгоритма: ${article.algorithm_version || "не указана"}${article.event_id ? ` · ID события: ${article.event_id}` : ""}.`);
  details.append(algorithm);
  content.append(details);

  if (article.additional_sources?.length) {
    const section = makeElement("section", "dialog-section");
    section.append(makeElement("h3", "", `Другие источники (${article.additional_sources.length})`));
    const list = makeElement("ul", "source-list");
    for (const source of article.additional_sources) {
      const item = makeElement("li");
      const url = safeExternalUrl(source.url);
      const title = [source.source_name, source.title].filter(Boolean).join(" · ") || source.id || "Публикация";
      if (url) {
        const link = makeElement("a", "", title);
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.append(link);
      } else {
        item.textContent = title;
      }
      list.append(item);
    }
    section.append(list);
    content.append(section);
  }
  if (article.uncertainties?.length) {
    content.append(insightBlock("Ограничения данных", article.uncertainties, { emptyMessage: "Не указаны." }));
  }

  const createButton = makeElement("button", "button button-primary", "Сформировать инсайт для компании");
  createButton.type = "button";
  createButton.addEventListener("click", () => onCreateInsight(createButton));
  content.append(createButton);
}

function formatPercent(value) {
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format((Number(value) || 0) * 100)}%`;
}

function reportMetric(title, value, note) {
  const card = makeElement("section", "ml-report-card");
  card.append(makeElement("h3", "", title));
  card.append(makeElement("strong", "ml-report-value", value));
  if (note) card.append(makeElement("p", "", note));
  return card;
}

function reportDetails(title, rows) {
  const details = makeElement("details", "ml-report-disclosure");
  details.append(makeElement("summary", "", title));
  const list = makeElement("ul", "ml-issue-list");
  for (const row of rows) list.append(makeElement("li", "", row));
  if (!rows.length) list.append(makeElement("li", "", "Замечаний нет."));
  details.append(list);
  return details;
}

export function renderMlQuality(container, report, { onApplyWeights } = {}) {
  container.replaceChildren();
  const { eda, validation, evaluation } = report;
  const companies = eda.companies;
  const payments = eda.payments;
  const links = eda.person_links;
  const personalized = evaluation.macro_metrics.personalized;
  const baseline = evaluation.macro_metrics.date_baseline;
  const deltaNdcg = (personalized["ndcg@5"] - baseline["ndcg@5"]) * 100;
  const cards = makeElement("div", "ml-report-grid");
  cards.append(reportMetric("Компании в CSV", new Intl.NumberFormat("ru-RU").format(companies.rows), `${companies.key_quality?.unique ?? 0} уникальных ID · ${companies.key_quality?.duplicate_ids ?? 0} неоднозначных`));
  cards.append(reportMetric("Профили прошли проверку", `${validation.valid_profiles} из ${validation.input_company_rows}`, `Средняя заполненность ${formatPercent(validation.mean_completeness)} · проблемных записей: ${validation.errors.length}`));
  cards.append(reportMetric("Контракт новостей", "Проверяется", "Формат RankedNews проверяется при каждом запросе персональной ленты."));
  cards.append(reportMetric("Платежные строки", new Intl.NumberFormat("ru-RU").format(payments?.rows || 0), payments ? `Ошибочные суммы: ${payments.invalid_amounts} · неизвестные контрагенты: ${payments.unknown_endpoints}` : "Таблица не предоставлена"));
  cards.append(reportMetric("nDCG@5 контрольного набора", formatPercent(personalized["ndcg@5"]), `Разница с сортировкой по дате: ${deltaNdcg >= 0 ? "+" : ""}${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(deltaNdcg)} п.п.`));
  cards.append(reportMetric("Доля объединённых дублей", formatPercent(evaluation.duplicate_fraction), `${evaluation.articles} публикаций · ${evaluation.companies} компании`));
  cards.append(reportMetric("Среднее время ранжирования", `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(evaluation.ranking_ms_mean)} мс`, `Алгоритм ${evaluation.algorithm_version} · контрольный набор`));
  container.append(cards);

  const weightsCard = makeElement("section", "ml-report-card");
  weightsCard.append(makeElement("h3", "", `Веса факторов · ${report.algorithm_version}`));
  const weights = makeElement("div", "ml-weight-list");
  for (const [name, weight] of Object.entries(report.weights)) {
    const row = makeElement("div", "ml-weight-row");
    row.append(makeElement("span", "", FIELD_LABELS[name] || name));
    const track = makeElement("div", "ml-weight-track");
    const bar = makeElement("span");
    bar.style.width = formatPercent(weight);
    track.append(bar);
    row.append(track, makeElement("strong", "", formatPercent(weight)));
    weights.append(row);
  }
  weightsCard.append(weights);
  const baselineRows = makeElement("dl", "ml-report-detail");
  baselineRows.append(makeElement("div", "", ""));
  baselineRows.lastElementChild.replaceChildren(makeElement("dt", "", "nDCG@5 по дате"), makeElement("dd", "", formatPercent(baseline["ndcg@5"])));
  baselineRows.append(makeElement("div", "", ""));
  baselineRows.lastElementChild.replaceChildren(makeElement("dt", "", "precision@5 персональная"), makeElement("dd", "", formatPercent(personalized["precision@5"])));
  baselineRows.append(makeElement("div", "", ""));
  baselineRows.lastElementChild.replaceChildren(makeElement("dt", "", "recall@5 персональная"), makeElement("dd", "", formatPercent(personalized["recall@5"])));
  weightsCard.append(baselineRows);
  weightsCard.append(makeElement("p", "", "Сравнительные метрики рассчитаны с весами по умолчанию."));

  const settings = makeElement("details", "ml-report-disclosure");
  settings.append(makeElement("summary", "", "Настроить веса для текущей ленты"));
  settings.append(makeElement("p", "profile-help", "Изменение действует только на эту страницу и не меняет общую настройку алгоритма."));
  const form = makeElement("form", "ml-weight-form");
  const controls = makeElement("div", "ml-weight-list");
  const inputByName = new Map();
  const defaultValues = Object.fromEntries(Object.entries(report.weights).map(([name, value]) => [name, Math.round(Number(value) * 100)]));
  const fields = Object.keys(report.weights);

  const updateDisplay = () => {
    for (const [name, input] of inputByName) {
      const output = form.querySelector(`output[data-for="${name}"]`);
      output.value = `${input.value}%`;
      output.textContent = `${input.value}%`;
    }
    const total = [...inputByName.values()].reduce((sum, input) => sum + Number(input.value), 0);
    totalLabel.textContent = `Сумма весов: ${total}%`;
  };

  const totalLabel = makeElement("p", "ml-weight-total", "Сумма весов: 100%");
  totalLabel.setAttribute("role", "status");
  const normalizeOthers = (changedName) => {
    const target = inputByName.get(changedName);
    const otherNames = fields.filter((name) => name !== changedName);
    const remaining = 100 - Number(target.value);
    const originalTotal = otherNames.reduce((sum, name) => sum + Number(inputByName.get(name).value), 0);
    let allocated = 0;
    otherNames.forEach((name, index) => {
      const input = inputByName.get(name);
      const value = index === otherNames.length - 1
        ? remaining - allocated
        : originalTotal > 0
          ? Math.floor(remaining * Number(input.value) / originalTotal)
          : Math.floor(remaining / otherNames.length);
      input.value = String(value);
      allocated += value;
    });
    updateDisplay();
  };

  for (const name of fields) {
    const row = makeElement("div", "ml-weight-input-row");
    const id = `ml-weight-${name}`;
    const label = makeElement("label", "", FIELD_LABELS[name] || name);
    label.htmlFor = id;
    const input = makeElement("input");
    input.id = id;
    input.name = name;
    input.type = "range";
    input.min = "0";
    input.max = "100";
    input.step = "1";
    input.value = String(defaultValues[name]);
    input.addEventListener("input", () => normalizeOthers(name));
    const output = makeElement("output");
    output.dataset.for = name;
    output.htmlFor = id;
    row.append(label, input, output);
    controls.append(row);
    inputByName.set(name, input);
  }
  form.append(controls, totalLabel);
  const actions = makeElement("div", "ml-weight-actions");
  const apply = makeElement("button", "button button-primary", "Применить к ленте");
  apply.type = "submit";
  const reset = makeElement("button", "button button-secondary", "Вернуть веса по умолчанию");
  reset.type = "button";
  reset.addEventListener("click", () => {
    for (const [name, value] of Object.entries(defaultValues)) inputByName.get(name).value = String(value);
    updateDisplay();
  });
  actions.append(apply, reset);
  form.append(actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    apply.disabled = true;
    apply.textContent = "Пересчитываем ленту…";
    try {
      const values = Object.fromEntries([...inputByName].map(([name, input]) => [name, Number(input.value) / 100]));
      await onApplyWeights?.(values);
    } finally {
      apply.disabled = false;
      apply.textContent = "Применить к ленте";
    }
  });
  settings.append(form);
  weightsCard.append(settings);
  updateDisplay();
  container.append(weightsCard);

  const missingRows = Object.entries(validation.missing_field_counts || {})
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([field, count]) => `${FIELD_LABELS[field] || field}: ${count}`);
  const invalidRows = Object.entries(validation.invalid_field_counts || {})
    .filter(([, count]) => count > 0)
    .map(([field, count]) => `${FIELD_LABELS[field] || field}: ${count} некорректных значений`);
  const profileErrorRows = (validation.errors || []).slice(0, 12)
    .map((error) => `${error.company_id}: ${error.code}`);
  const sourceRows = Object.entries(eda.columns || {})
    .sort((a, b) => (b[1].missing_fraction || 0) - (a[1].missing_fraction || 0))
    .slice(0, 8)
    .map(([field, stats]) => `${field}: ${formatPercent(stats.missing_fraction)} пропусков из ${companies.rows}`);
  const distributionRows = Object.entries(companies.columns || {})
    .filter(([, stats]) => stats.top_values?.length || stats.distribution)
    .slice(0, 10)
    .map(([field, stats]) => {
      if (stats.distribution) {
        const range = stats.distribution;
        return `${field}: медиана ${formatMoney(range.median)} · диапазон ${formatMoney(range.min)}–${formatMoney(range.max)} · выше 15 млрд: ${range.above_15bn}`;
      }
      return `${field}: ${(stats.top_values || []).slice(0, 5).map(([value, count]) => `${value} (${count})`).join(", ") || "значения не указаны"}`;
    });
  const benchmarkComparisons = (evaluation.comparisons || []).map((comparison) => {
    const metrics = evaluation.per_company.find((row) => row.company_id === comparison.company_id);
    const topPersonalized = comparison.top5.map((item) => `${item.id} (${item.grade})`).join(", ");
    return `${comparison.company_id}: персональное ранжирование nDCG ${formatPercent(metrics?.personalized?.["ndcg@5"])} против ${formatPercent(metrics?.date_baseline?.["ndcg@5"])} по дате; топ по баллам: ${topPersonalized}; по дате: ${comparison.baseline_top5.join(", " )}.`;
  });
  const diagnostics = makeElement("div", "ml-report-grid");
  diagnostics.append(reportDetails("Чаще всего не заполнены", missingRows));
  diagnostics.append(reportDetails("Некорректные значения в профилях", invalidRows));
  diagnostics.append(reportDetails("Профили с ошибками проверки", profileErrorRows));
  diagnostics.append(reportDetails("Сводка колонок CSV", sourceRows));
  diagnostics.append(reportDetails("Распределения CSV", distributionRows));
  diagnostics.append(reportDetails("Примеры top-5 в контрольном наборе", benchmarkComparisons));
  diagnostics.append(reportDetails("Проверки платежей и связей", [
    ...(payments ? [`Ошибочные количества платежей: ${payments.invalid_counts}`, `Строки платежей без стороны операции: ${payments.missing_endpoint_cells?.PAYER || 0} плательщиков, ${payments.missing_endpoint_cells?.BENEFICIARY || 0} получателей`] : ["CSV платежей не подключён."]),
    ...(payments ? [`Повторяющиеся строки платежей: ${payments.duplicate_records}`, `Покрытие платежами известных компаний: ${formatPercent(payments.known_company_coverage)}`] : []),
    ...(links ? [`Связи с неизвестным ID компании: ${links.unknown_companies}`, `Связи без ID физлица: ${links.missing_person_ids}`, `Повторяющиеся связи: ${links.duplicate_edges}`, `Покрытие известных компаний связями: ${formatPercent(links.known_company_coverage)}`] : ["CSV связей не подключён."]),
    `Дублирующиеся ID компаний: ${(companies.key_quality?.duplicate_ids || 0)}`,
  ]));
  container.append(diagnostics);

  const caveats = evaluation.limitations || [];
  if (caveats.length) {
    const notice = makeElement("section", "ml-quality-note");
    notice.append(makeElement("strong", "", "Ограничения контрольного набора: "));
    notice.append(document.createTextNode(caveats.join(" ")));
    container.append(notice);
  }
}

export function renderInsightDialog(content, insight, onAsk) {
  content.replaceChildren();
  const status = makeElement("p", "insight-status",
    insight.validation_status === "passed"
      ? `Проверка пройдена · ${insight.model_name || "AI-анализ"}`
      : "AI-анализ недоступен · показан ограниченный результат",
  );
  content.append(makeElement("h2", "", "Что это значит для компании"));
  const panel = makeElement("div", "insight-panel");
  panel.append(insightBlock("Что произошло", insight.what_happened, { emptyMessage: "Нет описания события." }));
  panel.append(insightBlock("Почему это важно", insight.why_it_matters, { emptyMessage: "Влияние не определено." }));
  panel.append(insightBlock("Риски", insight.risks, { modifier: "risk", emptyMessage: "Риски не подтверждены." }));
  panel.append(insightBlock("Возможности", insight.opportunities, { modifier: "opportunity", emptyMessage: "Возможности не подтверждены." }));
  panel.append(insightBlock("Следующие шаги", insight.next_steps, { emptyMessage: "Рекомендации не сформированы." }));
  const bankPosition = insight.bank_position?.text;
  panel.append(insightBlock("Материалы Альфа-Банка", bankPosition, {
    modifier: "bank",
    emptyMessage: "Подтверждённая позиция банка для этой новости не найдена.",
  }));
  if (insight.ai_conclusion) panel.append(insightBlock("Вывод модели", insight.ai_conclusion));
  if (insight.uncertainties?.length) panel.append(insightBlock("Ограничения и допущения", insight.uncertainties));
  content.append(status, panel);

  if (insight.sources?.length) {
    const section = makeElement("section", "dialog-section");
    section.append(makeElement("h3", "", "Источники"));
    const list = makeElement("ul", "source-list");
    for (const source of insight.sources) {
      const item = makeElement("li");
      const url = safeExternalUrl(source.url);
      if (url) {
        const link = makeElement("a", "", source.title || source.id || "Источник");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        item.append(link);
      } else {
        item.textContent = source.title || source.id || "Источник";
      }
      list.append(item);
    }
    section.append(list);
    content.append(section);
  }

  const form = makeElement("form", "question-form");
  const label = makeElement("label", "", "Задать вопрос по разбору");
  const input = makeElement("input");
  input.type = "text";
  input.name = "question";
  input.minLength = 2;
  input.maxLength = 1000;
  input.required = true;
  input.autocomplete = "off";
  input.placeholder = "Например: как это связано с кредитами компании?";
  label.append(input);
  const submit = makeElement("button", "", "Спросить");
  submit.type = "submit";
  form.append(label, submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (question.length < 2) {
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = "Готовим ответ…";
    try {
      const result = await onAsk(insight.insight_id, question);
      const answer = makeElement("p", "question-answer", result.answer);
      answer.setAttribute("role", "status");
      form.insertAdjacentElement("afterend", answer);
      input.value = "";
    } catch (error) {
      const message = makeElement("p", "question-error", `${error.message} Проверьте подключение и попробуйте ещё раз.`);
      message.setAttribute("role", "alert");
      form.insertAdjacentElement("afterend", message);
    } finally {
      submit.disabled = false;
      submit.textContent = "Спросить";
    }
  });
  content.append(form);
}
