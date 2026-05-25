const completionReviewRefreshButton = document.getElementById("completion-review-refresh");
const completionReviewStatusButtons = Array.from(
  document.querySelectorAll(".completion-review-status-option")
);
const completionReviewTableBody = document.getElementById("completion-review-table-body");
const completionReviewEmptyRow = document.getElementById("completion-review-empty-row");
const completionReviewRowTemplate = document.getElementById("completion-review-row-template");
const completionReviewCompletedOnlyCells = Array.from(
  document.querySelectorAll("[data-completed-only]")
);
const completionReviewPendingOnlyCells = Array.from(
  document.querySelectorAll("[data-pending-only]")
);
const completionReviewDialog = document.getElementById("completion-review-dialog");
const completionReviewDialogTitle = document.getElementById("completion-review-dialog-title");
const completionReviewCancelButton = document.getElementById("completion-review-cancel");
const completionReviewApproveButton = document.getElementById("completion-review-approve");
const completionReviewCertificateTypeField = document.getElementById(
  "completion-review-certificate-type-field"
);
const completionReviewCertificateTypeInputs = Array.from(
  document.querySelectorAll('input[name="completionReviewCertificateType"]')
);
const completionReviewRejectButton = document.getElementById("completion-review-reject");
const completionReviewEventName = document.getElementById("completion-review-event-name");
const completionReviewNumber = document.getElementById("completion-review-number");
const completionReviewKktixId = document.getElementById("completion-review-kktix-id");
const completionReviewTicketName = document.getElementById("completion-review-ticket-name");
const completionReviewCreatedAtField = document.getElementById("completion-review-created-at-field");
const completionReviewCreatedAt = document.getElementById("completion-review-created-at");
const completionReviewRequesterNote = document.getElementById("completion-review-requester-note");
const completionReviewName = document.getElementById("completion-review-name");
const completionReviewOrganization = document.getElementById("completion-review-organization");
const completionReviewEmail = document.getElementById("completion-review-email");
const completionReviewServiceStartDate = document.getElementById(
  "completion-review-service-start-date"
);
const completionReviewServiceEndDate = document.getElementById(
  "completion-review-service-end-date"
);
const completionReviewServiceHours = document.getElementById("completion-review-service-hours");
const completionReviewVolunteerFields = document.getElementById(
  "completion-review-volunteer-fields"
);
const completionReviewNote = document.getElementById("completion-review-note");
const completionReviewCompletedSummary = document.getElementById("completion-review-completed-summary");
const completionReviewCompletedStatus = document.getElementById("completion-review-completed-status");
const completionReviewFeedback = document.getElementById("completion-review-feedback");
const adminCompletionChangeRequestsApiPath = "/api/v1/admin/completion-cert-change-requests";
const portalCsrfToken = document.body?.dataset.portalCsrfToken || "";
const loadingCompletionReviewsMessage = "修改申請載入中...";
const emptyCompletionReviewsMessages = {
  completed: "目前沒有已完成審核的修改申請。",
  pending: "目前沒有待審核的修改申請。",
};
const portalEntryPath = "/portal";
const portalSessionStartedAtKey = "ipg:portal:session-started-at:v1";
const portalSessionMaxAgeMs = 8 * 60 * 60 * 1000;
const completionReviewStatusLabels = {
  approved: "已通過",
  cancelledByIssue: "已取消",
  pending: "待審核",
  rejected: "已駁回",
  transferred: "已轉移",
};
const {
  formatIsoDateInputValue,
  installDatePicker,
  normalizeDateInputValue,
} = window.iPlaygroundPortalDateTime || {};

