const eventCreateOpenButton = document.getElementById("event-create-open");
const eventCreateDialog = document.getElementById("event-create-dialog");
const eventCreateCancelButton = document.getElementById("event-create-cancel");
const eventCreateTitle = document.getElementById("event-create-title");
const eventFormSubmitButton = document.getElementById("event-form-submit");
const eventNameInput = document.getElementById("event-name-input");
const eventStatusCheckbox = document.getElementById("event-status-checkbox");
const eventStatusText = document.getElementById("event-status-text");
const eventListBody = document.getElementById("event-list-body");
const eventStartDateInput = document.getElementById("event-start-date");
const eventEndDateInput = document.getElementById("event-end-date");
const eventCompletionHoursInput = document.getElementById("event-completion-hours");
const eventCompletionDownloadStartsAtInput = document.getElementById(
  "event-completion-download-starts-at"
);
const eventCompletionDownloadSetting = document.getElementById(
  "event-completion-download-setting"
);
const eventCompletionDownloadToggle = document.querySelector(
  "#event-completion-download-setting [data-completion-download-toggle]"
);
const eventCompletionDocumentTypeOption = document.querySelector(
  "#event-create-dialog [data-completion-document-type-option]"
);
const eventDocumentTypeInputs = Array.from(
  document.querySelectorAll("#event-create-dialog [data-document-type]")
);
const portalCsrfToken = document.body.dataset.portalCsrfToken ?? "";
const adminEventsApiPath = "/api/v1/admin/events";
const eventListRowBusyMessageType = "ipg:event-row:busy";
const eventListRowUpsertMessageType = "ipg:event-row:upsert";
const eventListRowRemoveMessageType = "ipg:event-row:remove";
const eventListAlertMessageType = "ipg:event-list:alert";

let eventCreatePreviousFocus = null;
let eventDialogMode = "create";
let eventDialogInitialState = "";
let eventEditingId = "";
let eventRowsSignature = "";

const {
  formatIsoDateInputValue,
  formatCurrentDateTimeInputValue,
  formatUtcIsoDateTimeInputValue,
  installDatePicker,
  installDateTimePicker,
  normalizeDateInputValue,
  normalizeDateTimeInputValue,
} = window.iPlaygroundPortalDateTime;

function handlePortalUnauthorizedResponse(response) {
  return window.iPlaygroundPortalAuth?.handleUnauthorizedResponse?.(response) === true;
}

async function verifyPortalSession() {
  return window.iPlaygroundPortalAuth?.verifySession?.() ?? true;
}

function canRequestParentEventCreateDialog() {
  return window.parent && window.parent !== window;
}

function requestParentEventFormDialog(mode, eventData = {}) {
  window.parent.postMessage(
    {
      type: "ipg:event-form:open",
      mode,
      event: eventData,
    },
    window.location.origin
  );
}

function showEventPageAlert({ message, title, tone }) {
  window.iPlaygroundPageAlert?.show({
    dismissDelay: 6000,
    message,
    title,
    tone,
  });
}

function resolveEventDocumentTypes(mode, eventData) {
  const configuredTypes = Array.isArray(eventData.documentTypes) ? eventData.documentTypes : [];
  if (configuredTypes.length > 0) {
    return configuredTypes;
  }

  return mode === "create" ? ["completionCert"] : [];
}

function applyEventStatusValue(nextValue) {
  const normalizedValue = nextValue === "unlisted" ? "unlisted" : "open";

  if (eventStatusCheckbox instanceof HTMLInputElement) {
    eventStatusCheckbox.checked = normalizedValue === "open";
  }

  if (eventStatusText) {
    eventStatusText.textContent = normalizedValue === "open" ? "開放" : "下架";
  }
}

function collectEventDialogState() {
  return JSON.stringify({
    name: eventNameInput instanceof HTMLInputElement ? eventNameInput.value : "",
    status: eventStatusCheckbox instanceof HTMLInputElement && eventStatusCheckbox.checked
      ? "open"
      : "unlisted",
    eventStartDate:
      eventStartDateInput instanceof HTMLInputElement
        ? formatIsoDateInputValue(eventStartDateInput.value)
        : "",
    eventEndDate:
      eventEndDateInput instanceof HTMLInputElement
        ? formatIsoDateInputValue(eventEndDateInput.value)
        : "",
    completionHours:
      readCompletionHoursInputValue(),
    documentTypes: eventDocumentTypeInputs
      .filter((input) => input instanceof HTMLInputElement && input.checked)
      .map((input) => input.value),
    completionCertDownloadStartsAt:
      eventCompletionDownloadStartsAtInput instanceof HTMLInputElement
        ? formatUtcIsoDateTimeInputValue(eventCompletionDownloadStartsAtInput.value)
        : "",
  });
}

