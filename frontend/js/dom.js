export function makeElement(tag, className = "", text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null && text !== undefined) node.textContent = text;
  return node;
}

export function setText(selector, value, fallback = "—") {
  const node = document.querySelector(selector);
  if (node) node.textContent = value ?? fallback;
}

export function formatDate(value) {
  if (!value) return "Дата не указана";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Дата не указана";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric", month: "long", year: "numeric",
  }).format(date);
}

export function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "Нет данных";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(number)} ₽`;
}

export function formatPaymentAmount(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "Нет данных";
  return formatMoney(value);
}

export function safeExternalUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
