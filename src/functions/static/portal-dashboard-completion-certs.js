const completionUploadOpenButton = document.getElementById("completion-upload-open");
const completionUploadDialog = document.getElementById("completion-upload-dialog");
const completionUploadCancelButton = document.getElementById("completion-upload-cancel");
const completionUploadSubmitButton = document.getElementById("completion-upload-submit");
const completionUploadFileInput = document.getElementById("completion-upload-file");
const completionUploadFileName = document.getElementById("completion-upload-file-name");
const completionUploadEvent = document.getElementById("completion-upload-event");
const completionUploadEventSelect = document.getElementById("completion-upload-event-select");
const completionUploadEventTrigger = document.getElementById(
  "completion-upload-event-trigger"
);
const completionUploadEventValue = document.getElementById("completion-upload-event-value");
const completionUploadEventMenu = document.getElementById("completion-upload-event-options");
const completionUploadEventOptions = Array.from(
  document.querySelectorAll("#completion-upload-event-options .custom-select-option")
);
const completionCertTableBody = document.getElementById("completion-cert-table-body");
const completionCertEmptyRow = document.getElementById("completion-cert-empty-row");
const completionCertRowTemplate = document.getElementById(
  "completion-cert-row-template"
);
const completionBulkDownloadableButton = document.getElementById("completion-bulk-downloadable");
const completionBulkBlockedButton = document.getElementById("completion-bulk-blocked");
const completionFilterForm = document.querySelector(".document-filter-form");
const completionEventFilter = document.getElementById("completion-event-filter");
const completionEventFilterSelect = document.getElementById("completion-event-filter-select");
const completionEventFilterTrigger = document.getElementById(
  "completion-event-filter-trigger"
);
const completionEventFilterValue = document.getElementById("completion-event-filter-value");
const completionEventFilterMenu = document.getElementById("completion-event-filter-options");
const completionEventFilterOptions = Array.from(
  document.querySelectorAll("#completion-event-filter-options .custom-select-option")
);
const completionUploadOpenMessageType = "ipg:completion-upload:open";
const completionUploadImportMessageType = "ipg:completion-upload:import";
const defaultCompletionUploadFileName = "尚未選擇 CSV 檔案";
const invalidCompletionUploadFileName = "請選擇 CSV 檔案";
const failedCompletionUploadFileName = "CSV 檔案讀取失敗";
const defaultCompletionEventName = "iPlayground 2026";
const completionCsvFieldAliases = {
  attendeeName: ["姓名", "name", "attendeeName", "attendee_name", "中文姓名"],
  email: ["email", "e-mail", "電子郵件", "信箱"],
  registrationNumber: [
    "報名序號",
    "報名編號",
    "序號",
    "registrationNumber",
    "registration_number",
    "registrationNo",
    "registration_no",
  ],
  ticketType: ["票種", "ticketType", "ticket_type", "票種名稱"],
};

let completionUploadPreviousFocus = null;
let completionCertRows = [];

function canRequestParentCompletionUploadDialog() {
  return window.parent && window.parent !== window;
}

function requestParentCompletionUploadDialog() {
  window.parent.postMessage(
    {
      type: completionUploadOpenMessageType,
    },
    window.location.origin
  );
}

function getCompletionFilterEventName() {
  if (completionEventFilter instanceof HTMLInputElement) {
    return completionEventFilter.value || defaultCompletionEventName;
  }

  return defaultCompletionEventName;
}

function getCompletionUploadEventName() {
  if (completionUploadEvent instanceof HTMLInputElement) {
    return completionUploadEvent.value || getCompletionFilterEventName();
  }

  return getCompletionFilterEventName();
}

function applyCompletionUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultCompletionEventName;

  if (completionUploadEvent instanceof HTMLInputElement) {
    completionUploadEvent.value = normalizedValue;
  }

  if (completionUploadEventValue) {
    completionUploadEventValue.textContent = normalizedValue;
  }

  completionUploadEventOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function resetCompletionUploadDialog() {
  if (completionUploadFileInput instanceof HTMLInputElement) {
    completionUploadFileInput.value = "";
  }

  applyCompletionUploadEventValue(getCompletionFilterEventName());
  updateCompletionUploadFileName();
}

