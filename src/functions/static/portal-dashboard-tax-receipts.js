const taxUploadOpenButton = document.getElementById("tax-upload-open");
const taxUploadDialog = document.getElementById("tax-upload-dialog");
const taxUploadTitle = document.getElementById("tax-upload-title");
const taxUploadCancelButton = document.getElementById("tax-upload-cancel");
const taxUploadSubmitButton = document.getElementById("tax-upload-submit");
const taxUploadContinueOption = document.getElementById("tax-upload-continue-option");
const taxUploadContinueInput = document.getElementById("tax-upload-continue");
const taxUploadFileInput = document.getElementById("tax-upload-file");
const taxUploadFileName = document.getElementById("tax-upload-file-name");
const taxUploadErrors = document.getElementById("tax-upload-errors");
const taxUploadDropzone = document.querySelector('label[for="tax-upload-file"]');
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
const taxReceiptPagination = document.getElementById("tax-receipt-pagination");
const taxReceiptPagePrevButton = document.getElementById("tax-receipt-page-prev");
const taxReceiptPageNextButton = document.getElementById("tax-receipt-page-next");
const taxReceiptPageStatus = document.getElementById("tax-receipt-page-status");
const taxFilterForm = document.querySelector(".document-filter-form");
const taxEventFilter = document.getElementById("tax-event-filter");
const taxIdFilter = document.getElementById("tax-id-filter");
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
const adminTaxReceiptsApiPath = "/api/v1/admin/tax-receipts";
const taxReceiptDownloadApiPath = "/api/v1/tax-receipts/download";
const portalCsrfToken = document.body?.dataset.portalCsrfToken || "";
const defaultTaxUploadFileName = "尚未選擇 PDF 或圖檔";
const invalidTaxUploadFileName = "請選擇 PDF、PNG 或 JPG 檔案";
const failedTaxUploadFileName = "檔案讀取失敗";
const defaultTaxEventName = "";
const emptyTaxEventName = "尚無活動資料";
const loadingTaxReceiptRowsMessage = "營業稅繳稅證明資料載入中...";
const emptyTaxReceiptRowsMessage = "尚未新增營業稅繳稅證明。";
const emptyTaxReceiptSearchRowsMessage = "查無符合統編的繳稅證明。";
const downloadingTaxReceiptMessage = "正在準備繳稅證明檔案，請稍候。";
const taxReceiptRowsPerPage = 10;
const invalidTaxUploadTaxIdMessage = "請輸入 8 碼統編。";
const invalidTaxUploadAmountMessage = "請輸入大於 0 的整數金額。";
const invalidTaxUploadGeneratedAtMessage = "請輸入完整產製時間，格式為 YYYY / MM / DD HH:mm:ss。";
const invalidTaxUploadEventMessage = "請先選擇活動。";
const taxReceiptUploadExtensions = [".pdf", ".png", ".jpg", ".jpeg"];
const taxReceiptUploadMimeTypes = [
  "application/pdf",
  "image/png",
  "image/jpeg",
];

let taxUploadPreviousFocus = null;
let taxUploadDialogMode = "create";
let taxUploadEditingRowId = "";
let taxUploadInitialDraftState = null;
let taxReceiptRows = [];
let isLoadingTaxReceiptRows = true;
let taxReceiptRowsMessageOverride = "";
let taxEventsSignature = "";
let taxReceiptCurrentPage = 1;

const {
  formatCurrentDateTimeInputValue,
  formatUtcIsoDateTimeInputValue,
  installDateTimePicker,
  normalizeDateTimeInputValue,
} = window.iPlaygroundPortalDateTime;

function handlePortalUnauthorizedResponse(response) {
  return window.iPlaygroundPortalAuth?.handleUnauthorizedResponse?.(response) === true;
}

async function verifyPortalSession() {
  return window.iPlaygroundPortalAuth?.verifySession?.() ?? true;
}

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

function getTaxIdFilterValue() {
  return taxIdFilter instanceof HTMLInputElement ? taxIdFilter.value.trim() : "";
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
  setTaxUploadEventLocked(taxUploadDialogMode === "edit");
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
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

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

  clearTaxUploadErrors();
}

