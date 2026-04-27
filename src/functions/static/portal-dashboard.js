const portalPage = document.body;
const pageShell = document.querySelector(".page-shell");
const contentFrame = document.getElementById("admin-content-frame");
const logoutButton = document.getElementById("portal-logout");
const dashboardEventCreateDialog = document.getElementById("portal-event-create-dialog");
const dashboardEventCreateCancelButton = document.getElementById("portal-event-create-cancel");
const dashboardEventCreateTitle = document.getElementById("portal-event-create-title");
const dashboardEventFormSubmitButton = document.getElementById("portal-event-form-submit");
const dashboardEventNameInput = document.getElementById("portal-event-name-input");
const dashboardEventStatusCheckbox = document.getElementById("portal-event-status-checkbox");
const dashboardEventStatusText = document.getElementById("portal-event-status-text");
const dashboardEventCompletionDownloadStartsAtInput = document.getElementById(
  "portal-event-completion-download-starts-at"
);
const dashboardEventCompletionDownloadSetting = document.getElementById(
  "portal-event-completion-download-setting"
);
const dashboardEventCompletionDownloadToggle = document.querySelector(
  "#portal-event-completion-download-setting [data-completion-download-toggle]"
);
const dashboardEventCompletionDocumentTypeOption = document.querySelector(
  "#portal-event-create-dialog [data-completion-document-type-option]"
);
const dashboardEventDocumentTypeInputs = Array.from(
  document.querySelectorAll("#portal-event-create-dialog [data-document-type]")
);
const dashboardCompletionUploadDialog = document.getElementById(
  "portal-completion-upload-dialog"
);
const dashboardCompletionUploadCancelButton = document.getElementById(
  "portal-completion-upload-cancel"
);
const dashboardCompletionUploadSubmitButton = document.getElementById(
  "portal-completion-upload-submit"
);
const dashboardCompletionUploadFileInput = document.getElementById(
  "portal-completion-upload-file"
);
const dashboardCompletionUploadFileName = document.getElementById(
  "portal-completion-upload-file-name"
);
const dashboardCompletionUploadEvent = document.getElementById(
  "portal-completion-upload-event"
);
const dashboardCompletionUploadEventSelect = document.getElementById(
  "portal-completion-upload-event-select"
);
const dashboardCompletionUploadEventTrigger = document.getElementById(
  "portal-completion-upload-event-trigger"
);
const dashboardCompletionUploadEventValue = document.getElementById(
  "portal-completion-upload-event-value"
);
const dashboardCompletionUploadEventMenu = document.getElementById(
  "portal-completion-upload-event-options"
);
const dashboardCompletionUploadEventOptions = Array.from(
  document.querySelectorAll("#portal-completion-upload-event-options .custom-select-option")
);
const dashboardTaxUploadDialog = document.getElementById("portal-tax-upload-dialog");
const dashboardTaxUploadTitle = document.getElementById("portal-tax-upload-title");
const dashboardTaxUploadCancelButton = document.getElementById("portal-tax-upload-cancel");
const dashboardTaxUploadSubmitButton = document.getElementById("portal-tax-upload-submit");
const dashboardTaxUploadContinueOption = document.getElementById(
  "portal-tax-upload-continue-option"
);
const dashboardTaxUploadContinueInput = document.getElementById(
  "portal-tax-upload-continue"
);
const dashboardTaxUploadFileInput = document.getElementById("portal-tax-upload-file");
const dashboardTaxUploadFileName = document.getElementById("portal-tax-upload-file-name");
const dashboardTaxUploadTaxIdInput = document.getElementById("portal-tax-upload-tax-id");
const dashboardTaxUploadAmountInput = document.getElementById("portal-tax-upload-amount");
const dashboardTaxUploadGeneratedAtInput = document.getElementById(
  "portal-tax-upload-generated-at"
);
const dashboardTaxUploadEvent = document.getElementById("portal-tax-upload-event");
const dashboardTaxUploadEventSelect = document.getElementById(
  "portal-tax-upload-event-select"
);
const dashboardTaxUploadEventTrigger = document.getElementById(
  "portal-tax-upload-event-trigger"
);
const dashboardTaxUploadEventValue = document.getElementById("portal-tax-upload-event-value");
const dashboardTaxUploadEventMenu = document.getElementById("portal-tax-upload-event-options");
const dashboardTaxUploadEventOptions = Array.from(
  document.querySelectorAll("#portal-tax-upload-event-options .custom-select-option")
);

const portalEntryPath = portalPage.dataset.portalEntryPath ?? "/portal";
const logoutUrl =
  portalPage.dataset.logoutUrl ?? "/portal/auth/logout?post_logout_redirect_uri=/portal";