let completionReviewRows = [];
let selectedCompletionReviewStatus = "pending";
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
    eventName: typeof rowData?.eventName === "string" ? rowData.eventName : "",
    id: typeof rowData?.id === "string" ? rowData.id : "",
    requesterEmail:
      typeof rowData?.requesterEmail === "string" ? rowData.requesterEmail : "",
    requesterNote:
      typeof rowData?.requesterNote === "string" ? rowData.requesterNote : "",
    reviewedAt: typeof rowData?.reviewedAt === "string" ? rowData.reviewedAt : "",
    reviewedBy: typeof rowData?.reviewedBy === "string" ? rowData.reviewedBy : "",
    reviewNote: typeof rowData?.reviewNote === "string" ? rowData.reviewNote : "",
    status: typeof rowData?.status === "string" ? rowData.status : "pending",
    volunteerServiceDefaults:
      rowData?.volunteerServiceDefaults && typeof rowData.volunteerServiceDefaults === "object"
        ? {
            serviceEndDate:
              typeof rowData.volunteerServiceDefaults.serviceEndDate === "string"
                ? rowData.volunteerServiceDefaults.serviceEndDate
                : "",
            serviceHours:
              typeof rowData.volunteerServiceDefaults.serviceHours === "number" ||
              typeof rowData.volunteerServiceDefaults.serviceHours === "string"
                ? String(rowData.volunteerServiceDefaults.serviceHours)
                : "",
            serviceStartDate:
              typeof rowData.volunteerServiceDefaults.serviceStartDate === "string"
                ? rowData.volunteerServiceDefaults.serviceStartDate
                : "",
            volunteerServiceEligible: rowData.volunteerServiceDefaults.eligible === true,
          }
        : {
            serviceEndDate: "",
            serviceHours: "",
            serviceStartDate: "",
            volunteerServiceEligible: false,
          },
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

function getCompletionReviewStatusLabel(status) {
  return completionReviewStatusLabels[status] || status || "-";
}

function renderCompletionReviewStatusFilter() {
  completionReviewStatusButtons.forEach((button) => {
    if (!(button instanceof HTMLButtonElement)) {
      return;
    }

    const isActive = button.dataset.status === selectedCompletionReviewStatus;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
    button.disabled = isLoadingCompletionReviews || isSubmittingCompletionReview;
  });
}