function collectEventDialogPayload() {
  return JSON.parse(collectEventDialogState());
}

function hasEventNameValue() {
  return eventNameInput instanceof HTMLInputElement && eventNameInput.value.trim().length > 0;
}

function hasEventDateValues() {
  return (
    eventStartDateInput instanceof HTMLInputElement &&
    eventEndDateInput instanceof HTMLInputElement &&
    formatIsoDateInputValue(eventStartDateInput.value) !== "" &&
    formatIsoDateInputValue(eventEndDateInput.value) !== ""
  );
}

function hasCompletionHoursValue() {
  const value = readCompletionHoursInputValue();
  return Number.isInteger(value) && value > 0;
}

function hasRequiredCompletionCertFields() {
  if (!isCompletionCertEnabled()) {
    return true;
  }

  return (
    hasCompletionHoursValue() &&
    eventCompletionDownloadStartsAtInput instanceof HTMLInputElement &&
    formatUtcIsoDateTimeInputValue(eventCompletionDownloadStartsAtInput.value) !== ""
  );
}

function readCompletionHoursInputValue() {
  if (!(eventCompletionHoursInput instanceof HTMLInputElement)) {
    return null;
  }

  const rawValue = eventCompletionHoursInput.value.trim();
  if (!/^[0-9]+$/.test(rawValue)) {
    return null;
  }

  return Number.parseInt(rawValue, 10);
}

function updateEventFormSubmitState() {
  if (eventFormSubmitButton instanceof HTMLButtonElement) {
    eventFormSubmitButton.disabled =
      !hasEventNameValue() || !hasEventDateValues() || !hasRequiredCompletionCertFields();
  }
}

function getCompletionCertDocumentTypeInput() {
  return eventDocumentTypeInputs.find((input) => input.value === "completionCert");
}

function isCompletionCertEnabled() {
  const completionCertInput = getCompletionCertDocumentTypeInput();
  return completionCertInput instanceof HTMLInputElement && completionCertInput.checked;
}

function updateCompletionDownloadStartsAtVisibility() {
  const isVisible = isCompletionCertEnabled();

  if (eventCompletionDownloadSetting instanceof HTMLElement) {
    eventCompletionDownloadSetting.hidden = !isVisible;
  }

  if (
    isVisible &&
    eventCompletionDownloadStartsAtInput instanceof HTMLInputElement &&
    eventCompletionDownloadStartsAtInput.value.trim() === ""
  ) {
    eventCompletionDownloadStartsAtInput.value = formatCurrentDateTimeInputValue();
    eventCompletionDownloadStartsAtInput.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function toggleCompletionCertDocumentType() {
  const completionCertInput = getCompletionCertDocumentTypeInput();

  if (!(completionCertInput instanceof HTMLInputElement)) {
    return;
  }

  completionCertInput.checked = !completionCertInput.checked;
  completionCertInput.dispatchEvent(new Event("change", { bubbles: true }));
}

function setEventDialogMode(mode = "create", eventData = {}) {
  const isEditMode = mode === "edit";
  const documentTypes = resolveEventDocumentTypes(mode, eventData);
  eventDialogMode = isEditMode ? "edit" : "create";
  eventEditingId = isEditMode && typeof eventData.id === "string" ? eventData.id : "";

  if (eventCreateTitle) {
    eventCreateTitle.textContent = isEditMode ? "編輯活動" : "建立活動";
  }

  if (eventFormSubmitButton) {
    eventFormSubmitButton.textContent = isEditMode ? "儲存變更" : "建立活動";
  }

  if (eventNameInput instanceof HTMLInputElement) {
    eventNameInput.value = eventData.name ?? "";
  }

  if (eventStartDateInput instanceof HTMLInputElement) {
    eventStartDateInput.value =
      normalizeDateInputValue(eventData.eventStartDate ?? "") || "";
    eventStartDateInput.dispatchEvent(new Event("input", { bubbles: true }));
  }

  if (eventEndDateInput instanceof HTMLInputElement) {
    eventEndDateInput.value =
      normalizeDateInputValue(eventData.eventEndDate ?? "") || "";
    eventEndDateInput.dispatchEvent(new Event("input", { bubbles: true }));
  }

  if (eventCompletionHoursInput instanceof HTMLInputElement) {
    eventCompletionHoursInput.value =
      Number.isInteger(eventData.completionHours) && eventData.completionHours > 0
        ? String(eventData.completionHours)
        : "";
  }

  if (eventCompletionDownloadStartsAtInput instanceof HTMLInputElement) {
    eventCompletionDownloadStartsAtInput.value =
      normalizeDateTimeInputValue(eventData.completionCertDownloadStartsAt ?? "") ||
      formatCurrentDateTimeInputValue();
    eventCompletionDownloadStartsAtInput.dispatchEvent(new Event("input", { bubbles: true }));
  }

  updateEventFormSubmitState();

  applyEventStatusValue(eventData.status ?? (isEditMode ? "open" : "unlisted"));

  eventDocumentTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.checked = documentTypes.includes(input.value);
    }
  });

  updateCompletionDownloadStartsAtVisibility();
  eventDialogInitialState = collectEventDialogState();
}

