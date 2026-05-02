const completionReviewRefreshButton = document.getElementById("completion-review-refresh");
const completionReviewTableBody = document.getElementById("completion-review-table-body");
const completionReviewEmptyRow = document.getElementById("completion-review-empty-row");
const completionReviewRowTemplate = document.getElementById("completion-review-row-template");
const completionReviewDialog = document.getElementById("completion-review-dialog");
const completionReviewCancelButton = document.getElementById("completion-review-cancel");
const completionReviewApproveButton = document.getElementById("completion-review-approve");
const completionReviewRejectButton = document.getElementById("completion-review-reject");
const completionReviewNumber = document.getElementById("completion-review-number");
const completionReviewKktixId = document.getElementById("completion-review-kktix-id");
const completionReviewTicketName = document.getElementById("completion-review-ticket-name");
const completionReviewRequesterNote = document.getElementById("completion-review-requester-note");
const completionReviewName = document.getElementById("completion-review-name");
const completionReviewOrganization = document.getElementById("completion-review-organization");
const completionReviewEmail = document.getElementById("completion-review-email");
const completionReviewNote = document.getElementById("completion-review-note");
const completionReviewFeedback = document.getElementById("completion-review-feedback");
const adminCompletionChangeRequestsApiPath = "/api/v1/admin/completion-cert-change-requests";
const portalCsrfToken = document.body?.dataset.portalCsrfToken || "";
const loadingCompletionReviewsMessage = "修改申請載入中...";
const emptyCompletionReviewsMessage = "目前沒有待審核的修改申請。";
const portalEntryPath = "/portal";
const portalSessionStartedAtKey = "ipg:portal:session-started-at:v1";
const portalSessionMaxAgeMs = 8 * 60 * 60 * 1000;

let completionReviewRows = [];
let selectedCompletionReviewId = "";
let completionReviewPreviousFocus = null;
let isLoadingCompletionReviews = true;
let isSubmittingCompletionReview = false;

function redirectToPortalEntry() {
  const targetWindow = window.top && window.top !== window ? window.top : window;
  targetWindow.location.assign(portalEntryPath);
}

function handlePortalUnauthorizedResponse(response) {
  if (response.status !== 401) {
    return false;
  }

  redirectToPortalEntry();
  return true;
}

async function verifyPortalSession() {
  let startedAt = 0;
  try {
    startedAt = Number.parseInt(
      window.sessionStorage.getItem(portalSessionStartedAtKey) ?? "",
      10
    );
  } catch (error) {
    void error;
  }

  if (!Number.isFinite(startedAt) || startedAt <= 0) {
    try {
      window.sessionStorage.setItem(portalSessionStartedAtKey, String(Date.now()));
    } catch (error) {
      void error;
    }
    return true;
  }

  if (Date.now() - startedAt >= portalSessionMaxAgeMs) {
    redirectToPortalEntry();
    return false;
  }

  return true;
}

function setTextContent(parent, selector, value) {
  const element = parent.querySelector(selector);
  if (element) {
    element.textContent = value || "-";
  }
}

function normalizeCompletionReview(rowData) {
  const completionCert =
    rowData?.completionCert && typeof rowData.completionCert === "object"
      ? rowData.completionCert
      : {};

  return {
    completionCert: {
      email: typeof completionCert.email === "string" ? completionCert.email : "",
      eventId: typeof completionCert.eventId === "string" ? completionCert.eventId : "",
      id: typeof completionCert.id === "string" ? completionCert.id : "",
      kktixId: typeof completionCert.kktixId === "string" ? completionCert.kktixId : "",
      name: typeof completionCert.name === "string" ? completionCert.name : "",
      number:
        typeof completionCert.number === "number" || typeof completionCert.number === "string"
          ? String(completionCert.number)
          : "",
      organization:
        typeof completionCert.organization === "string" ? completionCert.organization : "",
      ticketName:
        typeof completionCert.ticketName === "string" ? completionCert.ticketName : "",
    },
    completionCertId:
      typeof rowData?.completionCertId === "string" ? rowData.completionCertId : "",
    createdAt: typeof rowData?.createdAt === "string" ? rowData.createdAt : "",
    eventId: typeof rowData?.eventId === "string" ? rowData.eventId : "",
    id: typeof rowData?.id === "string" ? rowData.id : "",
    requesterEmail:
      typeof rowData?.requesterEmail === "string" ? rowData.requesterEmail : "",
    requesterNote:
      typeof rowData?.requesterNote === "string" ? rowData.requesterNote : "",
    status: typeof rowData?.status === "string" ? rowData.status : "pending",
  };
}

function formatDisplayDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value || "-";
  }

  const parts = new Intl.DateTimeFormat("zh-TW", {
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
    minute: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Taipei",
    year: "numeric",
  }).formatToParts(date);
  const partValue = (type) => parts.find((part) => part.type === type)?.value ?? "";
  return `${partValue("year")} / ${partValue("month")} / ${partValue("day")} ${partValue("hour")}:${partValue("minute")}`;
}

function setCompletionReviewEmptyMessage(message) {
  const emptyCell = completionReviewEmptyRow?.querySelector("td");
  if (emptyCell) {
    emptyCell.textContent = message;
  }
}

function renderCompletionReviewRows() {
  if (
    !completionReviewTableBody ||
    !(completionReviewRowTemplate instanceof HTMLTemplateElement)
  ) {
    return;
  }

  completionReviewTableBody
    .querySelectorAll(".completion-review-row")
    .forEach((rowElement) => rowElement.remove());

  if (completionReviewEmptyRow instanceof HTMLTableRowElement) {
    completionReviewEmptyRow.hidden = completionReviewRows.length > 0;
    setCompletionReviewEmptyMessage(
      isLoadingCompletionReviews
        ? loadingCompletionReviewsMessage
        : emptyCompletionReviewsMessage
    );
  }

  completionReviewRows.forEach((rowData) => {
    const rowFragment = completionReviewRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".completion-review-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    setTextContent(rowElement, '[data-field="createdAt"]', formatDisplayDateTime(rowData.createdAt));
    setTextContent(rowElement, '[data-field="number"]', rowData.completionCert.number);
    setTextContent(rowElement, '[data-field="name"]', rowData.completionCert.name);
    setTextContent(
      rowElement,
      '[data-field="email"]',
      rowData.completionCert.email || rowData.requesterEmail
    );
    setTextContent(rowElement, '[data-field="requesterNote"]', rowData.requesterNote);

    const reviewButton = rowElement.querySelector(".document-edit-button");
    if (reviewButton instanceof HTMLButtonElement) {
      reviewButton.disabled = isSubmittingCompletionReview;
      reviewButton.addEventListener("click", () => {
        void openCompletionReviewDialog(rowData);
      });
    }

    completionReviewTableBody.append(rowElement);
  });
}

function showCompletionReviewPageAlert({ dismissDelay = 6000, message, title, tone }) {
  window.iPlaygroundPageAlert?.show({
    dismissDelay,
    message,
    title,
    tone,
  });
}

async function loadCompletionReviews() {
  isLoadingCompletionReviews = true;
  renderCompletionReviewRows();

  try {
    const response = await fetch(`${adminCompletionChangeRequestsApiPath}?status=pending`, {
      headers: {
        Accept: "application/json",
      },
    });
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "修改申請載入失敗。");
    }

    completionReviewRows = Array.isArray(responsePayload.changeRequests)
      ? responsePayload.changeRequests.map((row) => normalizeCompletionReview(row))
      : [];
  } catch (error) {
    completionReviewRows = [];
    showCompletionReviewPageAlert({
      message: error instanceof Error ? error.message : "修改申請載入失敗。",
      title: "載入失敗",
      tone: "error",
    });
  } finally {
    isLoadingCompletionReviews = false;
    renderCompletionReviewRows();
  }
}

function getCompletionReviewRow(rowId) {
  return completionReviewRows.find((row) => row.id === rowId) || null;
}

function clearCompletionReviewFeedback() {
  if (!(completionReviewFeedback instanceof HTMLElement)) {
    return;
  }

  completionReviewFeedback.textContent = "";
  completionReviewFeedback.hidden = true;
}

function showCompletionReviewFeedback(message) {
  if (!(completionReviewFeedback instanceof HTMLElement)) {
    return;
  }

  completionReviewFeedback.textContent = message;
  completionReviewFeedback.hidden = false;
}

function setInputValue(element, value) {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    element.value = value;
  }
}

function getInputValue(element) {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    return element.value.trim();
  }

  return "";
}

