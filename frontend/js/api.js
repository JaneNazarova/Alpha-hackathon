async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { Accept: "application/json", ...options.headers },
  });

  if (!response.ok) {
    let message = `Сервис вернул ошибку ${response.status}.`;
    try {
      const body = await response.json();
      message = body.detail?.message || body.error?.message || body.detail || body.error?.code || message;
      if (typeof message !== "string") message = JSON.stringify(message);
    } catch {
      // Keep the HTTP status message when the server response is not JSON.
    }
    if (response.status === 403) {
      message = "Обновление защищено токеном. Выполните запрос через Swagger UI или настройте NEWS_REFRESH_TOKEN.";
    }
    throw new Error(message);
  }

  return response.json();
}

export const getCompanies = (query = "") => {
  const params = new URLSearchParams({ limit: "100" });
  if (query) params.set("q", query);
  return request(`/api/companies?${params.toString()}`);
};

export const getCompany = (companyId, role) => request(
  `/api/companies/${encodeURIComponent(companyId)}?role=${encodeURIComponent(role)}`,
);

export const getFeed = (companyId, role, weights = null) => {
  const params = new URLSearchParams({ company_id: companyId, role });
  if (weights) params.set("weights", JSON.stringify(weights));
  return request(`/api/feed?${params.toString()}`);
};

export const getMlQuality = () => request("/api/ml/quality");

export const refreshNews = () => request("/api/news/refresh", { method: "POST" });

export const createInsight = (companyId, articleId, role) => request("/api/insights", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ company_id: companyId, article_id: articleId, user_role: role }),
});

export const askQuestion = (insightId, question) => request(
  `/api/insights/${encodeURIComponent(insightId)}/questions`,
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  },
);