function renderCompletionReviewRows() {
  if (
    !completionReviewTableBody ||
    !(completionReviewRowTemplate instanceof HTMLTemplateElement)
  ) {
    return;
  }

  const isCompletedReviewList = selectedCompletionReviewStatus === "completed";
  completionReviewCompletedOnlyCells.forEach((element) => {
    if (element instanceof HTMLElement || element instanceof HTMLTableColElement) {
      element.hidden = !isCompletedReviewList;
    }
  });
  completionReviewPendingOnlyCells.forEach((element) => {
    if (element instanceof HTMLElement || element instanceof HTMLTableColElement) {
      element.hidden = isCompletedReviewList;
    }
  });

  completionReviewTableBody
    .querySelectorAll(".completion-review-row")
    .forEach((rowElement) => rowElement.remove());

  if (completionReviewEmptyRow instanceof HTMLTableRowElement) {
    completionReviewEmptyRow.hidden = completionReviewRows.length > 0;
    const emptyCell = completionReviewEmptyRow.querySelector("td");
    if (emptyCell instanceof HTMLTableCellElement) {
      emptyCell.colSpan = isCompletedReviewList ? 7 : 6;
    }
    setCompletionReviewEmptyMessage(
      isLoadingCompletionReviews
        ? loadingCompletionReviewsMessage
        : emptyCompletionReviewsMessages[selectedCompletionReviewStatus] ||
            emptyCompletionReviewsMessages.pending
    );
  }
  renderCompletionReviewStatusFilter();

  completionReviewRows.forEach((rowData) => {
    const rowFragment = completionReviewRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".completion-review-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    rowElement.querySelectorAll("[data-completed-only]").forEach((element) => {
      if (element instanceof HTMLElement) {
        element.hidden = !isCompletedReviewList;
      }
    });
    rowElement.querySelectorAll("[data-pending-only]").forEach((element) => {
      if (element instanceof HTMLElement) {
        element.hidden = isCompletedReviewList;
      }
    });
    setTextContent(rowElement, '[data-field="createdAt"]', formatDisplayDateTime(rowData.createdAt));
    setTextContent(rowElement, '[data-field="reviewedAt"]', formatDisplayDateTime(rowData.reviewedAt));
    setTextContent(rowElement, '[data-field="status"]', getCompletionReviewStatusLabel(rowData.status));
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
      reviewButton.textContent = rowData.status === "pending" ? "審核" : "查看";
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
  const status = selectedCompletionReviewStatus;

  try {
    const response = await fetch(
      `${adminCompletionChangeRequestsApiPath}?status=${encodeURIComponent(status)}`,
      {
        headers: {
          Accept: "application/json",
        },
      }
    );
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "修改申請載入失敗。");
    }

    if (status === selectedCompletionReviewStatus) {
      completionReviewRows = Array.isArray(responsePayload.changeRequests)
        ? responsePayload.changeRequests.map((row) => normalizeCompletionReview(row))
        : [];
    }
  } catch (error) {
    if (status === selectedCompletionReviewStatus) {
      completionReviewRows = [];
    }
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

function setDatePickerInputValue(element, value) {
  if (element instanceof HTMLInputElement) {
    element.value = value;
    element.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function setDisabledInput(element, isDisabled) {
  if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
    element.disabled = isDisabled;
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

function getSelectedCompletionReviewCertificateType() {
  const selectedInput = completionReviewCertificateTypeInputs.find(
    (input) => input instanceof HTMLInputElement && input.checked
  );
  return selectedInput instanceof HTMLInputElement
    ? selectedInput.value
    : "completionCert";
}

function setCompletionReviewCertificateType(value) {
  completionReviewCertificateTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.checked = input.value === value;
    }
  });
}

function setDisabledCertificateTypeInputs(isDisabled) {
  completionReviewCertificateTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.disabled = isDisabled;
    }
  });
}

function updateCompletionReviewCertificateTypeControls(isPendingReview, rowData = null) {
  const isVolunteerServiceEligible =
    rowData?.volunteerServiceDefaults?.volunteerServiceEligible === true ||
    rowData?.status === "transferred";
  if (!isVolunteerServiceEligible) {
    setCompletionReviewCertificateType("completionCert");
  }
  const isVolunteerService =
    getSelectedCompletionReviewCertificateType() === "volunteerServiceCert";
  setDisabledInput(completionReviewName, !isPendingReview);
  setDisabledInput(completionReviewOrganization, !isPendingReview);
  setDisabledInput(completionReviewServiceStartDate, !isPendingReview);
  setDisabledInput(completionReviewServiceEndDate, !isPendingReview);
  setDisabledInput(completionReviewServiceHours, !isPendingReview);
  setDisabledCertificateTypeInputs(!isPendingReview);
  if (completionReviewCertificateTypeField instanceof HTMLElement) {
    completionReviewCertificateTypeField.hidden = !isVolunteerServiceEligible;
  }
  if (completionReviewVolunteerFields instanceof HTMLElement) {
    completionReviewVolunteerFields.hidden = !isVolunteerServiceEligible || !isVolunteerService;
  }
  if (completionReviewApproveButton instanceof HTMLButtonElement) {
    completionReviewApproveButton.textContent = isVolunteerService
      ? "轉移並結案"
      : "通過並更新";
  }
}

function fillCompletionReviewVolunteerDefaults(rowData, { overwrite = false } = {}) {
  const defaults = rowData?.volunteerServiceDefaults;
  if (!defaults || typeof defaults !== "object") {
    return;
  }

  if (overwrite || !getInputValue(completionReviewServiceStartDate)) {
    setDatePickerInputValue(
      completionReviewServiceStartDate,
      normalizeReviewServiceDateInput(defaults.serviceStartDate)
    );
  }
  if (overwrite || !getInputValue(completionReviewServiceEndDate)) {
    setDatePickerInputValue(
      completionReviewServiceEndDate,
      normalizeReviewServiceDateInput(defaults.serviceEndDate)
    );
  }
  if (overwrite || !getInputValue(completionReviewServiceHours)) {
    setInputValue(completionReviewServiceHours, defaults.serviceHours);
  }
}

