const welcomeAccountDisplay = document.getElementById("welcome-account-display");
const welcomeMetricOverview = document.getElementById("welcome-metric-overview");
const welcomeMetricSource = document.getElementById("welcome-metric-source");
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
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return "0";
  }

  return new Intl.NumberFormat("zh-TW").format(Math.trunc(numericValue));
}

function formatMetricCurrency(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return "$0";
  }

  return `$${new Intl.NumberFormat("zh-TW").format(Math.trunc(numericValue))}`;
}

function updateMetricValue(fieldName, value, formatter = formatMetricNumber) {
  const metricElement = document.querySelector(`[data-metric-field="${fieldName}"]`);
  if (!metricElement) {
    return;
  }

  metricElement.textContent = formatter(value);
  metricElement.classList.remove("is-loading");
}

function markMetricsUnavailable() {
  document.querySelectorAll("[data-metric-field]").forEach((metricElement) => {
    metricElement.textContent = "--";
    metricElement.classList.remove("is-loading");
  });
  if (welcomeMetricSource) {
    welcomeMetricSource.textContent = "資料來源：--";
  }
  welcomeMetricOverview?.setAttribute("aria-busy", "false");
}

function normalizeEventName(value) {
  return typeof value === "string" ? value.trim() : "";
}

function updateMetricSource(completionMetrics, taxReceiptMetrics) {
  if (!welcomeMetricSource) {
    return;
  }

  const completionEventName = normalizeEventName(completionMetrics?.eventName);
  const taxReceiptEventName = normalizeEventName(taxReceiptMetrics?.eventName);
  if (completionEventName && taxReceiptEventName) {
    welcomeMetricSource.textContent =
      completionEventName === taxReceiptEventName
        ? `資料來源：${completionEventName}`
        : `資料來源：完訓證明 ${completionEventName}；營業稅繳稅證明 ${taxReceiptEventName}`;
    return;
  }

  if (completionEventName) {
    welcomeMetricSource.textContent = `資料來源：完訓證明 ${completionEventName}`;
    return;
  }

  if (taxReceiptEventName) {
    welcomeMetricSource.textContent = `資料來源：營業稅繳稅證明 ${taxReceiptEventName}`;
    return;
  }

  welcomeMetricSource.textContent = "資料來源：--";
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
    updateMetricValue("completion.totalCount", completionMetrics.totalCount);
    updateMetricValue("completion.downloadCount", completionMetrics.downloadCount);
    updateMetricValue("completion.verificationCount", completionMetrics.verificationCount);
    updateMetricValue("completion.pendingCount", completionMetrics.pendingCount);

    const taxReceiptMetrics = payload?.taxReceiptMetrics ?? {};
    updateMetricValue("taxReceipt.receiptCount", taxReceiptMetrics.receiptCount);
    updateMetricValue(
      "taxReceipt.queriedCompanyCount",
      taxReceiptMetrics.queriedCompanyCount
    );
    updateMetricValue("taxReceipt.downloadCount", taxReceiptMetrics.downloadCount);
    updateMetricValue(
      "taxReceipt.totalAmount",
      taxReceiptMetrics.totalAmount,
      formatMetricCurrency
    );
    updateMetricSource(completionMetrics, taxReceiptMetrics);
    welcomeMetricOverview.setAttribute("aria-busy", "false");
  } catch (error) {
    void error;
    markMetricsUnavailable();
  }
}

ensureWelcomeAccountDisplay();
loadWelcomeMetrics();