function setStaticValue(element, value) {
  if (element instanceof HTMLElement) {
    element.textContent = value || "-";
  }
}

async function openCompletionReviewDialog(rowData) {
  if (!completionReviewDialog || isSubmittingCompletionReview) {
    return;
  }

  if (!(await verifyPortalSession())) {
    return;
  }

  selectedCompletionReviewId = rowData.id;
  completionReviewPreviousFocus = document.activeElement;
  clearCompletionReviewFeedback();
  setStaticValue(completionReviewNumber, rowData.completionCert.number);
  setStaticValue(completionReviewKktixId, rowData.completionCert.kktixId);
  setStaticValue(completionReviewTicketName, rowData.completionCert.ticketName);
  setStaticValue(completionReviewRequesterNote, rowData.requesterNote);
  setInputValue(completionReviewName, rowData.completionCert.name);
  setInputValue(completionReviewOrganization, rowData.completionCert.organization);
  setInputValue(completionReviewEmail, rowData.completionCert.email || rowData.requesterEmail);
  setInputValue(completionReviewNote, "");

  completionReviewDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  completionReviewName?.focus();
}

function closeCompletionReviewDialog() {
  if (!completionReviewDialog) {
    return;
  }

  completionReviewDialog.hidden = true;
  selectedCompletionReviewId = "";
  clearCompletionReviewFeedback();
  document.body.classList.remove("has-event-dialog");

  if (completionReviewPreviousFocus instanceof HTMLElement) {
    completionReviewPreviousFocus.focus();
  }
}

function setCompletionReviewSubmitting(isSubmitting) {
  isSubmittingCompletionReview = isSubmitting;
  [completionReviewApproveButton, completionReviewRejectButton, completionReviewCancelButton, completionReviewRefreshButton].forEach(
    (button) => {
      if (button instanceof HTMLButtonElement) {
        button.disabled = isSubmitting;
      }
    }
  );
  renderCompletionReviewRows();
}

async function submitCompletionReview(status) {
  const rowData = getCompletionReviewRow(selectedCompletionReviewId);
  if (!rowData) {
    showCompletionReviewFeedback("找不到要審核的修改申請。");
    return;
  }

  const payload = {
    eventId: rowData.eventId,
    reviewNote: getInputValue(completionReviewNote),
    status,
  };
  if (status === "approved") {
    payload.name = getInputValue(completionReviewName);
    payload.organization = getInputValue(completionReviewOrganization);
  }

  setCompletionReviewSubmitting(true);
  clearCompletionReviewFeedback();
  try {
    const response = await fetch(
      `${adminCompletionChangeRequestsApiPath}/${encodeURIComponent(rowData.id)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Portal-CSRF-Token": portalCsrfToken,
        },
        body: JSON.stringify(payload),
      }
    );
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "修改申請審核失敗。");
    }

    completionReviewRows = completionReviewRows.filter((row) => row.id !== rowData.id);
    closeCompletionReviewDialog();
    renderCompletionReviewRows();
    showCompletionReviewPageAlert({
      message: status === "approved" ? "修改申請已通過並更新資料。" : "修改申請已駁回。",
      title: "審核完成",
      tone: "success",
    });
  } catch (error) {
    showCompletionReviewFeedback(
      error instanceof Error ? error.message : "修改申請審核失敗。"
    );
  } finally {
    setCompletionReviewSubmitting(false);
  }
}

completionReviewRefreshButton?.addEventListener("click", () => {
  void loadCompletionReviews();
});

completionReviewCancelButton?.addEventListener("click", closeCompletionReviewDialog);
completionReviewApproveButton?.addEventListener("click", () => {
  void submitCompletionReview("approved");
});
completionReviewRejectButton?.addEventListener("click", () => {
  void submitCompletionReview("rejected");
});

completionReviewDialog?.addEventListener("click", (event) => {
  if (event.target === completionReviewDialog && !isSubmittingCompletionReview) {
    closeCompletionReviewDialog();
  }
});

document.addEventListener("keydown", (event) => {
  if (
    event.key === "Escape" &&
    completionReviewDialog &&
    !completionReviewDialog.hidden &&
    !isSubmittingCompletionReview
  ) {
    closeCompletionReviewDialog();
  }
});

void loadCompletionReviews();