const welcomePagePath = portalPage.dataset.welcomePagePath ?? "/portal/dashboard/welcome";
const portalCsrfToken = portalPage.dataset.portalCsrfToken ?? "";
const adminEventsApiPath = "/api/v1/admin/events";
const eventFormOpenMessageType = "ipg:event-form:open";
const eventListRowBusyMessageType = "ipg:event-row:busy";
const eventListRowUpsertMessageType = "ipg:event-row:upsert";
const eventListRowRemoveMessageType = "ipg:event-row:remove";
const eventListAlertMessageType = "ipg:event-list:alert";
const completionUploadOpenMessageType = "ipg:completion-upload:open";
const completionUploadImportMessageType = "ipg:completion-upload:import";
const taxReceiptUploadOpenMessageType = "ipg:tax-receipt-upload:open";
const taxReceiptUploadImportMessageType = "ipg:tax-receipt-upload:import";
const defaultPageTitle = document.title;
const defaultDashboardCompletionUploadFileName = "尚未選擇 CSV 檔案";
const invalidDashboardCompletionUploadFileName = "請選擇 CSV 檔案";
const failedDashboardCompletionUploadFileName = "CSV 檔案讀取失敗";
const defaultDashboardCompletionUploadEventName = "";
const emptyDashboardCompletionUploadEventName = "尚無活動資料";
const defaultDashboardTaxUploadFileName = "尚未選擇 PDF 或圖檔";
const invalidDashboardTaxUploadFileName = "請選擇 PDF、PNG 或 JPG 檔案";
const failedDashboardTaxUploadFileName = "檔案讀取失敗";
const defaultDashboardTaxUploadEventName = "";
const emptyDashboardTaxUploadEventName = "尚無活動資料";
const dashboardTaxReceiptUploadExtensions = [".pdf", ".png", ".jpg", ".jpeg"];
const dashboardTaxReceiptUploadMimeTypes = [
  "application/pdf",
  "image/png",
  "image/jpeg",
];

const viewButtons = Array.from(document.querySelectorAll("[data-view-target]"));
let dashboardEventCreatePreviousFocus = null;
let dashboardEventDialogMode = "create";
let dashboardEventInitialState = "";
let dashboardEventEditingId = "";
let dashboardCompletionUploadPreviousFocus = null;
let dashboardTaxUploadPreviousFocus = null;
let dashboardTaxUploadDialogMode = "create";
let dashboardTaxUploadEditingRowId = "";
let dashboardTaxUploadCurrentFileName = "";

const {
  formatCurrentDateTimeInputValue,
  formatUtcIsoDateTimeInputValue,
  installDateTimePicker,
  normalizeDateTimeInputValue,
} = window.iPlaygroundPortalDateTime;

function setActiveView(targetView) {
  viewButtons.forEach((button) => {
    const isActive = button.dataset.viewTarget === targetView;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

function normaliseFramePath(value) {
  try {
    return new URL(value, window.location.origin).pathname;
  } catch (error) {
    void error;
    return welcomePagePath;
  }
}

function syncViewFromFrame() {
  const currentPath = normaliseFramePath(contentFrame.src || welcomePagePath);
  if (currentPath === portalEntryPath) {
    window.location.assign(portalEntryPath);
    return;
  }

  const matchingButton =
    viewButtons.find((button) => button.dataset.viewPath === currentPath) ??
    viewButtons.find((button) => button.dataset.viewTarget === "welcome");

  if (!matchingButton) {
    return;
  }

  setActiveView(matchingButton.dataset.viewTarget ?? "welcome");
}

function syncPageTitleFromFrame() {
  let nextTitle = defaultPageTitle;

  try {
    const frameDocument = contentFrame.contentDocument;
    nextTitle = frameDocument?.title?.trim() || defaultPageTitle;
  } catch (error) {
    void error;
  }

  document.title = nextTitle;
}

function activateView(targetView) {
  const targetButton =
    viewButtons.find((button) => button.dataset.viewTarget === targetView) ??
    viewButtons.find((button) => button.dataset.viewTarget === "welcome");

  if (!targetButton) {
    return;
  }

  contentFrame.src = targetButton.dataset.viewPath ?? welcomePagePath;
  setActiveView(targetButton.dataset.viewTarget ?? "welcome");
}

function resolveDashboardEventDocumentTypes(mode, eventData) {
  const configuredTypes = Array.isArray(eventData.documentTypes) ? eventData.documentTypes : [];
  if (configuredTypes.length > 0) {
    return configuredTypes;
  }

  return mode === "create" ? ["completionCert"] : [];
}

function applyDashboardEventStatusValue(nextValue) {
  const normalizedValue = nextValue === "unlisted" ? "unlisted" : "open";

  if (dashboardEventStatusCheckbox instanceof HTMLInputElement) {
    dashboardEventStatusCheckbox.checked = normalizedValue === "open";
  }

  if (dashboardEventStatusText) {
    dashboardEventStatusText.textContent = normalizedValue === "open" ? "開放" : "下架";
  }
}

function collectDashboardEventDialogState() {
  return JSON.stringify({
    name: dashboardEventNameInput instanceof HTMLInputElement ? dashboardEventNameInput.value : "",
    status:
      dashboardEventStatusCheckbox instanceof HTMLInputElement && dashboardEventStatusCheckbox.checked
        ? "open"
        : "unlisted",
    documentTypes: dashboardEventDocumentTypeInputs
      .filter((input) => input instanceof HTMLInputElement && input.checked)
      .map((input) => input.value),
    completionCertDownloadStartsAt:
      dashboardEventCompletionDownloadStartsAtInput instanceof HTMLInputElement
        ? formatUtcIsoDateTimeInputValue(dashboardEventCompletionDownloadStartsAtInput.value)
        : "",
  });
}

function collectDashboardEventDialogPayload() {
  return JSON.parse(collectDashboardEventDialogState());
}

function hasDashboardEventNameValue() {
  return (
    dashboardEventNameInput instanceof HTMLInputElement &&
    dashboardEventNameInput.value.trim().length > 0
  );
}

function updateDashboardEventFormSubmitState() {
  if (dashboardEventFormSubmitButton instanceof HTMLButtonElement) {
    dashboardEventFormSubmitButton.disabled = !hasDashboardEventNameValue();
  }
}

function getDashboardCompletionCertDocumentTypeInput() {
  return dashboardEventDocumentTypeInputs.find((input) => input.value === "completionCert");
}

function isDashboardCompletionCertEnabled() {
  const completionCertInput = getDashboardCompletionCertDocumentTypeInput();
  return completionCertInput instanceof HTMLInputElement && completionCertInput.checked;
}

function updateDashboardCompletionDownloadStartsAtVisibility() {
  const isVisible = isDashboardCompletionCertEnabled();

  if (dashboardEventCompletionDownloadSetting instanceof HTMLElement) {
    dashboardEventCompletionDownloadSetting.hidden = !isVisible;
  }

  if (!isVisible && dashboardEventCompletionDownloadStartsAtInput instanceof HTMLInputElement) {
    dashboardEventCompletionDownloadStartsAtInput.value = "";
    dashboardEventCompletionDownloadStartsAtInput.dispatchEvent(
      new Event("input", { bubbles: true })
    );
  }

  if (
    isVisible &&
    dashboardEventCompletionDownloadStartsAtInput instanceof HTMLInputElement &&
    dashboardEventCompletionDownloadStartsAtInput.value.trim() === ""
  ) {
    dashboardEventCompletionDownloadStartsAtInput.value = formatCurrentDateTimeInputValue();
    dashboardEventCompletionDownloadStartsAtInput.dispatchEvent(
      new Event("input", { bubbles: true })
    );
  }
}

function toggleDashboardCompletionCertDocumentType() {
  const completionCertInput = getDashboardCompletionCertDocumentTypeInput();

  if (!(completionCertInput instanceof HTMLInputElement)) {
    return;
  }

  completionCertInput.checked = !completionCertInput.checked;
  completionCertInput.dispatchEvent(new Event("change", { bubbles: true }));
}

function setDashboardEventDialogMode(mode = "create", eventData = {}) {
  const isEditMode = mode === "edit";
  const documentTypes = resolveDashboardEventDocumentTypes(mode, eventData);
  dashboardEventDialogMode = isEditMode ? "edit" : "create";
  dashboardEventEditingId = isEditMode && typeof eventData.id === "string" ? eventData.id : "";

  if (dashboardEventCreateTitle) {
    dashboardEventCreateTitle.textContent = isEditMode ? "編輯活動" : "建立活動";
  }

  if (dashboardEventFormSubmitButton) {
    dashboardEventFormSubmitButton.textContent = isEditMode ? "儲存變更" : "建立活動";
  }

  if (dashboardEventNameInput instanceof HTMLInputElement) {
    dashboardEventNameInput.value = eventData.name ?? "";
  }

  if (dashboardEventCompletionDownloadStartsAtInput instanceof HTMLInputElement) {
    dashboardEventCompletionDownloadStartsAtInput.value =
      normalizeDateTimeInputValue(eventData.completionCertDownloadStartsAt ?? "") ||
      formatCurrentDateTimeInputValue();
    dashboardEventCompletionDownloadStartsAtInput.dispatchEvent(
      new Event("input", { bubbles: true })
    );
  }

  updateDashboardEventFormSubmitState();

  applyDashboardEventStatusValue(eventData.status ?? (isEditMode ? "open" : "unlisted"));

  dashboardEventDocumentTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.checked = documentTypes.includes(input.value);
    }
  });

  updateDashboardCompletionDownloadStartsAtVisibility();
  dashboardEventInitialState = collectDashboardEventDialogState();
}