function setTaxUploadEventLocked(isLocked) {
  if (taxUploadEventTrigger instanceof HTMLButtonElement) {
    taxUploadEventTrigger.disabled = isLocked;
    taxUploadEventTrigger.setAttribute("aria-disabled", String(isLocked));
    taxUploadEventTrigger.title = isLocked ? "活動不可在編輯時修改。" : "";
  }

  taxUploadEventSelect?.classList.toggle("is-disabled", isLocked);

  if (isLocked) {
    closeTaxUploadEventSelect();
  }
}

function getFirstTaxUploadEventValue() {
  const firstOption = taxUploadEventOptions[0];
  return firstOption?.dataset.value ?? firstOption?.textContent?.trim() ?? "";
}

function setTaxUploadTextValue(input, value) {
  if (input instanceof HTMLInputElement) {
    input.value = value ?? "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }
}

function getTaxUploadDraftState() {
  return {
    amount: getTaxUploadTextValue(taxUploadAmountInput),
    eventName: getTaxUploadEventName(),
    generatedAt: getTaxUploadTextValue(taxUploadGeneratedAtInput),
    taxId: getTaxUploadTextValue(taxUploadTaxIdInput),
  };
}

function clearTaxUploadErrors() {
  if (!(taxUploadErrors instanceof HTMLElement)) {
    return;
  }

  taxUploadErrors.replaceChildren();
  taxUploadErrors.hidden = true;
}

function showTaxUploadErrors(errors) {
  if (!(taxUploadErrors instanceof HTMLElement)) {
    return;
  }

  const title = document.createElement("strong");
  title.textContent = "請修正以下欄位後再新增。";
  const list = document.createElement("ul");
  errors.forEach((error) => {
    const item = document.createElement("li");
    item.textContent = error.message;
    list.append(item);
  });
  taxUploadErrors.replaceChildren(title, list);
  taxUploadErrors.hidden = false;
}

function showTaxReceiptPageAlert({ dismissDelay = 3000, message, title, tone }) {
  window.iPlaygroundPageAlert?.show({
    dismissDelay,
    message,
    title,
    tone,
  });
}

function setTaxUploadDialogMode(mode = "create", rowData = {}) {
  const isEditMode = mode === "edit";
  taxUploadDialogMode = isEditMode ? "edit" : "create";
  taxUploadEditingRowId = isEditMode ? rowData.id ?? "" : "";
  taxUploadInitialDraftState = null;

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

  clearTaxUploadErrors();
  if (taxUploadTaxIdInput instanceof HTMLInputElement) {
    taxUploadTaxIdInput.readOnly = isEditMode;
    taxUploadTaxIdInput.setAttribute("aria-readonly", String(isEditMode));
    taxUploadTaxIdInput.title = isEditMode ? "統編不可修改；如需更正請刪除後重新新增。" : "";
  }
  applyTaxUploadEventValue(
    rowData.eventName ||
      getTaxFilterEventName() ||
      getTaxUploadEventName() ||
      getFirstTaxUploadEventValue()
  );
  setTaxUploadEventLocked(isEditMode);
  setTaxUploadTextValue(taxUploadTaxIdInput, rowData.taxId ?? "");
  setTaxUploadTextValue(taxUploadAmountInput, rowData.amount ?? "");
  setTaxUploadTextValue(
    taxUploadGeneratedAtInput,
    normalizeDateTimeInputValue(rowData.generatedAt ?? "", { includeSeconds: true }) ||
      formatCurrentDateTimeInputValue({ includeSeconds: true })
  );
  updateTaxUploadFileName(rowData.fileName ?? "");
  taxUploadInitialDraftState = isEditMode ? getTaxUploadDraftState() : null;
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
  if (taxUploadDialogMode === "edit") {
    if (hasSelectedTaxUploadFile()) {
      return true;
    }

    const currentState = getTaxUploadDraftState();
    return Object.keys(currentState).some(
      (key) => currentState[key] !== taxUploadInitialDraftState?.[key]
    );
  }

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
    showTaxUploadErrors([{ message: invalidTaxUploadFileName, field: taxUploadFileInput }]);
    return;
  }

  clearTaxUploadErrors();
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

function hasDraggedTaxUploadFiles(event) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

function setTaxUploadDragActive(isActive) {
  taxUploadDropzone?.classList.toggle("is-drag-active", isActive);
}

function assignTaxUploadFile(file) {
  if (!(taxUploadFileInput instanceof HTMLInputElement)) {
    return;
  }

  if (!isTaxReceiptUploadFile(file)) {
    taxUploadFileInput.value = "";
    taxUploadFileName.textContent = invalidTaxUploadFileName;
    showTaxUploadErrors([{ message: invalidTaxUploadFileName, field: taxUploadFileInput }]);
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  taxUploadFileInput.files = transfer.files;
  updateTaxUploadFileName();
}

function handleTaxUploadDrag(event) {
  if (taxUploadDialog?.hidden || !hasDraggedTaxUploadFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setTaxUploadDragActive(true);
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function handleTaxUploadDragEnd(event) {
  if (taxUploadDialog?.hidden || !hasDraggedTaxUploadFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setTaxUploadDragActive(false);
}

function handleTaxUploadDrop(event) {
  if (taxUploadDialog?.hidden || !hasDraggedTaxUploadFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setTaxUploadDragActive(false);

  const file = event.dataTransfer?.files?.[0];
  if (file) {
    assignTaxUploadFile(file);
  }
}

function getTaxUploadTextValue(input) {
  return input instanceof HTMLInputElement ? input.value.trim() : "";
}

function isTaxUploadTaxId(value) {
  return /^[0-9]{8}$/.test(value);
}

function isTaxUploadAmount(value) {
  const normalizedValue = value.replace(/,/g, "");
  return (
    /^(?:0|[1-9][0-9]*)$/.test(normalizedValue) &&
    Number(normalizedValue) > 0
  );
}

function getTaxUploadGeneratedAtIso() {
  const normalizedDisplayValue = normalizeDateTimeInputValue(
    getTaxUploadTextValue(taxUploadGeneratedAtInput),
    { includeSeconds: true }
  );
  return normalizedDisplayValue
    ? formatUtcIsoDateTimeInputValue(normalizedDisplayValue)
    : "";
}

function validateTaxUploadForm(selectedFile) {
  const errors = [];
  const taxId = getTaxUploadTextValue(taxUploadTaxIdInput);
  const amount = getTaxUploadTextValue(taxUploadAmountInput);
  const generatedAt = getTaxUploadGeneratedAtIso();

  if (!getTaxUploadEventName()) {
    errors.push({ message: invalidTaxUploadEventMessage, field: taxUploadEventTrigger });
  }

  if (!isTaxUploadTaxId(taxId)) {
    errors.push({ message: invalidTaxUploadTaxIdMessage, field: taxUploadTaxIdInput });
  }

  if (!isTaxUploadAmount(amount)) {
    errors.push({ message: invalidTaxUploadAmountMessage, field: taxUploadAmountInput });
  }

  if (!generatedAt) {
    errors.push({ message: invalidTaxUploadGeneratedAtMessage, field: taxUploadGeneratedAtInput });
  }

  if (selectedFile && !isTaxReceiptUploadFile(selectedFile)) {
    errors.push({ message: invalidTaxUploadFileName, field: taxUploadFileInput });
  }

  if (taxUploadDialogMode === "create" && !selectedFile) {
    errors.push({ message: invalidTaxUploadFileName, field: taxUploadFileInput });
  }

  if (errors.length > 0) {
    showTaxUploadErrors(errors);
    const firstField = errors[0]?.field;
    if (firstField instanceof HTMLElement) {
      firstField.focus();
    }
    return null;
  }

  clearTaxUploadErrors();
  return { amount, generatedAt, taxId };
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
  clearTaxUploadErrors();
  taxUploadTaxIdInput?.focus();
}

function normalizeTaxReceiptRow(rowData) {
  return {
    amount:
      typeof rowData?.amount === "number" || typeof rowData?.amount === "string"
        ? String(rowData.amount)
        : "",
    contentType: typeof rowData?.contentType === "string" ? rowData.contentType : "",
    eventName: typeof rowData?.eventId === "string" ? rowData.eventId : "",
    fileName: typeof rowData?.fileName === "string" ? rowData.fileName : "",
    fileSize: typeof rowData?.fileSize === "number" ? rowData.fileSize : 0,
    generatedAt: typeof rowData?.generatedAt === "string" ? rowData.generatedAt : "",
    id: typeof rowData?.id === "string" ? rowData.id : "",
    taxId: typeof rowData?.taxId === "string" ? rowData.taxId : "",
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
  const taxIdQuery = getTaxIdFilterValue();
  return taxReceiptRows.filter((row) => {
    if (row.eventName !== eventName) {
      return false;
    }
    if (!taxIdQuery) {
      return true;
    }
    return row.taxId.includes(taxIdQuery);
  });
}

function getTaxReceiptPageCount(rowCount = getVisibleTaxReceiptRows().length) {
  return Math.max(1, Math.ceil(rowCount / taxReceiptRowsPerPage));
}

function clampTaxReceiptCurrentPage(rowCount = getVisibleTaxReceiptRows().length) {
  taxReceiptCurrentPage = Math.min(
    Math.max(1, taxReceiptCurrentPage),
    getTaxReceiptPageCount(rowCount)
  );
}

function getCurrentTaxReceiptPageRows(visibleRows) {
  clampTaxReceiptCurrentPage(visibleRows.length);
  const startIndex = (taxReceiptCurrentPage - 1) * taxReceiptRowsPerPage;
  return visibleRows.slice(startIndex, startIndex + taxReceiptRowsPerPage);
}

function buildTaxReceiptIdempotencyKey() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readTaxReceiptFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      resolve("");
      return;
    }

    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    });
    reader.addEventListener("error", () => {
      reject(new Error(failedTaxUploadFileName));
    });
    reader.readAsDataURL(file);
  });
}

async function buildTaxReceiptRequestPayload(file, receiptData) {
  const payload = {
    amount: receiptData.amount,
    eventId: receiptData.eventName,
    generatedAt: receiptData.generatedAt,
    taxId: receiptData.taxId,
  };

  if (file) {
    payload.contentType = file.type || resolveTaxReceiptContentType(file.name);
    payload.fileBase64 = await readTaxReceiptFileAsBase64(file);
    payload.fileName = file.name;
  }

  return payload;
}

function resolveTaxReceiptContentType(fileName) {
  const normalizedName = fileName.toLowerCase();
  if (normalizedName.endsWith(".pdf")) {
    return "application/pdf";
  }
  if (normalizedName.endsWith(".png")) {
    return "image/png";
  }
  return "image/jpeg";
}

async function saveTaxReceiptFile(file, receiptData = {}) {
  const rowId = receiptData.id ?? receiptData.rowId ?? "";
  const payload = await buildTaxReceiptRequestPayload(file, receiptData);
  const url = rowId ? `${adminTaxReceiptsApiPath}/${encodeURIComponent(rowId)}` : adminTaxReceiptsApiPath;
  const headers = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-Portal-CSRF-Token": portalCsrfToken,
  };
  if (!rowId) {
    headers["Idempotency-Key"] = buildTaxReceiptIdempotencyKey();
  }

  const response = await fetch(url, {
    method: rowId ? "PUT" : "POST",
    headers,
    body: JSON.stringify(payload),
  });
  if (handlePortalUnauthorizedResponse(response)) {
    return null;
  }

  const responsePayload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(responsePayload?.error?.message || "繳稅證明儲存失敗。");
  }

  return normalizeTaxReceiptRow(responsePayload.taxReceipt ?? {});
}