function openEventFormDialog({ mode = "create", eventData = {} } = {}) {
  if (canRequestParentEventCreateDialog()) {
    requestParentEventFormDialog(mode, eventData);
    return;
  }

  if (!eventCreateDialog) {
    return;
  }

  setEventDialogMode(mode, eventData);
  eventCreatePreviousFocus = document.activeElement;
  eventCreateDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  eventNameInput?.focus();
}

async function openEventCreateDialog() {
  if (!(await verifyPortalSession())) {
    return;
  }

  openEventFormDialog({ mode: "create" });
}

function buildEventDataFromRow(row) {
  const documentTypes = (row.dataset.eventDocumentTypes ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    id: row.dataset.eventId ?? "",
    name: row.dataset.eventName ?? "",
    status: row.dataset.eventStatus ?? "open",
    documentTypes,
    eventStartDate: row.dataset.eventStartDate ?? "",
    eventEndDate: row.dataset.eventEndDate ?? "",
    completionHours: Number.parseInt(row.dataset.eventCompletionHours ?? "", 10),
    completionCertDownloadStartsAt:
      row.dataset.eventCompletionCertDownloadStartsAt ?? "",
  };
}

async function openEventEditDialog(row) {
  if (!(await verifyPortalSession())) {
    return;
  }

  openEventFormDialog({
    mode: "edit",
    eventData: buildEventDataFromRow(row),
  });
}

function resolveEventDocumentTypeItems(documentTypes) {
  const items = {
    completionCert: {
      label: "完訓證明",
      typeClassName: "is-completion-cert",
    },
    volunteerServiceCert: {
      label: "志工服務證明",
      typeClassName: "is-volunteer-service-cert",
    },
    taxReceipt: {
      label: "營業稅繳稅證明",
      typeClassName: "is-tax-receipt",
    },
  };

  return documentTypes.map((documentType) => items[documentType]).filter(Boolean);
}

function resolveEventStatusLabel(status) {
  return status === "open" ? "開放" : "下架";
}

function resolveEventStatusBadgeClass(status) {
  return status === "open"
    ? "event-status-badge is-open"
    : "event-status-badge is-unlisted";
}

function normalizeLoadedEvent(eventData) {
  return {
    completionCertDownloadStartsAt:
      typeof eventData?.completionCertDownloadStartsAt === "string"
        ? eventData.completionCertDownloadStartsAt
        : "",
    completionHours:
      Number.isInteger(eventData?.completionHours) && eventData.completionHours > 0
        ? eventData.completionHours
        : null,
    documentTypes: Array.isArray(eventData?.documentTypes)
      ? eventData.documentTypes.filter((documentType) => typeof documentType === "string")
      : [],
    eventEndDate: typeof eventData?.eventEndDate === "string" ? eventData.eventEndDate : "",
    eventStartDate: typeof eventData?.eventStartDate === "string" ? eventData.eventStartDate : "",
    id: typeof eventData?.id === "string" ? eventData.id : "",
    name: typeof eventData?.name === "string" ? eventData.name : "",
    status: eventData?.status === "open" ? "open" : "unlisted",
  };
}