function openDashboardEventDialog({ mode = "create", eventData = {} } = {}) {
  if (!dashboardEventCreateDialog) {
    return;
  }

  setDashboardEventDialogMode(mode, eventData);
  dashboardEventCreatePreviousFocus = document.activeElement;
  dashboardEventCreateDialog.hidden = false;
  portalPage.classList.add("has-event-dialog");
  pageShell?.setAttribute("inert", "");
  pageShell?.setAttribute("aria-hidden", "true");
  dashboardEventNameInput?.focus();
}

function postEventListMessage(message) {
  if (!contentFrame?.contentWindow) {
    return;
  }

  contentFrame.contentWindow.postMessage(message, window.location.origin);
}

function shouldConfirmDashboardEventDialogClose() {
  if (!dashboardEventCreateDialog || dashboardEventCreateDialog.hidden) {
    return false;
  }

  if (dashboardEventDialogMode === "create") {
    return true;
  }

  return collectDashboardEventDialogState() !== dashboardEventInitialState;
}

function confirmDashboardEventDialogClose() {
  if (!shouldConfirmDashboardEventDialogClose()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function closeDashboardEventCreateDialog({ confirmUnsaved = false } = {}) {
  if (!dashboardEventCreateDialog) {
    return;
  }

  if (confirmUnsaved && !confirmDashboardEventDialogClose()) {
    return;
  }

  dashboardEventCreateDialog.hidden = true;
  portalPage.classList.remove("has-event-dialog");
  pageShell?.removeAttribute("inert");
  pageShell?.removeAttribute("aria-hidden");

  if (dashboardEventCreatePreviousFocus instanceof HTMLElement) {
    dashboardEventCreatePreviousFocus.focus();
  }
}

function buildDashboardIdempotencyKey() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildDashboardPendingEventId(idempotencyKey) {
  return `pending_${idempotencyKey.replaceAll("-", "_")}`;
}

async function submitDashboardEventForm() {
  if (!(dashboardEventFormSubmitButton instanceof HTMLButtonElement)) {
    return;
  }

  if (!hasDashboardEventNameValue()) {
    updateDashboardEventFormSubmitState();
    dashboardEventNameInput?.focus();
    return;
  }

  dashboardEventFormSubmitButton.disabled = true;
  const isEditMode = dashboardEventDialogMode === "edit";
  const idempotencyKey = isEditMode ? "" : buildDashboardIdempotencyKey();
  const pendingEventId = isEditMode ? "" : buildDashboardPendingEventId(idempotencyKey);
  try {
    const eventApiPath =
      isEditMode && dashboardEventEditingId
        ? `${adminEventsApiPath}/${encodeURIComponent(dashboardEventEditingId)}`
        : adminEventsApiPath;
    if (isEditMode) {
      closeDashboardEventCreateDialog();
      postEventListMessage({
        type: eventListRowBusyMessageType,
        eventId: dashboardEventEditingId,
        isBusy: true,
      });
    } else {
      postEventListMessage({
        type: eventListRowUpsertMessageType,
        replaceEventId: "",
        event: {
          ...collectDashboardEventDialogPayload(),
          id: pendingEventId,
        },
      });
      postEventListMessage({
        type: eventListRowBusyMessageType,
        eventId: pendingEventId,
        isBusy: true,
      });
      closeDashboardEventCreateDialog();
    }

    const response = await fetch(eventApiPath, {
      method: isEditMode ? "PUT" : "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Portal-CSRF-Token": portalCsrfToken,
        ...(isEditMode ? {} : { "Idempotency-Key": idempotencyKey }),
      },
      body: JSON.stringify(collectDashboardEventDialogPayload()),
    });
    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "建立活動失敗，請稍後再試。");
    }

    if (isEditMode) {
      postEventListMessage({
        type: eventListRowUpsertMessageType,
        event: responsePayload.event,
      });
      postEventListMessage({
        type: eventListAlertMessageType,
        title: "更新成功",
        message: "活動資料已更新。",
        tone: "success",
      });
    } else {
      postEventListMessage({
        type: eventListRowUpsertMessageType,
        replaceEventId: pendingEventId,
        event: responsePayload.event,
      });
      postEventListMessage({
        type: eventListAlertMessageType,
        title: "建立成功",
        message: "活動已建立。",
        tone: "success",
      });
    }
  } catch (error) {
    if (isEditMode) {
      postEventListMessage({
        type: eventListRowBusyMessageType,
        eventId: dashboardEventEditingId,
        isBusy: false,
      });
      postEventListMessage({
        type: eventListAlertMessageType,
        title: "儲存失敗",
        message: error instanceof Error ? error.message : "活動儲存失敗，請稍後再試。",
        tone: "error",
      });
    } else {
      postEventListMessage({
        type: eventListRowRemoveMessageType,
        eventId: pendingEventId,
      });
      postEventListMessage({
        type: eventListAlertMessageType,
        title: "建立失敗",
        message: error instanceof Error ? error.message : "建立活動失敗，請稍後再試。",
        tone: "error",
      });
    }
    updateDashboardEventFormSubmitState();
  }
}

