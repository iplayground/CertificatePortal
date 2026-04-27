const taxUploadOpenButton = document.getElementById("tax-upload-open");
const taxUploadDialog = document.getElementById("tax-upload-dialog");
const taxUploadTitle = document.getElementById("tax-upload-title");
const taxUploadCancelButton = document.getElementById("tax-upload-cancel");
const taxUploadSubmitButton = document.getElementById("tax-upload-submit");
const taxUploadContinueOption = document.getElementById("tax-upload-continue-option");
const taxUploadContinueInput = document.getElementById("tax-upload-continue");
const taxUploadFileInput = document.getElementById("tax-upload-file");
const taxUploadFileName = document.getElementById("tax-upload-file-name");
const taxUploadTaxIdInput = document.getElementById("tax-upload-tax-id");
const taxUploadAmountInput = document.getElementById("tax-upload-amount");
const taxUploadGeneratedAtInput = document.getElementById("tax-upload-generated-at");
const taxUploadEvent = document.getElementById("tax-upload-event");
const taxUploadEventSelect = document.getElementById("tax-upload-event-select");
const taxUploadEventTrigger = document.getElementById("tax-upload-event-trigger");
const taxUploadEventValue = document.getElementById("tax-upload-event-value");
const taxUploadEventMenu = document.getElementById("tax-upload-event-options");
const taxUploadEventOptions = Array.from(
  document.querySelectorAll("#tax-upload-event-options .custom-select-option")
);
const taxReceiptTableBody = document.getElementById("tax-receipt-table-body");
const taxReceiptEmptyRow = document.getElementById("tax-receipt-empty-row");
const taxReceiptRowTemplate = document.getElementById("tax-receipt-row-template");
const taxFilterForm = document.querySelector(".document-filter-form");
const taxEventFilter = document.getElementById("tax-event-filter");
const taxEventFilterSelect = document.getElementById("tax-event-filter-select");
const taxEventFilterTrigger = document.getElementById("tax-event-filter-trigger");
const taxEventFilterValue = document.getElementById("tax-event-filter-value");
const taxEventFilterMenu = document.getElementById("tax-event-filter-options");
const taxEventFilterOptions = Array.from(
  document.querySelectorAll("#tax-event-filter-options .custom-select-option")
);
const taxReceiptUploadOpenMessageType = "ipg:tax-receipt-upload:open";
const taxReceiptUploadImportMessageType = "ipg:tax-receipt-upload:import";
const defaultTaxUploadFileName = "尚未選擇 PDF 或圖檔";
const invalidTaxUploadFileName = "請選擇 PDF、PNG 或 JPG 檔案";
const failedTaxUploadFileName = "檔案讀取失敗";
const defaultTaxEventName = "";
const emptyTaxEventName = "尚無活動資料";
const taxReceiptUploadExtensions = [".pdf", ".png", ".jpg", ".jpeg"];
const taxReceiptUploadMimeTypes = [
  "application/pdf",
  "image/png",
  "image/jpeg",
];

let taxUploadPreviousFocus = null;
let taxUploadDialogMode = "create";
let taxUploadEditingRowId = "";
let taxReceiptRows = [];

const {
  formatCurrentDateTimeInputValue,
  formatUtcIsoDateTimeInputValue,
  installDateTimePicker,
  normalizeDateTimeInputValue,
} = window.iPlaygroundPortalDateTime;

function canRequestParentTaxUploadDialog() {
  return window.parent && window.parent !== window;
}

function buildTaxReceiptMessageData(mode, rowData = {}) {
  return {
    mode,
    receipt: {
      amount: rowData.amount ?? "",
      eventName: rowData.eventName ?? getTaxFilterEventName(),
      fileName: rowData.fileName ?? "",
      generatedAt: rowData.generatedAt ?? "",
      id: rowData.id ?? "",
      taxId: rowData.taxId ?? "",
    },
    type: taxReceiptUploadOpenMessageType,
  };
}

function requestParentTaxUploadDialog(mode = "create", rowData = {}) {
  window.parent.postMessage(buildTaxReceiptMessageData(mode, rowData), window.location.origin);
}

function getTaxFilterEventName() {
  if (taxEventFilter instanceof HTMLInputElement) {
    return taxEventFilter.value;
  }

  return defaultTaxEventName;
}

function getTaxUploadEventName() {
  if (taxUploadEvent instanceof HTMLInputElement) {
    return taxUploadEvent.value || getTaxFilterEventName();
  }

  return getTaxFilterEventName();
}

function applyTaxUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultTaxEventName;

  if (taxUploadEvent instanceof HTMLInputElement) {
    taxUploadEvent.value = normalizedValue;
  }

  if (taxUploadEventValue) {
    taxUploadEventValue.textContent = normalizedValue || emptyTaxEventName;
  }

  taxUploadEventOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function setTaxUploadTextValue(input, value) {
  if (input instanceof HTMLInputElement) {
    input.value = value ?? "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function setTaxUploadDialogMode(mode = "create", rowData = {}) {
  const isEditMode = mode === "edit";
  taxUploadDialogMode = isEditMode ? "edit" : "create";
  taxUploadEditingRowId = isEditMode ? rowData.id ?? "" : "";

  if (taxUploadTitle) {
    taxUploadTitle.textContent = isEditMode ? "修改繳稅證明" : "新增繳稅證明";
  }

  if (taxUploadSubmitButton) {
    taxUploadSubmitButton.textContent = isEditMode ? "儲存變更" : "新增繳稅證明";
  }

  if (taxUploadContinueOption instanceof HTMLElement) {
    taxUploadContinueOption.hidden = isEditMode;
  }

  if (taxUploadContinueInput instanceof HTMLInputElement) {
    taxUploadContinueInput.checked = false;
  }

  if (taxUploadFileInput instanceof HTMLInputElement) {
    taxUploadFileInput.value = "";
  }

  applyTaxUploadEventValue(rowData.eventName ?? getTaxFilterEventName());
  setTaxUploadTextValue(taxUploadTaxIdInput, rowData.taxId ?? "");
  setTaxUploadTextValue(taxUploadAmountInput, rowData.amount ?? "");
  setTaxUploadTextValue(
    taxUploadGeneratedAtInput,
    normalizeDateTimeInputValue(rowData.generatedAt ?? "") || formatCurrentDateTimeInputValue()
  );
  updateTaxUploadFileName(rowData.fileName ?? "");
}

function resetTaxUploadDialog() {
  setTaxUploadDialogMode("create");
}

function hasSelectedTaxUploadFile() {
  return (
    taxUploadFileInput instanceof HTMLInputElement &&
    taxUploadFileInput.files instanceof FileList &&
    taxUploadFileInput.files.length > 0
  );
}

function hasTaxUploadDraft() {
  const hasTextValue = [
    taxUploadTaxIdInput,
    taxUploadAmountInput,
    taxUploadGeneratedAtInput,
  ].some((input) => input instanceof HTMLInputElement && input.value.trim().length > 0);

  return hasTextValue || hasSelectedTaxUploadFile();
}

function isTaxReceiptUploadFile(file) {
  const normalizedName = file.name.toLowerCase();
  return (
    taxReceiptUploadMimeTypes.includes(file.type) ||
    taxReceiptUploadExtensions.some((extension) => normalizedName.endsWith(extension))
  );
}

function updateTaxUploadFileName(currentFileName = "") {
  if (!(taxUploadFileName instanceof HTMLElement)) {
    return;
  }

  if (
    !(taxUploadFileInput instanceof HTMLInputElement) ||
    !(taxUploadFileInput.files instanceof FileList) ||
    taxUploadFileInput.files.length === 0
  ) {
    taxUploadFileName.textContent =
      currentFileName || (taxUploadDialogMode === "edit" ? "未重新選擇檔案" : defaultTaxUploadFileName);
    return;
  }

  const selectedFile = taxUploadFileInput.files[0];
  if (!isTaxReceiptUploadFile(selectedFile)) {
    taxUploadFileInput.value = "";
    taxUploadFileName.textContent = invalidTaxUploadFileName;
    return;
  }

  taxUploadFileName.textContent = selectedFile.name;
}

function getSelectedTaxUploadFile() {
  if (
    !(taxUploadFileInput instanceof HTMLInputElement) ||
    !(taxUploadFileInput.files instanceof FileList) ||
    taxUploadFileInput.files.length === 0
  ) {
    return null;
  }

  return taxUploadFileInput.files[0];
}

function getTaxUploadTextValue(input) {
  return input instanceof HTMLInputElement ? input.value.trim() : "";
}

function shouldContinueTaxUpload() {
  return (
    taxUploadDialogMode === "create" &&
    taxUploadContinueInput instanceof HTMLInputElement &&
    taxUploadContinueInput.checked
  );
}

function resetTaxUploadFieldsForNextFile() {
  const eventName = getTaxUploadEventName();
  setTaxUploadDialogMode("create", { eventName });
  if (taxUploadContinueInput instanceof HTMLInputElement) {
    taxUploadContinueInput.checked = true;
  }
  taxUploadTaxIdInput?.focus();
}

function buildTaxReceiptRow(file, receiptData = {}) {
  const importId = Date.now();
  const fileUrl = URL.createObjectURL(file);

  return {
    amount: receiptData.amount ?? "",
    eventName: receiptData.eventName ?? getTaxUploadEventName(),
    fileName: file.name,
    fileUrl,
    generatedAt: receiptData.generatedAt ?? "",
    id: `tax-receipt-row-${importId}-${Math.random().toString(16).slice(2)}`,
    taxId: receiptData.taxId ?? "",
  };
}

function setTextContent(parent, selector, value) {
  const element = parent.querySelector(selector);
  if (element) {
    element.textContent = value || "-";
  }
}

function getVisibleTaxReceiptRows() {
  const eventName = getTaxFilterEventName();
  return taxReceiptRows.filter((row) => row.eventName === eventName);
}

function revokeTaxReceiptFileUrl(rowData) {
  if (rowData?.fileUrl) {
    URL.revokeObjectURL(rowData.fileUrl);
  }
}

function upsertTaxReceiptFile(file, receiptData = {}) {
  const rowId = receiptData.id ?? receiptData.rowId ?? "";
  const existingRow = rowId ? taxReceiptRows.find((row) => row.id === rowId) : null;

  if (!existingRow) {
    if (!file) {
      return;
    }
    taxReceiptRows = [...taxReceiptRows, buildTaxReceiptRow(file, receiptData)];
    applyTaxEventFilterValue(receiptData.eventName ?? getTaxUploadEventName(), { renderRows: false });
    renderTaxReceiptRows();
    return;
  }

  existingRow.amount = receiptData.amount ?? "";
  existingRow.eventName = receiptData.eventName ?? existingRow.eventName;
  existingRow.generatedAt = receiptData.generatedAt ?? "";
  existingRow.taxId = receiptData.taxId ?? "";

  if (file) {
    revokeTaxReceiptFileUrl(existingRow);
    existingRow.fileName = file.name;
    existingRow.fileUrl = URL.createObjectURL(file);
  }

  applyTaxEventFilterValue(existingRow.eventName, { renderRows: false });
  renderTaxReceiptRows();
}

function downloadTaxReceiptFile(rowData) {
  if (!rowData.fileUrl) {
    return;
  }

  const downloadLink = document.createElement("a");
  downloadLink.href = rowData.fileUrl;
  downloadLink.download = rowData.fileName || "tax-receipt";
  downloadLink.click();
}

function formatTaxGeneratedAt(value) {
  return normalizeDateTimeInputValue(value) || "";
}

function openTaxEditDialog(rowData) {
  if (canRequestParentTaxUploadDialog()) {
    requestParentTaxUploadDialog("edit", rowData);
    return;
  }

  openTaxUploadDialog({ mode: "edit", rowData });
}

function deleteTaxReceiptRow(rowId) {
  const rowData = taxReceiptRows.find((row) => row.id === rowId);
  if (!rowData) {
    return;
  }

  if (!window.confirm("確定要刪除此筆繳稅證明嗎？")) {
    return;
  }

  revokeTaxReceiptFileUrl(rowData);
  taxReceiptRows = taxReceiptRows.filter((row) => row.id !== rowId);
  renderTaxReceiptRows();
}

function renderTaxReceiptRows() {
  if (!taxReceiptTableBody || !(taxReceiptRowTemplate instanceof HTMLTemplateElement)) {
    return;
  }

  taxReceiptTableBody
    .querySelectorAll(".tax-receipt-row")
    .forEach((rowElement) => rowElement.remove());

  const visibleRows = getVisibleTaxReceiptRows();

  if (taxReceiptEmptyRow instanceof HTMLTableRowElement) {
    taxReceiptEmptyRow.hidden = visibleRows.length > 0;
  }

  visibleRows.forEach((rowData) => {
    const rowFragment = taxReceiptRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".tax-receipt-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    setTextContent(rowElement, '[data-field="taxId"]', rowData.taxId);
    setTextContent(rowElement, '[data-field="amount"]', rowData.amount);
    setTextContent(rowElement, '[data-field="generatedAt"]', formatTaxGeneratedAt(rowData.generatedAt));
    setTextContent(rowElement, '[data-field="fileName"]', rowData.fileName);

    const downloadButton = rowElement.querySelector(".document-download-button");
    if (downloadButton instanceof HTMLButtonElement) {
      downloadButton.disabled = !rowData.fileUrl;
      downloadButton.addEventListener("click", () => {
        downloadTaxReceiptFile(rowData);
      });
    }

    const editButton = rowElement.querySelector(".document-edit-button");
    if (editButton instanceof HTMLButtonElement) {
      editButton.addEventListener("click", () => {
        openTaxEditDialog(rowData);
      });
    }

    const deleteButton = rowElement.querySelector(".document-delete-button");
    if (deleteButton instanceof HTMLButtonElement) {
      const rowLabel = rowData.taxId || rowData.fileName || "此筆繳稅證明";
      deleteButton.setAttribute("aria-label", `刪除 ${rowLabel}`);
      deleteButton.addEventListener("click", () => {
        deleteTaxReceiptRow(rowData.id);
      });
    }

    taxReceiptTableBody.append(rowElement);
  });
}

function saveSelectedTaxReceiptFile() {
  const selectedFile = getSelectedTaxUploadFile();
  if (selectedFile && !isTaxReceiptUploadFile(selectedFile)) {
    updateTaxUploadFileName();
    taxUploadFileInput?.focus();
    return;
  }

  if (taxUploadDialogMode === "create" && !selectedFile) {
    updateTaxUploadFileName();
    taxUploadFileInput?.focus();
    return;
  }

  try {
    const shouldKeepDialogOpen = shouldContinueTaxUpload();
    upsertTaxReceiptFile(selectedFile, {
      amount: getTaxUploadTextValue(taxUploadAmountInput),
      eventName: getTaxUploadEventName(),
      generatedAt: formatUtcIsoDateTimeInputValue(getTaxUploadTextValue(taxUploadGeneratedAtInput)),
      id: taxUploadEditingRowId,
      taxId: getTaxUploadTextValue(taxUploadTaxIdInput),
    });
    if (shouldKeepDialogOpen) {
      resetTaxUploadFieldsForNextFile();
      return;
    }
    closeTaxUploadDialog();
  } catch (error) {
    void error;
    if (taxUploadFileName) {
      taxUploadFileName.textContent = failedTaxUploadFileName;
    }
  }
}

function confirmTaxUploadDialogClose() {
  if (!hasTaxUploadDraft()) {
    return true;
  }

  return window.confirm("資料尚未存檔，確定要取消嗎？");
}

function openTaxUploadDialog({ mode = "create", rowData = {} } = {}) {
  if (mode !== "edit" && canRequestParentTaxUploadDialog()) {
    requestParentTaxUploadDialog("create");
    return;
  }

  if (!taxUploadDialog) {
    return;
  }

  taxUploadPreviousFocus = document.activeElement;
  setTaxUploadDialogMode(mode, rowData);
  taxUploadDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  taxUploadTaxIdInput?.focus();
}

function closeTaxUploadDialog({ confirmUnsaved = false } = {}) {
  if (!taxUploadDialog) {
    return;
  }

  if (confirmUnsaved && !confirmTaxUploadDialogClose()) {
    return;
  }

  taxUploadDialog.hidden = true;
  closeTaxUploadEventSelect();
  document.body.classList.remove("has-event-dialog");

  if (taxUploadPreviousFocus instanceof HTMLElement) {
    taxUploadPreviousFocus.focus();
  }
}

function applyTaxEventFilterValue(nextValue, { renderRows = true } = {}) {
  const normalizedValue = nextValue?.trim();
  if (!normalizedValue) {
    return;
  }

  if (taxEventFilter instanceof HTMLInputElement) {
    taxEventFilter.value = normalizedValue;
  }

  if (taxEventFilterValue) {
    taxEventFilterValue.textContent = normalizedValue;
  }

  taxEventFilterOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });

  applyTaxFilters();

  if (renderRows) {
    renderTaxReceiptRows();
  }
}