function hasSelectedCompletionUploadFile() {
  return (
    completionUploadFileInput instanceof HTMLInputElement &&
    completionUploadFileInput.files instanceof FileList &&
    completionUploadFileInput.files.length > 0
  );
}

function isCompletionCsvFile(file) {
  return file.name.toLowerCase().endsWith(".csv");
}

function updateCompletionUploadFileName() {
  if (!(completionUploadFileName instanceof HTMLElement)) {
    return;
  }

  if (
    !(completionUploadFileInput instanceof HTMLInputElement) ||
    !(completionUploadFileInput.files instanceof FileList) ||
    completionUploadFileInput.files.length === 0
  ) {
    completionUploadFileName.textContent = defaultCompletionUploadFileName;
    return;
  }

  const selectedFile = completionUploadFileInput.files[0];
  if (!isCompletionCsvFile(selectedFile)) {
    completionUploadFileInput.value = "";
    completionUploadFileName.textContent = invalidCompletionUploadFileName;
    return;
  }

  completionUploadFileName.textContent = selectedFile.name;
}

function getSelectedCompletionUploadFile() {
  if (
    !(completionUploadFileInput instanceof HTMLInputElement) ||
    !(completionUploadFileInput.files instanceof FileList) ||
    completionUploadFileInput.files.length === 0
  ) {
    return null;
  }

  return completionUploadFileInput.files[0];
}

function normaliseCompletionCsvKey(value) {
  return value.trim().toLowerCase().replace(/[\s_-]+/g, "");
}

function parseCompletionCsv(csvText) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < csvText.length; index += 1) {
    const character = csvText[index];

    if (character === '"') {
      if (inQuotes && csvText[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (character === "," && !inQuotes) {
      row.push(field);
      field = "";
      continue;
    }

    if ((character === "\n" || character === "\r") && !inQuotes) {
      if (character === "\r" && csvText[index + 1] === "\n") {
        index += 1;
      }
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      continue;
    }

    field += character;
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }

  return rows
    .map((csvRow) => csvRow.map((csvField) => csvField.trim()))
    .filter((csvRow) => csvRow.some((csvField) => csvField.length > 0));
}

function findCompletionCsvColumnIndex(headers, aliases) {
  const normalizedAliases = aliases.map(normaliseCompletionCsvKey);
  return headers.findIndex((header) =>
    normalizedAliases.includes(normaliseCompletionCsvKey(header))
  );
}

function hasCompletionCsvHeader(headers) {
  return Object.values(completionCsvFieldAliases).some(
    (aliases) => findCompletionCsvColumnIndex(headers, aliases) >= 0
  );
}

function resolveCompletionCsvValue(row, columnIndexes, fieldName, fallbackIndex) {
  const columnIndex = columnIndexes[fieldName];
  const value = columnIndex >= 0 ? row[columnIndex] : row[fallbackIndex];
  return value?.trim() ?? "";
}

function buildCompletionCertRows(csvText, eventName = defaultCompletionEventName) {
  const parsedRows = parseCompletionCsv(csvText);
  if (parsedRows.length === 0) {
    return [];
  }

  const headers = parsedRows[0];
  const hasHeader = hasCompletionCsvHeader(headers);
  const dataRows = hasHeader ? parsedRows.slice(1) : parsedRows;
  const columnIndexes = {
    attendeeName: hasHeader
      ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.attendeeName)
      : -1,
    email: hasHeader ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.email) : -1,
    registrationNumber: hasHeader
      ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.registrationNumber)
      : -1,
    ticketType: hasHeader
      ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.ticketType)
      : -1,
  };
  const importId = Date.now();

  return dataRows
    .map((row, index) => ({
      attendeeName: resolveCompletionCsvValue(row, columnIndexes, "attendeeName", 2),
      email: resolveCompletionCsvValue(row, columnIndexes, "email", 3),
      eventName,
      id: `completion-row-${importId}-${index}`,
      isDownloadable: false,
      registrationNumber: resolveCompletionCsvValue(row, columnIndexes, "registrationNumber", 0),
      ticketType: resolveCompletionCsvValue(row, columnIndexes, "ticketType", 1),
    }))
    .filter((row) =>
      [row.attendeeName, row.email, row.registrationNumber, row.ticketType].some(Boolean)
    );
}

