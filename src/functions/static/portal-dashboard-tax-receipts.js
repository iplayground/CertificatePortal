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
let taxUploadEventSelect = document.getElementById("tax-upload-event-select");
let taxUploadEventTrigger = document.getElementById("tax-upload-event-trigger");
let taxUploadEventValue = document.getElementById("tax-upload-event-value");
let taxUploadEventMenu = document.getElementById("tax-upload-event-options");
let taxUploadEventOptions = Array.from(
  document.querySelectorAll("#tax-upload-event-options .custom-select-option")
);
const taxReceiptTableBody = document.getElementById("tax-receipt-table-body");
const taxReceiptEmptyRow = document.getElementById("tax-receipt-empty-row");
const taxReceiptRowTemplate = document.getElementById("tax-receipt-row-template");
const taxFilterForm = document.querySelector(".document-filter-form");
const taxEventFilter = document.getElementById("tax-event-filter");
let taxEventFilterSelect = document.getElementById("tax-event-filter-select");
let taxEventFilterTrigger = document.getElementById("tax-event-filter-trigger");
let taxEventFilterValue = document.getElementById("tax-event-filter-value");
let taxEventFilterMenu = document.getElementById("tax-event-filter-options");
let taxEventFilterOptions = Array.from(
  document.querySelectorAll("#tax-event-filter-options .custom-select-option")
);
const taxReceiptUploadOpenMessageType = "ipg:tax-receipt-upload:open";
const taxReceiptUploadImportMessageType = "ipg:tax-receipt-upload:import";
const adminEventsApiPath = "/api/v1/admin/events";
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
let taxEventsSignature = "";

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

function normalizeTaxEvent(eventData) {
  return {
    id: typeof eventData?.id === "string" ? eventData.id : "",
    name: typeof eventData?.name === "string" ? eventData.name.trim() : "",
  };
}

function getTaxEventValue(eventData) {
  return eventData.id;
}

function getTaxEventLabel(eventData) {
  return eventData.name || eventData.id || "未命名活動";
}

function resolveTaxEventLabel(options, eventId) {
  const selectedOption = options.find((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    return optionValue === eventId;
  });
  return selectedOption?.textContent?.trim() || eventId || emptyTaxEventName;
}