function applyTaxFilters() {
  const eventName = taxEventFilter instanceof HTMLInputElement ? taxEventFilter.value : "";
  return { eventName };
}

function closeTaxEventFilterSelect({ blurTrigger = false } = {}) {
  taxEventFilterSelect?.classList.remove("is-open");
  taxEventFilterTrigger?.setAttribute("aria-expanded", "false");

  if (taxEventFilterMenu) {
    taxEventFilterMenu.hidden = true;
  }

  if (blurTrigger) {
    taxEventFilterTrigger?.blur();
  }
}

function openTaxEventFilterSelect() {
  if (taxEventFilterOptions.length <= 1) {
    closeTaxEventFilterSelect();
    return;
  }

  taxEventFilterSelect?.classList.add("is-open");
  taxEventFilterTrigger?.setAttribute("aria-expanded", "true");

  if (taxEventFilterMenu) {
    taxEventFilterMenu.hidden = false;
  }
}

function closeTaxUploadEventSelect({ blurTrigger = false } = {}) {
  taxUploadEventSelect?.classList.remove("is-open");
  taxUploadEventTrigger?.setAttribute("aria-expanded", "false");

  if (taxUploadEventMenu) {
    taxUploadEventMenu.hidden = true;
  }

  if (blurTrigger) {
    taxUploadEventTrigger?.blur();
  }
}