function setTextContent(parent, selector, value) {
  const element = parent.querySelector(selector);
  if (element) {
    element.textContent = value || "-";
  }
}

function getVisibleCompletionCertRows() {
  const eventName = getCompletionFilterEventName();
  return completionCertRows.filter((row) => row.eventName === eventName);
}

function applyCompletionRowDownloadState(rowElement, rowData) {
  const statusLabel = rowElement.querySelector('[data-field="downloadStatus"]');
  const switchInput = rowElement.querySelector('[data-action="toggle-downloadable"]');
  const downloadButton = rowElement.querySelector(".document-download-button");

  rowElement.classList.toggle("is-downloadable", rowData.isDownloadable);
  rowElement.classList.toggle("is-blocked", !rowData.isDownloadable);

  if (statusLabel) {
    statusLabel.textContent = rowData.isDownloadable ? "已簽到" : "未簽到";
  }

  if (switchInput instanceof HTMLInputElement) {
    switchInput.checked = rowData.isDownloadable;
  }

  if (downloadButton instanceof HTMLButtonElement) {
    downloadButton.disabled = !rowData.isDownloadable;
  }
}

function updateCompletionBulkActionControls() {
  const visibleRows = getVisibleCompletionCertRows();
  const hasVisibleRows = visibleRows.length > 0;
  if (completionBulkDownloadableButton instanceof HTMLButtonElement) {
    completionBulkDownloadableButton.disabled = !hasVisibleRows;
  }

  if (completionBulkBlockedButton instanceof HTMLButtonElement) {
    completionBulkBlockedButton.disabled = !hasVisibleRows;
  }
}

function setCompletionRowDownloadState(rowId, isDownloadable) {
  const rowData = completionCertRows.find((row) => row.id === rowId);
  if (!rowData) {
    return;
  }

  rowData.isDownloadable = isDownloadable;
  const rowElement = completionCertTableBody?.querySelector(`[data-row-id="${rowId}"]`);
  if (rowElement instanceof HTMLTableRowElement) {
    applyCompletionRowDownloadState(rowElement, rowData);
  }
}

function renderCompletionCertRows() {
  if (
    !completionCertTableBody ||
    !(completionCertRowTemplate instanceof HTMLTemplateElement)
  ) {
    return;
  }

  completionCertTableBody
    .querySelectorAll(".completion-cert-row")
    .forEach((rowElement) => rowElement.remove());

  const visibleRows = getVisibleCompletionCertRows();

  if (completionCertEmptyRow instanceof HTMLTableRowElement) {
    completionCertEmptyRow.hidden = visibleRows.length > 0;
  }

  visibleRows.forEach((rowData) => {
    const rowFragment = completionCertRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".completion-cert-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    setTextContent(rowElement, '[data-field="registrationNumber"]', rowData.registrationNumber);
    setTextContent(rowElement, '[data-field="ticketType"]', rowData.ticketType);
    setTextContent(rowElement, '[data-field="attendeeName"]', rowData.attendeeName);
    setTextContent(rowElement, '[data-field="email"]', rowData.email);

    const switchInput = rowElement.querySelector('[data-action="toggle-downloadable"]');
    if (switchInput instanceof HTMLInputElement) {
      const rowLabel = rowData.attendeeName || rowData.registrationNumber || "此筆完訓證明";
      switchInput.setAttribute("aria-label", `${rowLabel} 簽到狀態`);
      switchInput.addEventListener("change", () => {
        setCompletionRowDownloadState(rowData.id, switchInput.checked);
      });
    }

    applyCompletionRowDownloadState(rowElement, rowData);
    completionCertTableBody.append(rowElement);
  });

  updateCompletionBulkActionControls();
}