function upsertTaxReceiptRow(rowData) {
  if (!rowData?.id) {
    return;
  }

  const existingIndex = taxReceiptRows.findIndex((row) => row.id === rowData.id);
  if (existingIndex < 0) {
    taxReceiptRows = [rowData, ...taxReceiptRows];
  } else {
    taxReceiptRows = taxReceiptRows.map((row, index) =>
      index === existingIndex ? rowData : row
    );
  }
  applyTaxEventFilterValue(rowData.eventName, { renderRows: false });
  renderTaxReceiptRows();
}

function buildPendingTaxReceiptRow(receiptData = {}, file = null) {
  return {
    amount: receiptData.amount ?? "",
    eventName: receiptData.eventName ?? defaultTaxEventName,
    fileName: file?.name ?? "",
    generatedAt: receiptData.generatedAt ?? "",
    id: `pending_${Date.now()}_${Math.random().toString(36).slice(2)}`,
    isPending: true,
    taxId: receiptData.taxId ?? "",
  };
}

function insertPendingTaxReceiptRow(rowData) {
  if (!rowData?.id) {
    return;
  }

  taxReceiptRows = [rowData, ...taxReceiptRows];
  applyTaxEventFilterValue(rowData.eventName, { renderRows: false });
  renderTaxReceiptRows();
}