function openTaxUploadEventSelect() {
  if (taxUploadEventOptions.length <= 1) {
    closeTaxUploadEventSelect();
    return;
  }

  taxUploadEventSelect?.classList.add("is-open");
  taxUploadEventTrigger?.setAttribute("aria-expanded", "true");

  if (taxUploadEventMenu) {
    taxUploadEventMenu.hidden = false;
  }
}

taxUploadOpenButton?.addEventListener("click", () => {
  openTaxUploadDialog();
});

taxUploadCancelButton?.addEventListener("click", () => {
  closeTaxUploadDialog({ confirmUnsaved: true });
});

installDateTimePicker(taxUploadGeneratedAtInput);

taxUploadSubmitButton?.addEventListener("click", saveSelectedTaxReceiptFile);
taxUploadFileInput?.addEventListener("change", () => {
  updateTaxUploadFileName();
});

taxUploadEventTrigger?.addEventListener("click", () => {
  if (taxUploadEventOptions.length <= 1) {
    return;
  }

  if (taxUploadEventSelect?.classList.contains("is-open")) {
    closeTaxUploadEventSelect({ blurTrigger: true });
    return;
  }

  openTaxUploadEventSelect();
});

taxUploadEventTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (taxUploadEventOptions.length <= 1) {
      return;
    }

    openTaxUploadEventSelect();
    taxUploadEventOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeTaxUploadEventSelect({ blurTrigger: true });
  }
});

taxFilterForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  applyTaxFilters();
});

taxEventFilterTrigger?.addEventListener("click", () => {
  if (taxEventFilterOptions.length <= 1) {
    return;
  }

  if (taxEventFilterSelect?.classList.contains("is-open")) {
    closeTaxEventFilterSelect({ blurTrigger: true });
    return;
  }

  openTaxEventFilterSelect();
});

taxEventFilterTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (taxEventFilterOptions.length <= 1) {
      return;
    }

    openTaxEventFilterSelect();
    taxEventFilterOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeTaxEventFilterSelect({ blurTrigger: true });
  }
});

taxEventFilterOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyTaxEventFilterValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeTaxEventFilterSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeTaxEventFilterSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      taxEventFilterOptions[(index + 1) % taxEventFilterOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      taxEventFilterOptions[
        (index - 1 + taxEventFilterOptions.length) % taxEventFilterOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeTaxEventFilterSelect();
    }
  });
});

taxUploadEventOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyTaxUploadEventValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeTaxUploadEventSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeTaxUploadEventSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      taxUploadEventOptions[(index + 1) % taxUploadEventOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      taxUploadEventOptions[
        (index - 1 + taxUploadEventOptions.length) % taxUploadEventOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeTaxUploadEventSelect();
    }
  });
});

taxUploadDialog?.addEventListener("click", (event) => {
  if (event.target === taxUploadDialog) {
    closeTaxUploadDialog({ confirmUnsaved: true });
  }
});

document.addEventListener("click", (event) => {
  if (taxEventFilterSelect instanceof HTMLElement && !taxEventFilterSelect.contains(event.target)) {
    closeTaxEventFilterSelect();
  }

  if (taxUploadEventSelect instanceof HTMLElement && !taxUploadEventSelect.contains(event.target)) {
    closeTaxUploadEventSelect();
  }
});

window.addEventListener("message", (event) => {
  const message = event.data;
  if (event.origin !== window.location.origin || typeof message !== "object" || message === null) {
    return;
  }

  if (message.type !== taxReceiptUploadImportMessageType) {
    return;
  }

  if (message.file && (!(message.file instanceof File) || !isTaxReceiptUploadFile(message.file))) {
    return;
  }

  upsertTaxReceiptFile(message.file ?? null, {
    amount: typeof message.amount === "string" ? message.amount : "",
    eventName: typeof message.eventName === "string" ? message.eventName : defaultTaxEventName,
    generatedAt: typeof message.generatedAt === "string" ? message.generatedAt : "",
    id: typeof message.rowId === "string" ? message.rowId : "",
    taxId: typeof message.taxId === "string" ? message.taxId : "",
  });
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && taxUploadDialog && !taxUploadDialog.hidden) {
    closeTaxUploadDialog({ confirmUnsaved: true });
  }
});

renderTaxReceiptRows();