function normalizeReviewServiceDateInput(value) {
  return typeof normalizeDateInputValue === "function"
    ? normalizeDateInputValue(value)
    : value;
}

function formatReviewServiceDatePayload(value) {
  return typeof formatIsoDateInputValue === "function"
    ? formatIsoDateInputValue(value)
    : value;
}

async function openCompletionReviewDialog(rowData) {
  if (!completionReviewDialog || isSubmittingCompletionReview) {
    return;
  }

  if (!(await verifyPortalSession())) {
    return;
  }

  selectedCompletionReviewId = rowData.id;
  const isPendingReview = rowData.status === "pending";
  completionReviewPreviousFocus = document.activeElement;
  clearCompletionReviewFeedback();
  setStaticValue(completionReviewDialogTitle, isPendingReview ? "審核修改申請" : "查看審核結果");
  setStaticValue(completionReviewEventName, rowData.eventName || rowData.eventId);
  setStaticValue(completionReviewNumber, rowData.completionCert.number);
  setStaticValue(completionReviewKktixId, rowData.completionCert.kktixId);
  setStaticValue(completionReviewTicketName, rowData.completionCert.ticketName);
  setStaticValue(completionReviewCreatedAt, formatDisplayDateTime(rowData.createdAt));
  setStaticValue(completionReviewRequesterNote, rowData.requesterNote);
  setCompletionReviewCertificateType(
    rowData.status === "transferred" ? "volunteerServiceCert" : "completionCert"
  );
  setInputValue(completionReviewName, rowData.completionCert.name);
  setInputValue(completionReviewOrganization, rowData.completionCert.organization);
  setInputValue(completionReviewEmail, rowData.completionCert.email || rowData.requesterEmail);
  fillCompletionReviewVolunteerDefaults(rowData, { overwrite: true });
  setInputValue(completionReviewNote, isPendingReview ? "" : rowData.reviewNote);
  setDisabledInput(completionReviewEmail, !isPendingReview);
  setDisabledInput(completionReviewNote, !isPendingReview);
  updateCompletionReviewCertificateTypeControls(isPendingReview, rowData);
  [completionReviewApproveButton, completionReviewRejectButton].forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      button.hidden = !isPendingReview;
    }
  });
  if (completionReviewCompletedSummary instanceof HTMLElement) {
    completionReviewCompletedSummary.hidden = isPendingReview;
  }
  if (completionReviewCreatedAtField instanceof HTMLElement) {
    completionReviewCreatedAtField.hidden = isPendingReview;
  }
  if (completionReviewCancelButton instanceof HTMLButtonElement) {
    completionReviewCancelButton.textContent = isPendingReview ? "取消" : "關閉";
  }
  setStaticValue(
    completionReviewCompletedStatus,
    [
      getCompletionReviewStatusLabel(rowData.status),
      rowData.reviewedAt ? formatDisplayDateTime(rowData.reviewedAt) : "",
      rowData.reviewedBy || "",
    ].filter(Boolean).join(" / ")
  );

  completionReviewDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  if (isPendingReview) {
    completionReviewName?.focus();
  } else {
    completionReviewCancelButton?.focus();
  }
}