function getCompletionEventNameFromFrame() {
  try {
    const frameEventFilter = contentFrame.contentDocument?.getElementById("completion-event-filter");
    if (frameEventFilter instanceof HTMLInputElement) {
      return frameEventFilter.value;
    }
  } catch (error) {
    void error;
  }

  return defaultDashboardCompletionUploadEventName;
}

function getDashboardCompletionUploadEventName() {
  if (dashboardCompletionUploadEvent instanceof HTMLInputElement) {
    return dashboardCompletionUploadEvent.value;
  }

  return defaultDashboardCompletionUploadEventName;
}

function applyDashboardCompletionUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultDashboardCompletionUploadEventName;

  if (dashboardCompletionUploadEvent instanceof HTMLInputElement) {
    dashboardCompletionUploadEvent.value = normalizedValue;
  }

  if (dashboardCompletionUploadEventValue) {
    dashboardCompletionUploadEventValue.textContent =
      normalizedValue || emptyDashboardCompletionUploadEventName;
  }

  dashboardCompletionUploadEventOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function resetDashboardCompletionUploadDialog() {
  if (dashboardCompletionUploadFileInput instanceof HTMLInputElement) {
    dashboardCompletionUploadFileInput.value = "";
  }

  applyDashboardCompletionUploadEventValue(getCompletionEventNameFromFrame());
  updateDashboardCompletionUploadFileName();
}

function hasSelectedDashboardCompletionUploadFile() {
  return (
    dashboardCompletionUploadFileInput instanceof HTMLInputElement &&
    dashboardCompletionUploadFileInput.files instanceof FileList &&
    dashboardCompletionUploadFileInput.files.length > 0
  );
}

function isDashboardCompletionCsvFile(file) {
  return file.name.toLowerCase().endsWith(".csv");
}

function updateDashboardCompletionUploadFileName() {
  if (!(dashboardCompletionUploadFileName instanceof HTMLElement)) {
    return;
  }

  if (
    !(dashboardCompletionUploadFileInput instanceof HTMLInputElement) ||
    !(dashboardCompletionUploadFileInput.files instanceof FileList) ||
    dashboardCompletionUploadFileInput.files.length === 0
  ) {
    dashboardCompletionUploadFileName.textContent = defaultDashboardCompletionUploadFileName;
    return;
  }

  const selectedFile = dashboardCompletionUploadFileInput.files[0];
  if (!isDashboardCompletionCsvFile(selectedFile)) {
    dashboardCompletionUploadFileInput.value = "";
    dashboardCompletionUploadFileName.textContent = invalidDashboardCompletionUploadFileName;
    return;
  }

  dashboardCompletionUploadFileName.textContent = selectedFile.name;
}