function replacePendingTaxReceiptRow(pendingRowId, savedRow) {
  if (!pendingRowId || !savedRow?.id) {
    return;
  }

  taxReceiptRows = taxReceiptRows.map((rowData) =>
    rowData.id === pendingRowId ? savedRow : rowData
  );
  applyTaxEventFilterValue(savedRow.eventName, { renderRows: false });
  renderTaxReceiptRows();
}

function removePendingTaxReceiptRow(pendingRowId) {
  if (!pendingRowId) {
    return;
  }

  taxReceiptRows = taxReceiptRows.filter((rowData) => rowData.id !== pendingRowId);
  renderTaxReceiptRows();
}

function setTaxReceiptEmptyMessage(message) {
  const emptyCell = taxReceiptEmptyRow?.querySelector("td");
  if (emptyCell) {
    emptyCell.textContent = message;
  }
}

async function loadTaxReceiptRows(eventId = getTaxFilterEventName()) {
  if (!eventId) {
    taxReceiptRows = [];
    isLoadingTaxReceiptRows = false;
    renderTaxReceiptRows();
    return;
  }

  isLoadingTaxReceiptRows = true;
  taxReceiptRowsMessageOverride = "";
  taxReceiptRows = taxReceiptRows.filter((rowData) => rowData.eventName !== eventId || rowData.isPending);
  renderTaxReceiptRows();

  try {
    const response = await fetch(
      `${adminTaxReceiptsApiPath}?eventId=${encodeURIComponent(eventId)}`,
      { headers: { Accept: "application/json" } }
    );
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "繳稅證明清單載入失敗。");
    }

    const rows = Array.isArray(responsePayload.taxReceipts)
      ? responsePayload.taxReceipts.map((rowData) => normalizeTaxReceiptRow(rowData))
      : [];
    taxReceiptCurrentPage = 1;
    taxReceiptRows = [
      ...taxReceiptRows.filter((rowData) => rowData.eventName !== eventId || rowData.isPending),
      ...rows,
    ];
    taxReceiptRowsMessageOverride = "";
  } catch (error) {
    taxReceiptRowsMessageOverride =
      error instanceof Error ? error.message : "繳稅證明清單載入失敗。";
  } finally {
    isLoadingTaxReceiptRows = false;
    renderTaxReceiptRows();
  }
}

