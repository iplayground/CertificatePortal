const eventCreateOpenButton = document.getElementById("event-create-open");
const eventCreateDialog = document.getElementById("event-create-dialog");
const eventCreateCancelButton = document.getElementById("event-create-cancel");
const eventCreateTitle = document.getElementById("event-create-title");
const eventFormSubmitButton = document.getElementById("event-form-submit");
const eventNameInput = document.getElementById("event-name-input");
const eventStatusCheckbox = document.getElementById("event-status-checkbox");
const eventStatusText = document.getElementById("event-status-text");
const eventDocumentTypeInputs = Array.from(
  document.querySelectorAll("#event-create-dialog [data-document-type]")
);
const eventRows = Array.from(document.querySelectorAll("[data-event-form-open]"));

let eventCreatePreviousFocus = null;
let eventDialogMode = "create";
let eventDialogInitialState = "";

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
    documentTypes: eventDocumentTypeInputs
      .filter((input) => input instanceof HTMLInputElement && input.checked)
      .map((input) => input.value),
  });
}

function setEventDialogMode(mode = "create", eventData = {}) {
  const isEditMode = mode === "edit";
  const documentTypes = resolveEventDocumentTypes(mode, eventData);
  eventDialogMode = isEditMode ? "edit" : "create";

  if (eventCreateTitle) {
    eventCreateTitle.textContent = isEditMode ? "編輯活動" : "建立活動";
  }

  if (eventFormSubmitButton) {
    eventFormSubmitButton.textContent = isEditMode ? "儲存變更" : "建立活動";
  }

  if (eventNameInput instanceof HTMLInputElement) {
    eventNameInput.value = eventData.name ?? (isEditMode ? "" : "iPlayground 2026");
  }

  applyEventStatusValue(eventData.status ?? "open");

  eventDocumentTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.checked = documentTypes.includes(input.value);
    }
  });

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

function openEventCreateDialog() {
  openEventFormDialog({ mode: "create" });
}

function buildEventDataFromRow(row) {
  const documentTypes = (row.dataset.eventDocumentTypes ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  return {
    name: row.dataset.eventName ?? "",
    status: row.dataset.eventStatus ?? "open",
    documentTypes,
  };
}

function openEventEditDialog(row) {
  openEventFormDialog({
    mode: "edit",
    eventData: buildEventDataFromRow(row),
  });
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

eventCreateOpenButton?.addEventListener("click", openEventCreateDialog);
eventCreateCancelButton?.addEventListener("click", () => {
  closeEventCreateDialog({ confirmUnsaved: true });
});

eventStatusCheckbox?.addEventListener("change", () => {
  applyEventStatusValue(eventStatusCheckbox.checked ? "open" : "unlisted");
});

eventRows.forEach((row) => {
  row.addEventListener("click", () => {
    openEventEditDialog(row);
  });

  row.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }

    event.preventDefault();
    openEventEditDialog(row);
  });
});

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