function getSelectedDashboardCompletionUploadFile() {
  if (
    !(dashboardCompletionUploadFileInput instanceof HTMLInputElement) ||
    !(dashboardCompletionUploadFileInput.files instanceof FileList) ||
    dashboardCompletionUploadFileInput.files.length === 0
  ) {
    return null;
  }

  return dashboardCompletionUploadFileInput.files[0];
}

async function sendDashboardCompletionUploadFileToFrame() {
  const selectedFile = getSelectedDashboardCompletionUploadFile();
  if (!selectedFile || !isDashboardCompletionCsvFile(selectedFile)) {
    updateDashboardCompletionUploadFileName();
    dashboardCompletionUploadFileInput?.focus();
    return;
  }

  try {
    const csvText = await selectedFile.text();
    contentFrame.contentWindow?.postMessage(
      {
        csvText,
        eventName: getDashboardCompletionUploadEventName(),
        fileName: selectedFile.name,
        type: completionUploadImportMessageType,
      },
      window.location.origin
    );
    closeDashboardCompletionUploadDialog();
  } catch (error) {
    void error;
    if (dashboardCompletionUploadFileName) {
      dashboardCompletionUploadFileName.textContent = failedDashboardCompletionUploadFileName;
    }
  }
}

function confirmDashboardCompletionUploadDialogClose() {
  if (!hasSelectedDashboardCompletionUploadFile()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function openDashboardCompletionUploadDialog() {
  if (!dashboardCompletionUploadDialog) {
    return;
  }

  resetDashboardCompletionUploadDialog();
  dashboardCompletionUploadPreviousFocus = document.activeElement;
  dashboardCompletionUploadDialog.hidden = false;
  portalPage.classList.add("has-event-dialog");
  pageShell?.setAttribute("inert", "");
  pageShell?.setAttribute("aria-hidden", "true");
  dashboardCompletionUploadFileInput?.focus();
}

function closeDashboardCompletionUploadDialog({ confirmUnsaved = false } = {}) {
  if (!dashboardCompletionUploadDialog) {
    return;
  }

  if (confirmUnsaved && !confirmDashboardCompletionUploadDialogClose()) {
    return;
  }

  dashboardCompletionUploadDialog.hidden = true;
  closeDashboardCompletionUploadEventSelect();
  portalPage.classList.remove("has-event-dialog");
  pageShell?.removeAttribute("inert");
  pageShell?.removeAttribute("aria-hidden");

  if (dashboardCompletionUploadPreviousFocus instanceof HTMLElement) {
    dashboardCompletionUploadPreviousFocus.focus();
  }
}

function closeDashboardCompletionUploadEventSelect({ blurTrigger = false } = {}) {
  dashboardCompletionUploadEventSelect?.classList.remove("is-open");
  dashboardCompletionUploadEventTrigger?.setAttribute("aria-expanded", "false");

  if (dashboardCompletionUploadEventMenu) {
    dashboardCompletionUploadEventMenu.hidden = true;
  }

  if (blurTrigger) {
    dashboardCompletionUploadEventTrigger?.blur();
  }
}

function canOpenDashboardCompletionUploadEventSelect() {
  return dashboardCompletionUploadEventOptions.length > 1;
}

function openDashboardCompletionUploadEventSelect() {
  if (!canOpenDashboardCompletionUploadEventSelect()) {
    closeDashboardCompletionUploadEventSelect();
    return;
  }

  dashboardCompletionUploadEventSelect?.classList.add("is-open");
  dashboardCompletionUploadEventTrigger?.setAttribute("aria-expanded", "true");

  if (dashboardCompletionUploadEventMenu) {
    dashboardCompletionUploadEventMenu.hidden = false;
  }
}

function getTaxEventNameFromFrame() {
  try {
    const frameEventFilter = contentFrame.contentDocument?.getElementById("tax-event-filter");
    if (frameEventFilter instanceof HTMLInputElement) {
      return frameEventFilter.value;
    }
  } catch (error) {
    void error;
  }

  return defaultDashboardTaxUploadEventName;
}

function getDashboardTaxUploadEventName() {
  if (dashboardTaxUploadEvent instanceof HTMLInputElement) {
    return dashboardTaxUploadEvent.value;
  }

  return defaultDashboardTaxUploadEventName;
}

function applyDashboardTaxUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultDashboardTaxUploadEventName;

  if (dashboardTaxUploadEvent instanceof HTMLInputElement) {
    dashboardTaxUploadEvent.value = normalizedValue;
  }

  if (dashboardTaxUploadEventValue) {
    dashboardTaxUploadEventValue.textContent = normalizedValue || emptyDashboardTaxUploadEventName;
  }

  dashboardTaxUploadEventOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function setDashboardTaxUploadTextValue(input, value) {
  if (input instanceof HTMLInputElement) {
    input.value = value ?? "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function setDashboardTaxUploadDialogMode(mode = "create", receiptData = {}) {
  const isEditMode = mode === "edit";
  dashboardTaxUploadDialogMode = isEditMode ? "edit" : "create";
  dashboardTaxUploadEditingRowId = isEditMode ? receiptData.id ?? "" : "";
  dashboardTaxUploadCurrentFileName = isEditMode ? receiptData.fileName ?? "" : "";

  if (dashboardTaxUploadTitle) {
    dashboardTaxUploadTitle.textContent = isEditMode ? "修改繳稅證明" : "新增繳稅證明";
  }

  if (dashboardTaxUploadSubmitButton) {
    dashboardTaxUploadSubmitButton.textContent = isEditMode ? "儲存變更" : "新增繳稅證明";
  }

  if (dashboardTaxUploadContinueOption instanceof HTMLElement) {
    dashboardTaxUploadContinueOption.hidden = isEditMode;
  }

  if (dashboardTaxUploadContinueInput instanceof HTMLInputElement) {
    dashboardTaxUploadContinueInput.checked = false;
  }

  if (dashboardTaxUploadFileInput instanceof HTMLInputElement) {
    dashboardTaxUploadFileInput.value = "";
  }

  setDashboardTaxUploadTextValue(dashboardTaxUploadTaxIdInput, receiptData.taxId ?? "");
  setDashboardTaxUploadTextValue(dashboardTaxUploadAmountInput, receiptData.amount ?? "");
  setDashboardTaxUploadTextValue(
    dashboardTaxUploadGeneratedAtInput,
    normalizeDateTimeInputValue(receiptData.generatedAt ?? "") || formatCurrentDateTimeInputValue()
  );
  applyDashboardTaxUploadEventValue(receiptData.eventName ?? getTaxEventNameFromFrame());
  updateDashboardTaxUploadFileName();
}

function resetDashboardTaxUploadDialog() {
  setDashboardTaxUploadDialogMode("create");
}

function hasSelectedDashboardTaxUploadFile() {
  return (
    dashboardTaxUploadFileInput instanceof HTMLInputElement &&
    dashboardTaxUploadFileInput.files instanceof FileList &&
    dashboardTaxUploadFileInput.files.length > 0
  );
}

function hasDashboardTaxUploadDraft() {
  const hasTextValue = [
    dashboardTaxUploadTaxIdInput,
    dashboardTaxUploadAmountInput,
    dashboardTaxUploadGeneratedAtInput,
  ].some((input) => input instanceof HTMLInputElement && input.value.trim().length > 0);

  return hasTextValue || hasSelectedDashboardTaxUploadFile();
}

function isDashboardTaxReceiptUploadFile(file) {
  const normalizedName = file.name.toLowerCase();
  return (
    dashboardTaxReceiptUploadMimeTypes.includes(file.type) ||
    dashboardTaxReceiptUploadExtensions.some((extension) => normalizedName.endsWith(extension))
  );
}

function updateDashboardTaxUploadFileName() {
  if (!(dashboardTaxUploadFileName instanceof HTMLElement)) {
    return;
  }

  if (
    !(dashboardTaxUploadFileInput instanceof HTMLInputElement) ||
    !(dashboardTaxUploadFileInput.files instanceof FileList) ||
    dashboardTaxUploadFileInput.files.length === 0
  ) {
    dashboardTaxUploadFileName.textContent =
      dashboardTaxUploadCurrentFileName ||
      (dashboardTaxUploadDialogMode === "edit"
        ? "未重新選擇檔案"
        : defaultDashboardTaxUploadFileName);
    return;
  }

  const selectedFile = dashboardTaxUploadFileInput.files[0];
  if (!isDashboardTaxReceiptUploadFile(selectedFile)) {
    dashboardTaxUploadFileInput.value = "";
    dashboardTaxUploadFileName.textContent = invalidDashboardTaxUploadFileName;
    return;
  }

  dashboardTaxUploadFileName.textContent = selectedFile.name;
}

function getSelectedDashboardTaxUploadFile() {
  if (
    !(dashboardTaxUploadFileInput instanceof HTMLInputElement) ||
    !(dashboardTaxUploadFileInput.files instanceof FileList) ||
    dashboardTaxUploadFileInput.files.length === 0
  ) {
    return null;
  }

  return dashboardTaxUploadFileInput.files[0];
}

function getDashboardTaxUploadTextValue(input) {
  return input instanceof HTMLInputElement ? input.value.trim() : "";
}

function shouldContinueDashboardTaxUpload() {
  return (
    dashboardTaxUploadDialogMode === "create" &&
    dashboardTaxUploadContinueInput instanceof HTMLInputElement &&
    dashboardTaxUploadContinueInput.checked
  );
}

function resetDashboardTaxUploadFieldsForNextFile() {
  const eventName = getDashboardTaxUploadEventName();
  setDashboardTaxUploadDialogMode("create", { eventName });
  if (dashboardTaxUploadContinueInput instanceof HTMLInputElement) {
    dashboardTaxUploadContinueInput.checked = true;
  }
  dashboardTaxUploadTaxIdInput?.focus();
}

function sendDashboardTaxUploadFileToFrame() {
  const selectedFile = getSelectedDashboardTaxUploadFile();
  if (selectedFile && !isDashboardTaxReceiptUploadFile(selectedFile)) {
    updateDashboardTaxUploadFileName();
    dashboardTaxUploadFileInput?.focus();
    return;
  }

  if (dashboardTaxUploadDialogMode === "create" && !selectedFile) {
    updateDashboardTaxUploadFileName();
    dashboardTaxUploadFileInput?.focus();
    return;
  }

  try {
    const shouldKeepDialogOpen = shouldContinueDashboardTaxUpload();
    contentFrame.contentWindow?.postMessage(
      {
        amount: getDashboardTaxUploadTextValue(dashboardTaxUploadAmountInput),
        eventName: getDashboardTaxUploadEventName(),
        file: selectedFile ?? null,
        fileName: selectedFile?.name ?? dashboardTaxUploadCurrentFileName,
        generatedAt: formatUtcIsoDateTimeInputValue(
          getDashboardTaxUploadTextValue(dashboardTaxUploadGeneratedAtInput)
        ),
        rowId: dashboardTaxUploadEditingRowId,
        taxId: getDashboardTaxUploadTextValue(dashboardTaxUploadTaxIdInput),
        type: taxReceiptUploadImportMessageType,
      },
      window.location.origin
    );
    if (shouldKeepDialogOpen) {
      resetDashboardTaxUploadFieldsForNextFile();
      return;
    }
    closeDashboardTaxUploadDialog();
  } catch (error) {
    void error;
    if (dashboardTaxUploadFileName) {
      dashboardTaxUploadFileName.textContent = failedDashboardTaxUploadFileName;
    }
  }
}

function confirmDashboardTaxUploadDialogClose() {
  if (!hasDashboardTaxUploadDraft()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function openDashboardTaxUploadDialog({ mode = "create", receiptData = {} } = {}) {
  if (!dashboardTaxUploadDialog) {
    return;
  }

  if (mode === "edit") {
    setDashboardTaxUploadDialogMode("edit", receiptData);
  } else {
    resetDashboardTaxUploadDialog();
  }

  dashboardTaxUploadPreviousFocus = document.activeElement;
  dashboardTaxUploadDialog.hidden = false;
  portalPage.classList.add("has-event-dialog");
  pageShell?.setAttribute("inert", "");
  pageShell?.setAttribute("aria-hidden", "true");
  dashboardTaxUploadTaxIdInput?.focus();
}

function closeDashboardTaxUploadDialog({ confirmUnsaved = false } = {}) {
  if (!dashboardTaxUploadDialog) {
    return;
  }

  if (confirmUnsaved && !confirmDashboardTaxUploadDialogClose()) {
    return;
  }

  dashboardTaxUploadDialog.hidden = true;
  closeDashboardTaxUploadEventSelect();
  portalPage.classList.remove("has-event-dialog");
  pageShell?.removeAttribute("inert");
  pageShell?.removeAttribute("aria-hidden");

  if (dashboardTaxUploadPreviousFocus instanceof HTMLElement) {
    dashboardTaxUploadPreviousFocus.focus();
  }
}

function closeDashboardTaxUploadEventSelect({ blurTrigger = false } = {}) {
  dashboardTaxUploadEventSelect?.classList.remove("is-open");
  dashboardTaxUploadEventTrigger?.setAttribute("aria-expanded", "false");

  if (dashboardTaxUploadEventMenu) {
    dashboardTaxUploadEventMenu.hidden = true;
  }

  if (blurTrigger) {
    dashboardTaxUploadEventTrigger?.blur();
  }
}

function canOpenDashboardTaxUploadEventSelect() {
  return dashboardTaxUploadEventOptions.length > 1;
}

function openDashboardTaxUploadEventSelect() {
  if (!canOpenDashboardTaxUploadEventSelect()) {
    closeDashboardTaxUploadEventSelect();
    return;
  }

  dashboardTaxUploadEventSelect?.classList.add("is-open");
  dashboardTaxUploadEventTrigger?.setAttribute("aria-expanded", "true");

  if (dashboardTaxUploadEventMenu) {
    dashboardTaxUploadEventMenu.hidden = false;
  }
}

viewButtons.forEach((button) => {
  button.addEventListener("click", () => {
    activateView(button.dataset.viewTarget ?? "welcome");
  });
});

contentFrame.addEventListener("load", () => {
  syncViewFromFrame();
  syncPageTitleFromFrame();
});

logoutButton.addEventListener("click", () => {
  window.location.assign(logoutUrl);
});

dashboardEventCreateCancelButton?.addEventListener("click", () => {
  closeDashboardEventCreateDialog({ confirmUnsaved: true });
});

dashboardCompletionUploadCancelButton?.addEventListener("click", () => {
  closeDashboardCompletionUploadDialog({ confirmUnsaved: true });
});

dashboardCompletionUploadSubmitButton?.addEventListener("click", () => {
  void sendDashboardCompletionUploadFileToFrame();
});

dashboardTaxUploadCancelButton?.addEventListener("click", () => {
  closeDashboardTaxUploadDialog({ confirmUnsaved: true });
});

dashboardTaxUploadSubmitButton?.addEventListener("click", sendDashboardTaxUploadFileToFrame);

dashboardCompletionUploadEventTrigger?.addEventListener("click", () => {
  if (!canOpenDashboardCompletionUploadEventSelect()) {
    return;
  }

  if (dashboardCompletionUploadEventSelect?.classList.contains("is-open")) {
    closeDashboardCompletionUploadEventSelect({ blurTrigger: true });
    return;
  }

  openDashboardCompletionUploadEventSelect();
});

dashboardCompletionUploadEventTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!canOpenDashboardCompletionUploadEventSelect()) {
      return;
    }

    openDashboardCompletionUploadEventSelect();
    dashboardCompletionUploadEventOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeDashboardCompletionUploadEventSelect({ blurTrigger: true });
  }
});

dashboardCompletionUploadFileInput?.addEventListener(
  "change",
  updateDashboardCompletionUploadFileName
);

dashboardTaxUploadEventTrigger?.addEventListener("click", () => {
  if (!canOpenDashboardTaxUploadEventSelect()) {
    return;
  }

  if (dashboardTaxUploadEventSelect?.classList.contains("is-open")) {
    closeDashboardTaxUploadEventSelect({ blurTrigger: true });
    return;
  }

  openDashboardTaxUploadEventSelect();
});

dashboardTaxUploadEventTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!canOpenDashboardTaxUploadEventSelect()) {
      return;
    }

    openDashboardTaxUploadEventSelect();
    dashboardTaxUploadEventOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeDashboardTaxUploadEventSelect({ blurTrigger: true });
  }
});