function resolveTaxReceiptDownloadFilename(response, rowData) {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  return match?.[1] || rowData.fileName || "tax-receipt";
}

function downloadTaxReceiptBlob(fileBlob, filename) {
  const objectUrl = window.URL.createObjectURL(fileBlob);
  const downloadLink = document.createElement("a");
  downloadLink.href = objectUrl;
  downloadLink.download = filename;
  document.body.append(downloadLink);
  downloadLink.click();
  downloadLink.remove();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl);
  }, 1000);
}

function setTaxReceiptDownloadButtonBusy(downloadButton, isBusy) {
  const label = downloadButton.querySelector("span:last-child");
  if (label) {
    label.textContent = isBusy ? "下載中..." : "下載";
  }
  downloadButton.setAttribute("aria-busy", String(isBusy));
}

function updateTaxReceiptPaginationControls(visibleRows) {
  const rowCount = visibleRows.length;
  const pageCount = getTaxReceiptPageCount(rowCount);
  const shouldShowPagination = rowCount > taxReceiptRowsPerPage;

  if (taxReceiptPagination instanceof HTMLElement) {
    taxReceiptPagination.hidden = !shouldShowPagination;
  }

  if (taxReceiptPageStatus instanceof HTMLElement) {
    taxReceiptPageStatus.textContent = `第 ${taxReceiptCurrentPage} / ${pageCount} 頁`;
  }

  if (taxReceiptPagePrevButton instanceof HTMLButtonElement) {
    taxReceiptPagePrevButton.disabled = !shouldShowPagination || taxReceiptCurrentPage <= 1;
  }

  if (taxReceiptPageNextButton instanceof HTMLButtonElement) {
    taxReceiptPageNextButton.disabled = !shouldShowPagination || taxReceiptCurrentPage >= pageCount;
  }
}