function importCompletionCsvText(csvText, eventName = getCompletionUploadEventName()) {
  completionCertRows = [
    ...completionCertRows.filter((row) => row.eventName !== eventName),
    ...buildCompletionCertRows(csvText, eventName),
  ];
  applyCompletionEventFilterValue(eventName, { renderRows: false });
  renderCompletionCertRows();
}

async function importSelectedCompletionCsvFile() {
  const selectedFile = getSelectedCompletionUploadFile();
  if (!selectedFile || !isCompletionCsvFile(selectedFile)) {
    updateCompletionUploadFileName();
    completionUploadFileInput?.focus();
    return;
  }

  try {
    importCompletionCsvText(await selectedFile.text());
    closeCompletionUploadDialog();
  } catch (error) {
    void error;
    if (completionUploadFileName) {
      completionUploadFileName.textContent = failedCompletionUploadFileName;
    }
  }
}

function applyDownloadableStateToCurrentActivity(isDownloadable) {
  getVisibleCompletionCertRows().forEach((row) => {
    setCompletionRowDownloadState(row.id, isDownloadable);
  });
}

function confirmCompletionUploadDialogClose() {
  if (!hasSelectedCompletionUploadFile()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function openCompletionUploadDialog() {
  if (canRequestParentCompletionUploadDialog()) {
    requestParentCompletionUploadDialog();
    return;
  }

  if (!completionUploadDialog) {
    return;
  }

  resetCompletionUploadDialog();
  completionUploadPreviousFocus = document.activeElement;
  completionUploadDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  completionUploadFileInput?.focus();
}

function closeCompletionUploadDialog({ confirmUnsaved = false } = {}) {
  if (!completionUploadDialog) {
    return;
  }

  if (confirmUnsaved && !confirmCompletionUploadDialogClose()) {
    return;
  }

  completionUploadDialog.hidden = true;
  closeCompletionUploadEventSelect();
  document.body.classList.remove("has-event-dialog");

  if (completionUploadPreviousFocus instanceof HTMLElement) {
    completionUploadPreviousFocus.focus();
  }
}

function applyCompletionEventFilterValue(nextValue, { renderRows = true } = {}) {
  const normalizedValue = nextValue?.trim();
  if (!normalizedValue) {
    return;
  }

  if (completionEventFilter instanceof HTMLInputElement) {
    completionEventFilter.value = normalizedValue;
  }

  if (completionEventFilterValue) {
    completionEventFilterValue.textContent = normalizedValue;
  }

  completionEventFilterOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });

  applyCompletionFilters();

  if (renderRows) {
    renderCompletionCertRows();
  }
}

function applyCompletionFilters() {
  const eventName = completionEventFilter instanceof HTMLInputElement ? completionEventFilter.value : "";
  return { eventName };
}

function closeCompletionEventFilterSelect({ blurTrigger = false } = {}) {
  completionEventFilterSelect?.classList.remove("is-open");
  completionEventFilterTrigger?.setAttribute("aria-expanded", "false");

  if (completionEventFilterMenu) {
    completionEventFilterMenu.hidden = true;
  }

  if (blurTrigger) {
    completionEventFilterTrigger?.blur();
  }
}

function openCompletionEventFilterSelect() {
  completionEventFilterSelect?.classList.add("is-open");
  completionEventFilterTrigger?.setAttribute("aria-expanded", "true");

  if (completionEventFilterMenu) {
    completionEventFilterMenu.hidden = false;
  }
}