dashboardTaxUploadFileInput?.addEventListener("change", updateDashboardTaxUploadFileName);

dashboardCompletionUploadEventOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyDashboardCompletionUploadEventValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeDashboardCompletionUploadEventSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDashboardCompletionUploadEventSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      dashboardCompletionUploadEventOptions[
        (index + 1) % dashboardCompletionUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      dashboardCompletionUploadEventOptions[
        (index - 1 + dashboardCompletionUploadEventOptions.length) %
          dashboardCompletionUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeDashboardCompletionUploadEventSelect();
    }
  });
});

dashboardTaxUploadEventOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyDashboardTaxUploadEventValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeDashboardTaxUploadEventSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDashboardTaxUploadEventSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      dashboardTaxUploadEventOptions[
        (index + 1) % dashboardTaxUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      dashboardTaxUploadEventOptions[
        (index - 1 + dashboardTaxUploadEventOptions.length) %
          dashboardTaxUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeDashboardTaxUploadEventSelect();
    }
  });
});

dashboardEventStatusCheckbox?.addEventListener("change", () => {
  applyDashboardEventStatusValue(dashboardEventStatusCheckbox.checked ? "open" : "unlisted");
});

dashboardEventFormSubmitButton?.addEventListener("click", () => {
  void submitDashboardEventForm();
});
dashboardEventNameInput?.addEventListener("input", updateDashboardEventFormSubmitState);
installDateTimePicker(dashboardEventCompletionDownloadStartsAtInput);
installDateTimePicker(dashboardTaxUploadGeneratedAtInput);