function findEventRowById(eventId) {
  if (!eventId || !(eventListBody instanceof HTMLTableSectionElement)) {
    return null;
  }

  return eventListBody.querySelector(`[data-event-id="${CSS.escape(eventId)}"]`);
}

function setEventRowBusyState(eventId, isBusy) {
  const row = findEventRowById(eventId);
  if (!(row instanceof HTMLTableRowElement)) {
    return;
  }

  row.classList.toggle("is-disabled", isBusy);
  row.setAttribute("aria-disabled", String(isBusy));
  row.tabIndex = isBusy ? -1 : 0;
}

function removeEventRow(eventId) {
  const row = findEventRowById(eventId);
  if (!(row instanceof HTMLTableRowElement)) {
    return;
  }

  row.remove();

  if (
    eventListBody instanceof HTMLTableSectionElement &&
    eventListBody.querySelectorAll(".event-list-row").length === 0
  ) {
    renderEventEmptyRow("尚未建立活動。");
  }
}

function renderEventEmptyRow(message) {
  if (!(eventListBody instanceof HTMLTableSectionElement)) {
    return;
  }

  const row = document.createElement("tr");
  const cell = document.createElement("td");
  row.className = "document-empty-row";
  cell.colSpan = 3;
  cell.textContent = message;
  row.append(cell);
  eventListBody.replaceChildren(row);
}

function bindEventRow(row) {
  row.addEventListener("click", () => {
    if (row.classList.contains("is-disabled")) {
      return;
    }

    openEventEditDialog(row);
  });

  row.addEventListener("keydown", (event) => {
    if (row.classList.contains("is-disabled")) {
      return;
    }

    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    openEventEditDialog(row);
  });
}

function buildEventRow(eventData) {
  const row = document.createElement("tr");
  const nameCell = document.createElement("td");
  const documentTypesCell = document.createElement("td");
  const statusCell = document.createElement("td");
  const documentPillList = document.createElement("div");
  const statusBadge = document.createElement("span");
  const eventName = eventData.name;
  const documentTypeItems = resolveEventDocumentTypeItems(eventData.documentTypes);

  row.className = "event-list-row";
  row.tabIndex = 0;
  row.setAttribute("role", "button");
  row.setAttribute("aria-label", `編輯活動 ${eventName}`);
  row.dataset.eventFormOpen = "edit";
  row.dataset.eventId = eventData.id;
  row.dataset.eventName = eventName;
  row.dataset.eventStatus = eventData.status;
  row.dataset.eventDocumentTypes = eventData.documentTypes.join(",");
  row.dataset.eventStartDate = eventData.eventStartDate;
  row.dataset.eventEndDate = eventData.eventEndDate;
  row.dataset.eventCompletionHours = String(eventData.completionHours ?? "");
  row.dataset.eventCompletionCertDownloadStartsAt = eventData.completionCertDownloadStartsAt;

  nameCell.textContent = eventName;
  documentPillList.className = "document-type-pill-list";

  if (documentTypeItems.length > 0) {
    documentTypeItems.forEach((documentTypeItem) => {
      const documentPill = document.createElement("span");
      documentPill.className = `document-type-pill ${documentTypeItem.typeClassName}`;
      documentPill.textContent = documentTypeItem.label;
      documentPillList.append(documentPill);
    });
  } else {
    const emptyDocumentPill = document.createElement("span");
    emptyDocumentPill.className = "document-type-pill is-empty";
    emptyDocumentPill.textContent = "未開放文件申請";
    documentPillList.append(emptyDocumentPill);
  }

  statusBadge.className = resolveEventStatusBadgeClass(eventData.status);
  statusBadge.textContent = resolveEventStatusLabel(eventData.status);
  documentTypesCell.append(documentPillList);
  statusCell.append(statusBadge);

  row.append(nameCell, documentTypesCell, statusCell);
  bindEventRow(row);
  return row;
}

function buildPendingEventRow(eventData) {
  const row = buildEventRow(eventData);
  row.classList.add("is-disabled");
  row.setAttribute("aria-disabled", "true");
  row.tabIndex = -1;
  return row;
}

function renderEventRows(events) {
  if (!(eventListBody instanceof HTMLTableSectionElement)) {
    return;
  }

  eventRowsSignature = JSON.stringify(events);

  if (events.length === 0) {
    renderEventEmptyRow("尚未建立活動。");
    return;
  }

  eventListBody.replaceChildren(...events.map((eventData) => buildEventRow(eventData)));
}