function closeCompletionReviewDialog() {
  if (!completionReviewDialog) {
    return;
  }

  completionReviewDialog.hidden = true;
  selectedCompletionReviewId = "";
  clearCompletionReviewFeedback();
  if (completionReviewCancelButton instanceof HTMLButtonElement) {
    completionReviewCancelButton.textContent = "取消";
  }
  setDisabledInput(completionReviewName, false);
  setDisabledInput(completionReviewOrganization, false);
  setDisabledInput(completionReviewEmail, false);
  setDisabledInput(completionReviewServiceStartDate, false);
  setDisabledInput(completionReviewServiceEndDate, false);
  setDisabledInput(completionReviewServiceHours, false);
  setDisabledInput(completionReviewNote, false);
  setInputValue(completionReviewServiceStartDate, "");
  setInputValue(completionReviewServiceEndDate, "");
  setInputValue(completionReviewServiceHours, "");
  setDisabledCertificateTypeInputs(false);
  setCompletionReviewCertificateType("completionCert");
  if (completionReviewVolunteerFields instanceof HTMLElement) {
    completionReviewVolunteerFields.hidden = true;
  }
  if (completionReviewApproveButton instanceof HTMLButtonElement) {
    completionReviewApproveButton.textContent = "通過並更新";
  }
  [completionReviewApproveButton, completionReviewRejectButton].forEach((button) => {
    if (button instanceof HTMLButtonElement) {
      button.hidden = false;
    }
  });
  document.body.classList.remove("has-event-dialog");

  if (completionReviewPreviousFocus instanceof HTMLElement) {
    completionReviewPreviousFocus.focus();
  }
}

function setCompletionReviewSubmitting(isSubmitting) {
  isSubmittingCompletionReview = isSubmitting;
  [
    completionReviewApproveButton,
    completionReviewRejectButton,
    completionReviewCancelButton,
    completionReviewRefreshButton,
  ].forEach(
    (button) => {
      if (button instanceof HTMLButtonElement) {
        button.disabled = isSubmitting;
      }
    }
  );
  renderCompletionReviewStatusFilter();
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
  if (status === "transferred") {
    payload.name = getInputValue(completionReviewName);
    payload.organization = getInputValue(completionReviewOrganization);
    payload.serviceStartDate = formatReviewServiceDatePayload(
      getInputValue(completionReviewServiceStartDate)
    );
    payload.serviceEndDate = formatReviewServiceDatePayload(
      getInputValue(completionReviewServiceEndDate)
    );
    payload.serviceHours = getInputValue(completionReviewServiceHours);
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
    const successMessage =
      status === "approved"
        ? "修改申請已通過並更新資料。"
        : status === "transferred"
          ? "資料已轉移到志工服務證明。"
          : "修改申請已駁回。";
    showCompletionReviewPageAlert({
      message: successMessage,
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

completionReviewStatusButtons.forEach((button) => {
  if (!(button instanceof HTMLButtonElement)) {
    return;
  }

  button.addEventListener("click", () => {
    const nextStatus = button.dataset.status || "pending";
    if (nextStatus === selectedCompletionReviewStatus || isLoadingCompletionReviews) {
      return;
    }

    selectedCompletionReviewStatus = nextStatus;
    completionReviewRows = [];
    void loadCompletionReviews();
  });
});

completionReviewCancelButton?.addEventListener("click", closeCompletionReviewDialog);
completionReviewApproveButton?.addEventListener("click", () => {
  const certificateType = getSelectedCompletionReviewCertificateType();
  void submitCompletionReview(
    certificateType === "volunteerServiceCert" ? "transferred" : "approved"
  );
});
completionReviewRejectButton?.addEventListener("click", () => {
  void submitCompletionReview("rejected");
});

completionReviewCertificateTypeInputs.forEach((input) => {
  if (input instanceof HTMLInputElement) {
    input.addEventListener("change", () => {
      const rowData = getCompletionReviewRow(selectedCompletionReviewId);
      if (input.checked && input.value === "volunteerServiceCert") {
        fillCompletionReviewVolunteerDefaults(rowData);
      }
      updateCompletionReviewCertificateTypeControls(rowData?.status === "pending", rowData);
    });
  }
});

if (typeof installDatePicker === "function") {
  installDatePicker(completionReviewServiceStartDate);
  installDatePicker(completionReviewServiceEndDate);
}

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