dashboardEventDocumentTypeInputs.forEach((input) => {
  input.addEventListener("change", updateDashboardCompletionDownloadStartsAtVisibility);
});

dashboardEventCompletionDownloadToggle?.addEventListener("click", () => {
  toggleDashboardCompletionCertDocumentType();
});

dashboardEventCompletionDownloadToggle?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  event.preventDefault();
  toggleDashboardCompletionCertDocumentType();
});

dashboardEventCompletionDocumentTypeOption?.addEventListener("click", (event) => {
  if (event.target !== dashboardEventCompletionDocumentTypeOption) {
    return;
  }

  toggleDashboardCompletionCertDocumentType();
});

dashboardEventCreateDialog?.addEventListener("click", (event) => {
  if (event.target === dashboardEventCreateDialog) {
    closeDashboardEventCreateDialog({ confirmUnsaved: true });
  }
});

dashboardCompletionUploadDialog?.addEventListener("click", (event) => {
  if (event.target === dashboardCompletionUploadDialog) {
    closeDashboardCompletionUploadDialog({ confirmUnsaved: true });
  }
});

dashboardTaxUploadDialog?.addEventListener("click", (event) => {
  if (event.target === dashboardTaxUploadDialog) {
    closeDashboardTaxUploadDialog({ confirmUnsaved: true });
  }
});

