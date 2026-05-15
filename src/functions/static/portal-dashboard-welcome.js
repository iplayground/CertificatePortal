const welcomeAccountDisplay = document.getElementById("welcome-account-display");
const welcomeMetricOverview = document.getElementById("welcome-metric-overview");
const welcomeMetricsApiPath = "/api/v1/admin/dashboard/welcome-metrics";

function ensureWelcomeAccountDisplay() {
  if (!welcomeAccountDisplay) {
    return;
  }

  if (!welcomeAccountDisplay.textContent?.trim()) {
    welcomeAccountDisplay.textContent = "管理者";
  }
}

function formatMetricNumber(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return "0";
  }

  return new Intl.NumberFormat("zh-TW").format(Math.trunc(numericValue));
}

function updateMetricValue(fieldName, value) {
  const metricElement = document.querySelector(`[data-metric-field="${fieldName}"]`);
  if (!metricElement) {
    return;
  }

  metricElement.textContent = formatMetricNumber(value);
  metricElement.classList.remove("is-loading");
}

function markMetricsUnavailable() {
  document.querySelectorAll("[data-metric-field]").forEach((metricElement) => {
    metricElement.textContent = "-";
    metricElement.classList.remove("is-loading");
  });
  welcomeMetricOverview?.setAttribute("aria-busy", "false");
}

async function loadWelcomeMetrics() {
  if (!welcomeMetricOverview) {
    return;
  }

  try {
    const response = await fetch(welcomeMetricsApiPath, {
      headers: {
        Accept: "application/json",
      },
    });

    if (response.status === 401) {
      const targetWindow = window.top && window.top !== window ? window.top : window;
      targetWindow.location.assign("/portal");
      return;
    }

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.error?.message || "welcome metrics unavailable");
    }

    const completionMetrics = payload?.completionCertMetrics ?? {};
    updateMetricValue("completion.downloadableCount", completionMetrics.downloadableCount);
    updateMetricValue("completion.downloadCount", completionMetrics.downloadCount);
    updateMetricValue("completion.verificationCount", completionMetrics.verificationCount);
    updateMetricValue("completion.pendingCount", completionMetrics.pendingCount);
    welcomeMetricOverview.setAttribute("aria-busy", "false");
  } catch (error) {
    void error;
    markMetricsUnavailable();
  }
}

ensureWelcomeAccountDisplay();
loadWelcomeMetrics();