async function downloadTaxReceiptFile(rowData) {
  if (!rowData.id || !rowData.eventName) {
    return;
  }

  const response = await fetch(
    taxReceiptDownloadApiPath,
    {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: `${rowData.contentType || "application/octet-stream"}, application/json`,
        "Content-Type": "application/json",
        "X-Portal-CSRF-Token": portalCsrfToken,
      },
      body: JSON.stringify({ eventId: rowData.eventName, receiptIds: [rowData.id] }),
    },
  );
  if (handlePortalUnauthorizedResponse(response)) {
    return;
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload?.error?.message || "繳稅證明下載失敗。");
  }

  const fileBlob = await response.blob();
  downloadTaxReceiptBlob(fileBlob, resolveTaxReceiptDownloadFilename(response, rowData));
}

function formatTaxGeneratedAt(value) {
  return normalizeDateTimeInputValue(value, { includeSeconds: true }) || "";
}

async function openTaxEditDialog(rowData) {
  if (!(await verifyPortalSession())) {
    return;
  }

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

  void deleteTaxReceiptFile(rowData);
}

async function deleteTaxReceiptFile(rowData) {
  try {
    const response = await fetch(
      `${adminTaxReceiptsApiPath}/${encodeURIComponent(rowData.id)}?eventId=${encodeURIComponent(rowData.eventName)}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
          "X-Portal-CSRF-Token": portalCsrfToken,
        },
      }
    );
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }
    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "繳稅證明刪除失敗。");
    }
    taxReceiptRows = taxReceiptRows.filter((row) => row.id !== rowData.id);
    renderTaxReceiptRows();
    showTaxReceiptPageAlert({
      message: "繳稅證明資料已刪除。",
      title: "刪除成功",
      tone: "success",
    });
  } catch (error) {
    showTaxUploadErrors([
      { message: error instanceof Error ? error.message : "繳稅證明刪除失敗。" },
    ]);
  }
}

function renderTaxReceiptRows() {
  if (!taxReceiptTableBody || !(taxReceiptRowTemplate instanceof HTMLTemplateElement)) {
    return;
  }

  taxReceiptTableBody
    .querySelectorAll(".tax-receipt-row")
    .forEach((rowElement) => rowElement.remove());

  const visibleRows = getVisibleTaxReceiptRows();
  const pageRows = getCurrentTaxReceiptPageRows(visibleRows);
  updateTaxReceiptPaginationControls(visibleRows);

  if (taxReceiptEmptyRow instanceof HTMLTableRowElement) {
    taxReceiptEmptyRow.hidden = visibleRows.length > 0;
    setTaxReceiptEmptyMessage(
      taxReceiptRowsMessageOverride ||
      (isLoadingTaxReceiptRows
        ? loadingTaxReceiptRowsMessage
        : getTaxIdFilterValue()
          ? emptyTaxReceiptSearchRowsMessage
          : emptyTaxReceiptRowsMessage)
    );
  }

  pageRows.forEach((rowData) => {
    const rowFragment = taxReceiptRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".tax-receipt-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    rowElement.classList.toggle("is-disabled", Boolean(rowData.isPending));
    if (rowData.isPending) {
      rowElement.setAttribute("aria-disabled", "true");
      rowElement.title = "檔案正在新增中";
    }
    setTextContent(rowElement, '[data-field="taxId"]', rowData.taxId);
    setTextContent(rowElement, '[data-field="amount"]', rowData.amount);
    setTextContent(rowElement, '[data-field="generatedAt"]', formatTaxGeneratedAt(rowData.generatedAt));

    const downloadButton = rowElement.querySelector(".document-download-button");
    if (downloadButton instanceof HTMLButtonElement) {
      downloadButton.disabled = Boolean(rowData.isPending) || !rowData.id;
      downloadButton.addEventListener("click", async () => {
        downloadButton.disabled = true;
        setTaxReceiptDownloadButtonBusy(downloadButton, true);
        showTaxReceiptPageAlert({
          dismissDelay: -1,
          message: downloadingTaxReceiptMessage,
          title: "下載中",
          tone: "info",
        });
        try {
          await downloadTaxReceiptFile(rowData);
          showTaxReceiptPageAlert({
            message: "檔案已開始下載。",
            title: "下載已開始",
            tone: "success",
          });
        } catch (error) {
          showTaxReceiptPageAlert({
            message: error instanceof Error ? error.message : "繳稅證明下載失敗。",
            title: "下載失敗",
            tone: "error",
          });
        } finally {
          setTaxReceiptDownloadButtonBusy(downloadButton, false);
          downloadButton.disabled = Boolean(rowData.isPending) || !rowData.id;
        }
      });
    }

    const editButton = rowElement.querySelector(".document-edit-button");
    if (editButton instanceof HTMLButtonElement) {
      editButton.disabled = Boolean(rowData.isPending);
      editButton.addEventListener("click", () => {
        void openTaxEditDialog(rowData);
      });
    }

    const deleteButton = rowElement.querySelector(".document-delete-button");
    if (deleteButton instanceof HTMLButtonElement) {
      deleteButton.disabled = Boolean(rowData.isPending);
      const rowLabel = rowData.taxId || rowData.fileName || "此筆繳稅證明";
      deleteButton.setAttribute("aria-label", `刪除 ${rowLabel}`);
      deleteButton.addEventListener("click", () => {
        deleteTaxReceiptRow(rowData.id);
      });
    }

    taxReceiptTableBody.append(rowElement);
  });
}

async function saveSelectedTaxReceiptFile() {
  const selectedFile = getSelectedTaxUploadFile();
  const validatedData = validateTaxUploadForm(selectedFile);
  if (!validatedData) {
    return;
  }

  let pendingRow = null;
  try {
    const shouldKeepDialogOpen = shouldContinueTaxUpload();
    pendingRow =
      taxUploadDialogMode === "create"
        ? buildPendingTaxReceiptRow(
            {
              amount: validatedData.amount,
              eventName: getTaxUploadEventName(),
              generatedAt: validatedData.generatedAt,
              taxId: validatedData.taxId,
            },
            selectedFile
          )
        : null;
    if (pendingRow) {
      insertPendingTaxReceiptRow(pendingRow);
    }
    const savedRow = await saveTaxReceiptFile(selectedFile, {
      amount: validatedData.amount,
      eventName: getTaxUploadEventName(),
      generatedAt: validatedData.generatedAt,
      id: taxUploadEditingRowId,
      taxId: validatedData.taxId,
    });
    if (savedRow) {
      if (pendingRow) {
        replacePendingTaxReceiptRow(pendingRow.id, savedRow);
      } else {
        upsertTaxReceiptRow(savedRow);
      }
      showTaxReceiptPageAlert({
        message:
          taxUploadDialogMode === "edit"
            ? "繳稅證明資料已更新。"
            : "繳稅證明資料已新增。",
        title: taxUploadDialogMode === "edit" ? "更新成功" : "新增成功",
        tone: "success",
      });
    }
    if (shouldKeepDialogOpen) {
      resetTaxUploadFieldsForNextFile();
      return;
    }
    closeTaxUploadDialog();
  } catch (error) {
    removePendingTaxReceiptRow(pendingRow?.id ?? "");
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

async function openTaxUploadDialog({ mode = "create", rowData = {} } = {}) {
  if (!(await verifyPortalSession())) {
    return;
  }

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
    void loadTaxReceiptRows(normalizedValue);
  }
}

function applyTaxFilters() {
  const eventName = taxEventFilter instanceof HTMLInputElement ? taxEventFilter.value : "";
  const taxId = getTaxIdFilterValue();
  taxReceiptCurrentPage = 1;
  renderTaxReceiptRows();
  return { eventName, taxId };
}

function goToTaxReceiptPage(nextPage) {
  taxReceiptCurrentPage = nextPage;
  clampTaxReceiptCurrentPage();
  renderTaxReceiptRows();
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
  void openTaxUploadDialog();
});

taxUploadCancelButton?.addEventListener("click", () => {
  closeTaxUploadDialog({ confirmUnsaved: true });
});

installDateTimePicker(taxUploadGeneratedAtInput, { includeSeconds: true });

taxUploadSubmitButton?.addEventListener("click", saveSelectedTaxReceiptFile);
taxUploadFileInput?.addEventListener("change", () => {
  updateTaxUploadFileName();
});
["dragenter", "dragover"].forEach((eventName) => {
  document.addEventListener(eventName, handleTaxUploadDrag);
});
["dragleave", "dragend"].forEach((eventName) => {
  document.addEventListener(eventName, handleTaxUploadDragEnd);
});
document.addEventListener("drop", handleTaxUploadDrop);
taxUploadTaxIdInput?.addEventListener("input", clearTaxUploadErrors);
taxUploadAmountInput?.addEventListener("input", clearTaxUploadErrors);
taxUploadGeneratedAtInput?.addEventListener("input", clearTaxUploadErrors);

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

taxIdFilter?.addEventListener("input", () => {
  applyTaxFilters();
});

taxReceiptPagePrevButton?.addEventListener("click", () => {
  goToTaxReceiptPage(taxReceiptCurrentPage - 1);
});

taxReceiptPageNextButton?.addEventListener("click", () => {
  goToTaxReceiptPage(taxReceiptCurrentPage + 1);
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

  const receiptData = {
    amount: typeof message.amount === "string" ? message.amount : "",
    eventName: typeof message.eventName === "string" ? message.eventName : defaultTaxEventName,
    generatedAt: typeof message.generatedAt === "string" ? message.generatedAt : "",
    id: typeof message.rowId === "string" ? message.rowId : "",
    taxId: typeof message.taxId === "string" ? message.taxId : "",
  };
  const pendingRow = receiptData.id ? null : buildPendingTaxReceiptRow(receiptData, message.file ?? null);
  if (pendingRow) {
    insertPendingTaxReceiptRow(pendingRow);
  }

  void saveTaxReceiptFile(message.file ?? null, receiptData).then((savedRow) => {
    if (savedRow) {
      if (pendingRow) {
        replacePendingTaxReceiptRow(pendingRow.id, savedRow);
      } else {
        upsertTaxReceiptRow(savedRow);
      }
      showTaxReceiptPageAlert({
        message: message.rowId ? "繳稅證明資料已更新。" : "繳稅證明資料已新增。",
        title: message.rowId ? "更新成功" : "新增成功",
        tone: "success",
      });
    }
  }).catch((error) => {
    removePendingTaxReceiptRow(pendingRow?.id ?? "");
    showTaxUploadErrors([
      { message: error instanceof Error ? error.message : "繳稅證明儲存失敗。" },
    ]);
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