window.addEventListener("message", (event) => {
  const message = event.data;
  if (event.origin !== window.location.origin || typeof message !== "object" || message === null) {
    return;
  }

  if (message.type === eventFormOpenMessageType) {
    openDashboardEventDialog({
      mode: message.mode === "edit" ? "edit" : "create",
      eventData: message.event ?? {},
    });
    return;
  }

  if (message.type === completionUploadOpenMessageType) {
    openDashboardCompletionUploadDialog();
    return;
  }

  if (message.type === taxReceiptUploadOpenMessageType) {
    openDashboardTaxUploadDialog({
      mode: message.mode === "edit" ? "edit" : "create",
      receiptData: message.receipt ?? {},
    });
  }
});

document.addEventListener("click", (event) => {
  if (
    dashboardCompletionUploadEventSelect instanceof HTMLElement &&
    !dashboardCompletionUploadEventSelect.contains(event.target)
  ) {
    closeDashboardCompletionUploadEventSelect();
  }

  if (
    dashboardTaxUploadEventSelect instanceof HTMLElement &&
    !dashboardTaxUploadEventSelect.contains(event.target)
  ) {
    closeDashboardTaxUploadEventSelect();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dashboardEventCreateDialog && !dashboardEventCreateDialog.hidden) {
    closeDashboardEventCreateDialog({ confirmUnsaved: true });
  }

  if (
    event.key === "Escape" &&
    dashboardCompletionUploadDialog &&
    !dashboardCompletionUploadDialog.hidden
  ) {
    closeDashboardCompletionUploadDialog({ confirmUnsaved: true });
  }

  if (event.key === "Escape" && dashboardTaxUploadDialog && !dashboardTaxUploadDialog.hidden) {
    closeDashboardTaxUploadDialog({ confirmUnsaved: true });
  }
});

syncViewFromFrame();
syncPageTitleFromFrame();