function upsertEventRow(eventData, { replaceEventId = "" } = {}) {
  const normalizedEvent = normalizeLoadedEvent(eventData);
  const existingRow = findEventRowById(replaceEventId || normalizedEvent.id);
  const nextRow = buildEventRow(normalizedEvent);

  if (existingRow) {
    existingRow.replaceWith(nextRow);
    return;
  }

  if (!(eventListBody instanceof HTMLTableSectionElement)) {
    return;
  }

  eventListBody.querySelector(".document-empty-row")?.remove();
  eventListBody.prepend(nextRow);
}

function insertPendingEventRow(eventData) {
  if (!(eventListBody instanceof HTMLTableSectionElement)) {
    return;
  }

  eventListBody.querySelector(".document-empty-row")?.remove();
  eventListBody.prepend(buildPendingEventRow(normalizeLoadedEvent(eventData)));
}

async function loadEventRows() {
  const eventCache = window.iPlaygroundPortalEvents;
  const cachedEvents = eventCache?.getCachedEvents?.();
  let cachedEventsSignature = "";

  if (Array.isArray(cachedEvents)) {
    const events = cachedEvents.map((eventData) => normalizeLoadedEvent(eventData));
    cachedEventsSignature = JSON.stringify(events);
    renderEventRows(events);
  } else {
    renderEventEmptyRow("活動載入中。");
  }

  try {
    const response = await fetch(adminEventsApiPath, {
      headers: {
        Accept: "application/json",
      },
    });
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "活動清單載入失敗。");
    }

    const responseEvents = Array.isArray(responsePayload.events) ? responsePayload.events : [];
    eventCache?.setCachedEvents?.(responseEvents);
    const events = responseEvents.map((eventData) => normalizeLoadedEvent(eventData));
    const refreshedEventsSignature = JSON.stringify(events);
    if (refreshedEventsSignature !== cachedEventsSignature) {
      renderEventRows(events);
    }
  } catch (error) {
    if (Array.isArray(cachedEvents)) {
      return;
    }
    renderEventEmptyRow(error instanceof Error ? error.message : "活動清單載入失敗。");
  }
}

function shouldConfirmEventDialogClose() {
  if (!eventCreateDialog || eventCreateDialog.hidden) {
    return false;
  }

  if (eventDialogMode === "create") {
    return true;
  }

  return collectEventDialogState() !== eventDialogInitialState;
}

function confirmEventDialogClose() {
  if (!shouldConfirmEventDialogClose()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function closeEventCreateDialog({ confirmUnsaved = false } = {}) {
  if (!eventCreateDialog) {
    return;
  }

  if (confirmUnsaved && !confirmEventDialogClose()) {
    return;
  }

  eventCreateDialog.hidden = true;
  document.body.classList.remove("has-event-dialog");

  if (eventCreatePreviousFocus instanceof HTMLElement) {
    eventCreatePreviousFocus.focus();
  }
}

function buildEventIdempotencyKey() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function buildPendingEventId(idempotencyKey) {
  return `pending_${idempotencyKey.replaceAll("-", "_")}`;
}

async function submitEventForm() {
  if (!(eventFormSubmitButton instanceof HTMLButtonElement)) {
    return;
  }

  if (!hasEventNameValue()) {
    updateEventFormSubmitState();
    eventNameInput?.focus();
    return;
  }

  if (!hasEventDateValues() || !hasRequiredCompletionCertFields()) {
    updateEventFormSubmitState();
    eventStartDateInput?.focus();
    return;
  }

  eventFormSubmitButton.disabled = true;
  const isEditMode = eventDialogMode === "edit";
  const idempotencyKey = isEditMode ? "" : buildEventIdempotencyKey();
  const pendingEventId = isEditMode ? "" : buildPendingEventId(idempotencyKey);
  try {
    const eventApiPath =
      isEditMode && eventEditingId
        ? `${adminEventsApiPath}/${encodeURIComponent(eventEditingId)}`
        : adminEventsApiPath;
    if (isEditMode) {
      closeEventCreateDialog();
      setEventRowBusyState(eventEditingId, true);
    } else {
      const pendingEvent = {
        ...collectEventDialogPayload(),
        id: pendingEventId,
      };
      closeEventCreateDialog();
      insertPendingEventRow(pendingEvent);
    }

    const response = await fetch(eventApiPath, {
      method: isEditMode ? "PUT" : "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Portal-CSRF-Token": portalCsrfToken,
        ...(isEditMode ? {} : { "Idempotency-Key": idempotencyKey }),
      },
      body: JSON.stringify(collectEventDialogPayload()),
    });
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "建立活動失敗，請稍後再試。");
    }

    const savedEvent = responsePayload.event;
    window.iPlaygroundPortalEvents?.upsertCachedEvent?.(savedEvent);

    if (isEditMode) {
      upsertEventRow(savedEvent);
      showEventPageAlert({
        message: "活動資料已更新。",
        title: "更新成功",
        tone: "success",
      });
    } else {
      upsertEventRow(savedEvent, { replaceEventId: pendingEventId });
      showEventPageAlert({
        message: "活動已建立。",
        title: "建立成功",
        tone: "success",
      });
    }
  } catch (error) {
    showEventPageAlert({
      message:
        error instanceof Error
          ? error.message
          : isEditMode
            ? "活動儲存失敗，請稍後再試。"
            : "建立活動失敗，請稍後再試。",
      title: isEditMode ? "儲存失敗" : "建立失敗",
      tone: "error",
    });
    if (isEditMode) {
      setEventRowBusyState(eventEditingId, false);
    } else {
      removeEventRow(pendingEventId);
    }
    updateEventFormSubmitState();
  }
}