function closeCompletionUploadEventSelect({ blurTrigger = false } = {}) {
  completionUploadEventSelect?.classList.remove("is-open");
  completionUploadEventTrigger?.setAttribute("aria-expanded", "false");

  if (completionUploadEventMenu) {
    completionUploadEventMenu.hidden = true;
  }

  if (blurTrigger) {
    completionUploadEventTrigger?.blur();
  }
}

function openCompletionUploadEventSelect() {
  completionUploadEventSelect?.classList.add("is-open");
  completionUploadEventTrigger?.setAttribute("aria-expanded", "true");

  if (completionUploadEventMenu) {
    completionUploadEventMenu.hidden = false;
  }
}

completionUploadOpenButton?.addEventListener("click", openCompletionUploadDialog);
completionUploadCancelButton?.addEventListener("click", () => {
  closeCompletionUploadDialog({ confirmUnsaved: true });
});

completionUploadSubmitButton?.addEventListener("click", () => {
  void importSelectedCompletionCsvFile();
});

completionUploadFileInput?.addEventListener("change", updateCompletionUploadFileName);

completionUploadEventTrigger?.addEventListener("click", () => {
  if (completionUploadEventSelect?.classList.contains("is-open")) {
    closeCompletionUploadEventSelect({ blurTrigger: true });
    return;
  }

  openCompletionUploadEventSelect();
});

completionUploadEventTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openCompletionUploadEventSelect();
    completionUploadEventOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeCompletionUploadEventSelect({ blurTrigger: true });
  }
});

completionBulkDownloadableButton?.addEventListener("click", () => {
  applyDownloadableStateToCurrentActivity(true);
});

completionBulkBlockedButton?.addEventListener("click", () => {
  applyDownloadableStateToCurrentActivity(false);
});

completionFilterForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  applyCompletionFilters();
});

completionEventFilterTrigger?.addEventListener("click", () => {
  if (completionEventFilterSelect?.classList.contains("is-open")) {
    closeCompletionEventFilterSelect({ blurTrigger: true });
    return;
  }

  openCompletionEventFilterSelect();
});

completionEventFilterTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openCompletionEventFilterSelect();
    completionEventFilterOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeCompletionEventFilterSelect({ blurTrigger: true });
  }
});

completionEventFilterOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyCompletionEventFilterValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeCompletionEventFilterSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeCompletionEventFilterSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      completionEventFilterOptions[(index + 1) % completionEventFilterOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      completionEventFilterOptions[
        (index - 1 + completionEventFilterOptions.length) % completionEventFilterOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeCompletionEventFilterSelect();
    }
  });
});

completionUploadEventOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyCompletionUploadEventValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeCompletionUploadEventSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeCompletionUploadEventSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      completionUploadEventOptions[(index + 1) % completionUploadEventOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      completionUploadEventOptions[
        (index - 1 + completionUploadEventOptions.length) % completionUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeCompletionUploadEventSelect();
    }
  });
});

completionUploadDialog?.addEventListener("click", (event) => {
  if (event.target === completionUploadDialog) {
    closeCompletionUploadDialog({ confirmUnsaved: true });
  }
});

document.addEventListener("click", (event) => {
  if (
    completionEventFilterSelect instanceof HTMLElement &&
    !completionEventFilterSelect.contains(event.target)
  ) {
    closeCompletionEventFilterSelect();
  }

  if (
    completionUploadEventSelect instanceof HTMLElement &&
    !completionUploadEventSelect.contains(event.target)
  ) {
    closeCompletionUploadEventSelect();
  }
});

window.addEventListener("message", (event) => {
  const message = event.data;
  if (event.origin !== window.location.origin || typeof message !== "object" || message === null) {
    return;
  }

  if (message.type === completionUploadImportMessageType && typeof message.csvText === "string") {
    importCompletionCsvText(
      message.csvText,
      typeof message.eventName === "string" ? message.eventName : defaultCompletionEventName
    );
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && completionUploadDialog && !completionUploadDialog.hidden) {
    closeCompletionUploadDialog({ confirmUnsaved: true });
  }
});

renderCompletionCertRows();