function buildTaxEventOption(eventData, index, applyValue, closeSelect, optionListRef) {
  const option = document.createElement("button");
  option.className = `custom-select-option${index === 0 ? " is-selected" : ""}`;
  option.type = "button";
  option.setAttribute("role", "option");
  option.dataset.value = getTaxEventValue(eventData);
  option.setAttribute("aria-selected", String(index === 0));
  option.textContent = getTaxEventLabel(eventData);

  option.addEventListener("click", () => {
    applyValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    const optionList = optionListRef();
    if (event.key === "Escape") {
      event.preventDefault();
      closeSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      optionList[(index + 1) % optionList.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      optionList[(index - 1 + optionList.length) % optionList.length]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeSelect();
    }
  });

  return option;
}

function buildTaxEventSelect({
  describedBy,
  isSingleOption = false,
  menuId,
  selectId,
  triggerId,
  valueId,
}) {
  const select = document.createElement("div");
  select.className = `custom-select${isSingleOption ? " is-single-option" : ""}`;
  select.id = selectId;

  const trigger = document.createElement("button");
  trigger.className = "custom-select-trigger";
  trigger.id = triggerId;
  trigger.type = "button";
  if (isSingleOption) {
    trigger.setAttribute("aria-disabled", "true");
    trigger.setAttribute("tabindex", "-1");
  } else {
    trigger.setAttribute("aria-haspopup", "listbox");
  }
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-labelledby", describedBy);

  const value = document.createElement("span");
  value.className = "custom-select-value";
  value.id = valueId;
  value.textContent = emptyTaxEventName;

  const menu = document.createElement("div");
  menu.className = "custom-select-menu";
  menu.id = menuId;
  menu.role = "listbox";
  menu.hidden = true;

  trigger.append(value);
  if (!isSingleOption) {
    const caret = document.createElement("span");
    caret.className = "select-caret";
    caret.setAttribute("aria-hidden", "true");
    trigger.append(caret);
  }
  select.append(trigger, menu);
  return { menu, select, trigger, value };
}

function renderTaxEventSelects(events) {
  if (!(taxEventFilter instanceof HTMLInputElement)) {
    return;
  }

  const normalizedEvents = events
    .map((eventData) => normalizeTaxEvent(eventData))
    .filter((eventData) => getTaxEventValue(eventData));
  const nextEventsSignature = JSON.stringify(normalizedEvents);

  if (nextEventsSignature === taxEventsSignature) {
    return;
  }

  taxEventsSignature = nextEventsSignature;

  if (normalizedEvents.length === 0) {
    if (taxEventFilterValue) {
      taxEventFilterValue.textContent = emptyTaxEventName;
    }
    if (taxUploadEventValue) {
      taxUploadEventValue.textContent = emptyTaxEventName;
    }
    taxEventFilter.value = "";
    if (taxUploadEvent instanceof HTMLInputElement) {
      taxUploadEvent.value = "";
    }
    renderTaxReceiptRows();
    return;
  }

  const firstEventValue = getTaxEventValue(normalizedEvents[0] ?? {});
  const currentEventValue = getTaxFilterEventName();
  const nextEventValue = normalizedEvents.some(
    (eventData) => getTaxEventValue(eventData) === currentEventValue
  )
    ? currentEventValue
    : firstEventValue;
  const isSingleOption = normalizedEvents.length === 1;

  const filterSelect = buildTaxEventSelect({
    describedBy: "tax-event-filter-label tax-event-filter-value",
    isSingleOption,
    menuId: "tax-event-filter-options",
    selectId: "tax-event-filter-select",
    triggerId: "tax-event-filter-trigger",
    valueId: "tax-event-filter-value",
  });
  taxEventFilterValue?.replaceWith(filterSelect.select);
  taxEventFilterSelect = filterSelect.select;
  taxEventFilterTrigger = filterSelect.trigger;
  taxEventFilterValue = filterSelect.value;
  taxEventFilterMenu = filterSelect.menu;
  taxEventFilterOptions = normalizedEvents.map((eventData, index) =>
    buildTaxEventOption(
      eventData,
      index,
      applyTaxEventFilterValue,
      closeTaxEventFilterSelect,
      () => taxEventFilterOptions
    )
  );
  taxEventFilterMenu.replaceChildren(...taxEventFilterOptions);

  const uploadSelect = buildTaxEventSelect({
    describedBy: "tax-upload-event-label tax-upload-event-value",
    isSingleOption,
    menuId: "tax-upload-event-options",
    selectId: "tax-upload-event-select",
    triggerId: "tax-upload-event-trigger",
    valueId: "tax-upload-event-value",
  });
  taxUploadEventValue?.replaceWith(uploadSelect.select);
  taxUploadEventSelect = uploadSelect.select;
  taxUploadEventTrigger = uploadSelect.trigger;
  taxUploadEventValue = uploadSelect.value;
  taxUploadEventMenu = uploadSelect.menu;
  taxUploadEventOptions = normalizedEvents.map((eventData, index) =>
    buildTaxEventOption(
      eventData,
      index,
      applyTaxUploadEventValue,
      closeTaxUploadEventSelect,
      () => taxUploadEventOptions
    )
  );
  taxUploadEventMenu.replaceChildren(...taxUploadEventOptions);

  taxEventFilterTrigger.addEventListener("click", toggleTaxEventFilterSelect);
  taxEventFilterTrigger.addEventListener("keydown", handleTaxEventFilterTriggerKeydown);
  taxUploadEventTrigger.addEventListener("click", toggleTaxUploadEventSelect);
  taxUploadEventTrigger.addEventListener("keydown", handleTaxUploadEventTriggerKeydown);

  applyTaxEventFilterValue(nextEventValue);
  applyTaxUploadEventValue(nextEventValue);
}

async function loadTaxEvents() {
  const eventCache = window.iPlaygroundPortalEvents;
  const cachedEvents = eventCache?.getCachedEvents?.();
  let cachedEventsSignature = "";

  if (Array.isArray(cachedEvents)) {
    cachedEventsSignature = JSON.stringify(
      cachedEvents
        .map((eventData) => normalizeTaxEvent(eventData))
        .filter((eventData) => getTaxEventValue(eventData))
    );
    renderTaxEventSelects(cachedEvents);
  }

  try {
    const response = await fetch(adminEventsApiPath, {
      headers: {
        Accept: "application/json",
      },
    });
    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "活動清單載入失敗。");
    }

    const events = Array.isArray(responsePayload.events) ? responsePayload.events : [];
    eventCache?.setCachedEvents?.(events);
    const refreshedEventsSignature = JSON.stringify(
      events
        .map((eventData) => normalizeTaxEvent(eventData))
        .filter((eventData) => getTaxEventValue(eventData))
    );
    if (refreshedEventsSignature !== cachedEventsSignature) {
      renderTaxEventSelects(events);
    }
  } catch (error) {
    if (Array.isArray(cachedEvents)) {
      return;
    }
    if (taxEventFilterValue) {
      taxEventFilterValue.textContent =
        error instanceof Error ? error.message : "活動清單載入失敗。";
    }
    if (taxUploadEventValue) {
      taxUploadEventValue.textContent = "活動清單載入失敗。";
    }
  }
}

function applyTaxUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultTaxEventName;

  if (taxUploadEvent instanceof HTMLInputElement) {
    taxUploadEvent.value = normalizedValue;
  }

  if (taxUploadEventValue) {
    taxUploadEventValue.textContent = resolveTaxEventLabel(taxUploadEventOptions, normalizedValue);
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
    taxEventFilterValue.textContent = resolveTaxEventLabel(taxEventFilterOptions, normalizedValue);
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

function toggleTaxEventFilterSelect() {
  if (taxEventFilterOptions.length <= 1) {
    closeTaxEventFilterSelect({ blurTrigger: true });
    return;
  }

  if (taxEventFilterSelect?.classList.contains("is-open")) {
    closeTaxEventFilterSelect({ blurTrigger: true });
    return;
  }

  openTaxEventFilterSelect();
}

function handleTaxEventFilterTriggerKeydown(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (taxEventFilterOptions.length <= 1) {
      return;
    }
    openTaxEventFilterSelect();
    taxEventFilterOptions[0]?.focus();
    return;
  }

  if (event.key === "Escape") {
    closeTaxEventFilterSelect({ blurTrigger: true });
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

function toggleTaxUploadEventSelect() {
  if (taxUploadEventOptions.length <= 1) {
    closeTaxUploadEventSelect({ blurTrigger: true });
    return;
  }

  if (taxUploadEventSelect?.classList.contains("is-open")) {
    closeTaxUploadEventSelect({ blurTrigger: true });
    return;
  }

  openTaxUploadEventSelect();
}

function handleTaxUploadEventTriggerKeydown(event) {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (taxUploadEventOptions.length <= 1) {
      return;
    }
    openTaxUploadEventSelect();
    taxUploadEventOptions[0]?.focus();
    return;
  }

  if (event.key === "Escape") {
    closeTaxUploadEventSelect({ blurTrigger: true });
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

window.addEventListener("ipg:portal-events:updated", (event) => {
  const events = Array.isArray(event.detail?.events) ? event.detail.events : [];
  renderTaxEventSelects(events);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && taxUploadDialog && !taxUploadDialog.hidden) {
    closeTaxUploadDialog({ confirmUnsaved: true });
  }
});

void loadTaxEvents();
renderTaxReceiptRows();