eventCreateOpenButton?.addEventListener("click", () => {
  void openEventCreateDialog();
});
eventCreateCancelButton?.addEventListener("click", () => {
  closeEventCreateDialog({ confirmUnsaved: true });
});

eventStatusCheckbox?.addEventListener("change", () => {
  applyEventStatusValue(eventStatusCheckbox.checked ? "open" : "unlisted");
});

eventFormSubmitButton?.addEventListener("click", () => {
  void submitEventForm();
});
eventNameInput?.addEventListener("input", updateEventFormSubmitState);
eventStartDateInput?.addEventListener("input", updateEventFormSubmitState);
eventEndDateInput?.addEventListener("input", updateEventFormSubmitState);
eventCompletionHoursInput?.addEventListener("input", updateEventFormSubmitState);
installDatePicker(eventStartDateInput);
installDatePicker(eventEndDateInput);
installDateTimePicker(eventCompletionDownloadStartsAtInput);

eventDocumentTypeInputs.forEach((input) => {
  input.addEventListener("change", updateCompletionDownloadStartsAtVisibility);
});

eventCompletionDownloadToggle?.addEventListener("click", () => {
  toggleCompletionCertDocumentType();
});

eventCompletionDownloadToggle?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  event.preventDefault();
  toggleCompletionCertDocumentType();
});

eventCompletionDocumentTypeOption?.addEventListener("click", (event) => {
  if (event.target !== eventCompletionDocumentTypeOption) {
    return;
  }

  toggleCompletionCertDocumentType();
});

window.addEventListener("ipg:portal-events:updated", (event) => {
  const events = Array.isArray(event.detail?.events)
    ? event.detail.events.map((eventData) => normalizeLoadedEvent(eventData))
    : [];
  const nextEventsSignature = JSON.stringify(events);
  if (nextEventsSignature !== eventRowsSignature) {
    renderEventRows(events);
  }
});

void loadEventRows();

eventCreateDialog?.addEventListener("click", (event) => {
  if (event.target === eventCreateDialog) {
    closeEventCreateDialog({ confirmUnsaved: true });
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && eventCreateDialog && !eventCreateDialog.hidden) {
    closeEventCreateDialog({ confirmUnsaved: true });
  }
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) {
    return;
  }

  const message = event.data ?? {};
  if (message.type === eventListRowBusyMessageType) {
    setEventRowBusyState(message.eventId, Boolean(message.isBusy));
    return;
  }

  if (message.type === eventListRowUpsertMessageType) {
    upsertEventRow(message.event ?? {}, {
      replaceEventId: typeof message.replaceEventId === "string" ? message.replaceEventId : "",
    });
    return;
  }

  if (message.type === eventListRowRemoveMessageType) {
    removeEventRow(typeof message.eventId === "string" ? message.eventId : "");
    return;
  }

  if (message.type === eventListAlertMessageType) {
    showEventPageAlert({
      message: typeof message.message === "string" ? message.message : "",
      title: typeof message.title === "string" ? message.title : "",
      tone: typeof message.tone === "string" ? message.tone : "info",
    });
  }
});
