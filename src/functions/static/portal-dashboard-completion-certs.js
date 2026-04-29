const completionUploadOpenButton = document.getElementById("completion-upload-open");
const completionUploadDialog = document.getElementById("completion-upload-dialog");
const completionUploadCancelButton = document.getElementById("completion-upload-cancel");
const completionUploadSubmitButton = document.getElementById("completion-upload-submit");
const completionUploadFileInput = document.getElementById("completion-upload-file");
const completionUploadFileName = document.getElementById("completion-upload-file-name");
const completionUploadErrors = document.getElementById("completion-upload-errors");
const completionUploadDropzone = document.querySelector(
  'label[for="completion-upload-file"]'
);
const completionUploadEvent = document.getElementById("completion-upload-event");
let completionUploadEventSelect = document.getElementById("completion-upload-event-select");
let completionUploadEventTrigger = document.getElementById(
  "completion-upload-event-trigger"
);
let completionUploadEventValue = document.getElementById("completion-upload-event-value");
let completionUploadEventMenu = document.getElementById("completion-upload-event-options");
let completionUploadEventOptions = Array.from(
  document.querySelectorAll("#completion-upload-event-options .custom-select-option")
);
const completionCertTableBody = document.getElementById("completion-cert-table-body");
const completionCertEmptyRow = document.getElementById("completion-cert-empty-row");
const completionCertRowTemplate = document.getElementById(
  "completion-cert-row-template"
);
const completionBulkDownloadableButton = document.getElementById("completion-bulk-downloadable");
const completionBulkBlockedButton = document.getElementById("completion-bulk-blocked");
const completionEditDialog = document.getElementById("completion-edit-dialog");
const completionEditCancelButton = document.getElementById("completion-edit-cancel");
const completionEditSubmitButton = document.getElementById("completion-edit-submit");
const completionEditNumber = document.getElementById("completion-edit-number");
const completionEditKktixId = document.getElementById("completion-edit-kktix-id");
const completionEditBadgeName = document.getElementById("completion-edit-badge-name");
const completionEditName = document.getElementById("completion-edit-name");
const completionEditEmail = document.getElementById("completion-edit-email");
const completionEditTicketName = document.getElementById("completion-edit-ticket-name");
const completionEditFeedback = document.getElementById("completion-edit-feedback");
const completionFilterForm = document.querySelector(".document-filter-form");
const completionEventFilter = document.getElementById("completion-event-filter");
let completionEventFilterSelect = document.getElementById("completion-event-filter-select");
let completionEventFilterTrigger = document.getElementById(
  "completion-event-filter-trigger"
);
let completionEventFilterValue = document.getElementById("completion-event-filter-value");
let completionEventFilterMenu = document.getElementById("completion-event-filter-options");
let completionEventFilterOptions = Array.from(
  document.querySelectorAll("#completion-event-filter-options .custom-select-option")
);
const adminEventsApiPath = "/api/v1/admin/events";
const adminCompletionCertsApiPath = "/api/v1/admin/completion-certs";
const adminCompletionCertsImportApiPath = "/api/v1/admin/completion-certs/import";
const portalCsrfToken = document.body?.dataset.portalCsrfToken || "";
const completionUploadOpenMessageType = "ipg:completion-upload:open";
const completionUploadImportMessageType = "ipg:completion-upload:import";
const defaultCompletionUploadFileName = "尚未選擇 CSV 檔案";
const invalidCompletionUploadFileName = "請選擇 CSV 檔案";
const failedCompletionUploadFileName = "CSV 檔案讀取失敗";
const importingCompletionUploadFileName = "完訓證明資料匯入中...";
const defaultCompletionEventName = "";
const emptyCompletionEventName = "尚無活動資料";
const loadingCompletionCertRowsMessage = "完訓證明資料載入中...";
const emptyCompletionCertRowsMessage =
  "目前活動尚無完訓證明資料。請先上傳完訓證明 CSV。";
const completionCsvFieldAliases = {
  badgeName: ["你是誰，ID 或具有鑑識度的名稱 Name on Badge"],
  email: ["Email", "email"],
  kktixId: ["Id"],
  name: ["姓名 Full Name"],
  number: ["報名序號"],
  ticketName: ["票種"],
};

let completionUploadPreviousFocus = null;
let completionEditPreviousFocus = null;
let completionEditRowId = "";
let completionCertRows = [];
let isLoadingCompletionCertRows = true;
let completionEventsSignature = "";

function normalizeCompletionEvent(eventData) {
  return {
    id: typeof eventData?.id === "string" ? eventData.id : "",
    name: typeof eventData?.name === "string" ? eventData.name.trim() : "",
  };
}

function getCompletionEventValue(eventData) {
  return eventData.id;
}

function getCompletionEventLabel(eventData) {
  return eventData.name || eventData.id || "未命名活動";
}

function buildCompletionEventOption(eventData, index, applyValue, closeSelect, optionListRef) {
  const option = document.createElement("button");
  option.className = `custom-select-option${index === 0 ? " is-selected" : ""}`;
  option.type = "button";
  option.setAttribute("role", "option");
  option.dataset.value = getCompletionEventValue(eventData);
  option.setAttribute("aria-selected", String(index === 0));
  option.textContent = getCompletionEventLabel(eventData);

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

function buildCompletionEventSelect({
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
  value.textContent = emptyCompletionEventName;

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

function renderCompletionEventSelects(events) {
  if (!(completionEventFilter instanceof HTMLInputElement)) {
    return;
  }

  const normalizedEvents = events
    .map((eventData) => normalizeCompletionEvent(eventData))
    .filter((eventData) => getCompletionEventValue(eventData));
  const nextEventsSignature = JSON.stringify(normalizedEvents);

  if (nextEventsSignature === completionEventsSignature) {
    return;
  }

  completionEventsSignature = nextEventsSignature;

  const firstEventValue = getCompletionEventValue(normalizedEvents[0] ?? {});
  const isSingleOption = normalizedEvents.length === 1;
  const currentEventValue = getCompletionFilterEventName();
  const nextEventValue = normalizedEvents.some(
    (eventData) => getCompletionEventValue(eventData) === currentEventValue
  )
    ? currentEventValue
    : firstEventValue;

  if (normalizedEvents.length === 0) {
    if (completionEventFilterValue) {
      completionEventFilterValue.textContent = emptyCompletionEventName;
    }
    if (completionUploadEventValue) {
      completionUploadEventValue.textContent = emptyCompletionEventName;
    }
    completionEventFilter.value = "";
    if (completionUploadEvent instanceof HTMLInputElement) {
      completionUploadEvent.value = "";
    }
    completionCertRows = [];
    isLoadingCompletionCertRows = false;
    renderCompletionCertRows();
    return;
  }

  const filterSelect = buildCompletionEventSelect({
    describedBy: "completion-event-filter-label completion-event-filter-value",
    isSingleOption,
    menuId: "completion-event-filter-options",
    selectId: "completion-event-filter-select",
    triggerId: "completion-event-filter-trigger",
    valueId: "completion-event-filter-value",
  });
  completionEventFilterValue?.replaceWith(filterSelect.select);
  completionEventFilterSelect = filterSelect.select;
  completionEventFilterTrigger = filterSelect.trigger;
  completionEventFilterValue = filterSelect.value;
  completionEventFilterMenu = filterSelect.menu;
  completionEventFilterOptions = normalizedEvents.map((eventData, index) =>
    buildCompletionEventOption(
      eventData,
      index,
      applyCompletionEventFilterValue,
      closeCompletionEventFilterSelect,
      () => completionEventFilterOptions
    )
  );
  completionEventFilterMenu.replaceChildren(...completionEventFilterOptions);

  const uploadSelect = buildCompletionEventSelect({
    describedBy: "completion-upload-event-label completion-upload-event-value",
    isSingleOption,
    menuId: "completion-upload-event-options",
    selectId: "completion-upload-event-select",
    triggerId: "completion-upload-event-trigger",
    valueId: "completion-upload-event-value",
  });
  completionUploadEventValue?.replaceWith(uploadSelect.select);
  completionUploadEventSelect = uploadSelect.select;
  completionUploadEventTrigger = uploadSelect.trigger;
  completionUploadEventValue = uploadSelect.value;
  completionUploadEventMenu = uploadSelect.menu;
  completionUploadEventOptions = normalizedEvents.map((eventData, index) =>
    buildCompletionEventOption(
      eventData,
      index,
      applyCompletionUploadEventValue,
      closeCompletionUploadEventSelect,
      () => completionUploadEventOptions
    )
  );
  completionUploadEventMenu.replaceChildren(...completionUploadEventOptions);

  completionEventFilterTrigger.addEventListener("click", toggleCompletionEventFilterSelect);
  completionEventFilterTrigger.addEventListener("keydown", handleCompletionEventFilterTriggerKeydown);
  completionUploadEventTrigger.addEventListener("click", toggleCompletionUploadEventSelect);
  completionUploadEventTrigger.addEventListener("keydown", handleCompletionUploadEventTriggerKeydown);

  applyCompletionEventFilterValue(nextEventValue);
  applyCompletionUploadEventValue(nextEventValue);
}

async function loadCompletionEvents() {
  const eventCache = window.iPlaygroundPortalEvents;
  const cachedEvents = eventCache?.getCachedEvents?.();
  let cachedEventsSignature = "";

  if (Array.isArray(cachedEvents)) {
    cachedEventsSignature = JSON.stringify(
      cachedEvents
        .map((eventData) => normalizeCompletionEvent(eventData))
        .filter((eventData) => getCompletionEventValue(eventData))
    );
    renderCompletionEventSelects(cachedEvents);
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
        .map((eventData) => normalizeCompletionEvent(eventData))
        .filter((eventData) => getCompletionEventValue(eventData))
    );
    if (refreshedEventsSignature !== cachedEventsSignature) {
      renderCompletionEventSelects(events);
    }
  } catch (error) {
    if (Array.isArray(cachedEvents)) {
      return;
    }
    if (completionEventFilterValue) {
      completionEventFilterValue.textContent =
        error instanceof Error ? error.message : "活動清單載入失敗。";
    }
    if (completionUploadEventValue) {
      completionUploadEventValue.textContent = "活動清單載入失敗。";
    }
  }
}

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
    return completionEventFilter.value;
  }

  return defaultCompletionEventName;
}

function getCompletionUploadEventName() {
  if (completionUploadEvent instanceof HTMLInputElement) {
    return completionUploadEvent.value || getCompletionFilterEventName();
  }

  return getCompletionFilterEventName();
}

function resolveCompletionEventLabel(options, eventId) {
  const selectedOption = options.find((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    return optionValue === eventId;
  });
  return selectedOption?.textContent?.trim() || eventId || emptyCompletionEventName;
}

function applyCompletionUploadEventValue(nextValue) {
  const normalizedValue = nextValue?.trim() || defaultCompletionEventName;

  if (completionUploadEvent instanceof HTMLInputElement) {
    completionUploadEvent.value = normalizedValue;
  }

  if (completionUploadEventValue) {
    completionUploadEventValue.textContent = resolveCompletionEventLabel(
      completionUploadEventOptions,
      normalizedValue
    );
  }

  completionUploadEventOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function getFirstCompletionUploadEventValue() {
  const firstOption = completionUploadEventOptions[0];
  return firstOption?.dataset.value ?? firstOption?.textContent?.trim() ?? "";
}

function resetCompletionUploadDialog() {
  if (completionUploadFileInput instanceof HTMLInputElement) {
    completionUploadFileInput.value = "";
  }

  clearCompletionUploadErrors();
  applyCompletionUploadEventValue(
    getCompletionFilterEventName() ||
      getCompletionUploadEventName() ||
      getFirstCompletionUploadEventValue()
  );
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

  clearCompletionUploadErrors();
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

function clearCompletionUploadErrors() {
  if (!(completionUploadErrors instanceof HTMLElement)) {
    return;
  }

  completionUploadErrors.replaceChildren();
  completionUploadErrors.hidden = true;
}

function buildCompletionUploadImportError(responsePayload, fallbackMessage) {
  const error = new Error(responsePayload?.error?.message || fallbackMessage);
  error.rowErrors = Array.isArray(responsePayload?.error?.details?.rowErrors)
    ? responsePayload.error.details.rowErrors
    : [];
  return error;
}

function showCompletionUploadError(error) {
  if (!(completionUploadErrors instanceof HTMLElement)) {
    return;
  }

  const message = error instanceof Error ? error.message : failedCompletionUploadFileName;
  const rowErrors = Array.isArray(error?.rowErrors) ? error.rowErrors : [];
  const title = document.createElement("strong");
  title.textContent = message;
  completionUploadErrors.replaceChildren(title);

  if (rowErrors.length > 0) {
    const list = document.createElement("ul");
    rowErrors.forEach((rowError) => {
      const item = document.createElement("li");
      item.textContent = rowError?.message || `CSV 第 ${rowError?.rowNumber ?? "?"} 列資料不合法。`;
      list.append(item);
    });
    completionUploadErrors.append(list);
  }

  completionUploadErrors.hidden = false;
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

function hasDraggedCompletionFiles(event) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

function setCompletionUploadDragActive(isActive) {
  completionUploadDropzone?.classList.toggle("is-drag-active", isActive);
}

function assignCompletionUploadFile(file) {
  if (!(completionUploadFileInput instanceof HTMLInputElement)) {
    return;
  }

  if (!isCompletionCsvFile(file)) {
    completionUploadFileInput.value = "";
    completionUploadFileName.textContent = invalidCompletionUploadFileName;
    return;
  }

  const transfer = new DataTransfer();
  transfer.items.add(file);
  completionUploadFileInput.files = transfer.files;
  updateCompletionUploadFileName();
}

function handleCompletionUploadDrag(event) {
  if (completionUploadDialog?.hidden || !hasDraggedCompletionFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setCompletionUploadDragActive(true);
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function handleCompletionUploadDragEnd(event) {
  if (completionUploadDialog?.hidden || !hasDraggedCompletionFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setCompletionUploadDragActive(false);
}

function handleCompletionUploadDrop(event) {
  if (completionUploadDialog?.hidden || !hasDraggedCompletionFiles(event)) {
    return;
  }

  event.preventDefault();
  event.stopPropagation();
  setCompletionUploadDragActive(false);

  const file = event.dataTransfer?.files?.[0];
  if (file) {
    assignCompletionUploadFile(file);
  }
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

function resolveCompletionCsvValue(row, columnIndexes, fieldName) {
  const columnIndex = columnIndexes[fieldName];
  const value = columnIndex >= 0 ? row[columnIndex] : "";
  return value?.trim() ?? "";
}

function buildCompletionCertRows(csvText, eventName = defaultCompletionEventName) {
  const parsedRows = parseCompletionCsv(csvText);
  if (parsedRows.length === 0) {
    return [];
  }

  const headers = parsedRows[0];
  const hasHeader = hasCompletionCsvHeader(headers);
  if (!hasHeader) {
    return [];
  }

  const dataRows = hasHeader ? parsedRows.slice(1) : parsedRows;
  const columnIndexes = {
    badgeName: hasHeader
      ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.badgeName)
      : -1,
    email: hasHeader ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.email) : -1,
    kktixId: hasHeader ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.kktixId) : -1,
    name: hasHeader ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.name) : -1,
    number: hasHeader ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.number) : -1,
    ticketName: hasHeader
      ? findCompletionCsvColumnIndex(headers, completionCsvFieldAliases.ticketName)
      : -1,
  };
  const importId = Date.now();

  return dataRows
    .map((row, index) => ({
      badgeName: resolveCompletionCsvValue(row, columnIndexes, "badgeName"),
      email: resolveCompletionCsvValue(row, columnIndexes, "email"),
      eventName,
      id: `completion-row-${importId}-${index}`,
      isDownloadable: false,
      kktixId: resolveCompletionCsvValue(row, columnIndexes, "kktixId"),
      name: resolveCompletionCsvValue(row, columnIndexes, "name"),
      number: resolveCompletionCsvValue(row, columnIndexes, "number"),
      ticketName: resolveCompletionCsvValue(row, columnIndexes, "ticketName"),
    }))
    .filter((row) =>
      [
        row.badgeName,
        row.email,
        row.kktixId,
        row.name,
        row.number,
        row.ticketName,
      ].some(Boolean)
    );
}

function setTextContent(parent, selector, value) {
  const element = parent.querySelector(selector);
  if (element) {
    element.textContent = value || "-";
  }
}

function normalizeCompletionCertRow(rowData) {
  return {
    attendanceStatus:
      typeof rowData?.attendanceStatus === "string"
        ? rowData.attendanceStatus
        : "notCheckedIn",
    badgeName: typeof rowData?.badgeName === "string" ? rowData.badgeName : "",
    certStatus: typeof rowData?.certStatus === "string" ? rowData.certStatus : "notIssued",
    email: typeof rowData?.email === "string" ? rowData.email : "",
    eventId: typeof rowData?.eventId === "string" ? rowData.eventId : "",
    id: typeof rowData?.id === "string" ? rowData.id : "",
    isDownloadable: rowData?.attendanceStatus === "checkedIn",
    kktixId: typeof rowData?.kktixId === "string" ? rowData.kktixId : "",
    name: typeof rowData?.name === "string" ? rowData.name : "",
    number:
      typeof rowData?.number === "number" || typeof rowData?.number === "string"
        ? String(rowData.number)
        : "",
    ticketName: typeof rowData?.ticketName === "string" ? rowData.ticketName : "",
  };
}

function getVisibleCompletionCertRows() {
  const eventId = getCompletionFilterEventName();
  return completionCertRows.filter((row) => row.eventId === eventId);
}

function getCompletionCertRow(rowId) {
  return completionCertRows.find((row) => row.id === rowId) || null;
}

function clearCompletionEditFeedback() {
  if (!(completionEditFeedback instanceof HTMLElement)) {
    return;
  }

  completionEditFeedback.textContent = "";
  completionEditFeedback.hidden = true;
}

function showCompletionEditFeedback(message) {
  if (!(completionEditFeedback instanceof HTMLElement)) {
    return;
  }

  completionEditFeedback.textContent = message;
  completionEditFeedback.hidden = false;
}

function setCompletionEditInputValue(element, value) {
  if (element instanceof HTMLInputElement) {
    element.value = value;
  }
}

function getCompletionEditInputValue(element) {
  return element instanceof HTMLInputElement ? element.value.trim() : "";
}

function openCompletionEditDialog(rowData) {
  if (!completionEditDialog) {
    return;
  }

  completionEditRowId = rowData.id;
  completionEditPreviousFocus = document.activeElement;
  clearCompletionEditFeedback();

  if (completionEditNumber) {
    completionEditNumber.textContent = rowData.number || "-";
  }
  if (completionEditKktixId) {
    completionEditKktixId.textContent = rowData.kktixId || "-";
  }
  setCompletionEditInputValue(completionEditBadgeName, rowData.badgeName);
  setCompletionEditInputValue(completionEditName, rowData.name);
  setCompletionEditInputValue(completionEditEmail, rowData.email);
  setCompletionEditInputValue(completionEditTicketName, rowData.ticketName);

  completionEditDialog.hidden = false;
  document.body.classList.add("has-event-dialog");
  completionEditBadgeName?.focus();
}

function closeCompletionEditDialog() {
  if (!completionEditDialog) {
    return;
  }

  completionEditDialog.hidden = true;
  completionEditRowId = "";
  clearCompletionEditFeedback();
  document.body.classList.remove("has-event-dialog");

  if (completionEditPreviousFocus instanceof HTMLElement) {
    completionEditPreviousFocus.focus();
  }
}

function normalizeEditedCompletionCert(rowData) {
  return normalizeCompletionCertRow(rowData);
}

async function submitCompletionEditDialog() {
  if (!(completionEditSubmitButton instanceof HTMLButtonElement)) {
    return;
  }

  const rowData = getCompletionCertRow(completionEditRowId);
  if (!rowData) {
    showCompletionEditFeedback("找不到要修改的完訓證明資料。");
    return;
  }

  const payload = {
    badgeName: getCompletionEditInputValue(completionEditBadgeName),
    email: getCompletionEditInputValue(completionEditEmail),
    eventId: rowData.eventId,
    name: getCompletionEditInputValue(completionEditName),
    ticketName: getCompletionEditInputValue(completionEditTicketName),
  };

  completionEditSubmitButton.disabled = true;
  clearCompletionEditFeedback();
  try {
    const response = await fetch(
      `${adminCompletionCertsApiPath}/${encodeURIComponent(rowData.id)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Portal-CSRF-Token": portalCsrfToken,
        },
        body: JSON.stringify(payload),
      }
    );
    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "完訓證明資料修改失敗。");
    }

    const updatedRow = normalizeEditedCompletionCert(responsePayload.completionCert);
    completionCertRows = completionCertRows.map((row) =>
      row.id === updatedRow.id ? updatedRow : row
    );
    renderCompletionCertRows();
    closeCompletionEditDialog();
  } catch (error) {
    showCompletionEditFeedback(
      error instanceof Error ? error.message : "完訓證明資料修改失敗。"
    );
  } finally {
    completionEditSubmitButton.disabled = false;
  }
}

function applyCompletionRowDownloadState(rowElement, rowData) {
  const switchInput = rowElement.querySelector('[data-action="toggle-downloadable"]');
  const downloadButton = rowElement.querySelector(".document-download-button");

  rowElement.classList.toggle("is-downloadable", rowData.isDownloadable);
  rowElement.classList.toggle("is-blocked", !rowData.isDownloadable);

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

function setCompletionCertEmptyMessage(message) {
  const emptyCell = completionCertEmptyRow?.querySelector("td");
  if (emptyCell) {
    emptyCell.textContent = message;
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
    setCompletionCertEmptyMessage(
      isLoadingCompletionCertRows
        ? loadingCompletionCertRowsMessage
        : emptyCompletionCertRowsMessage
    );
  }

  visibleRows.forEach((rowData) => {
    const rowFragment = completionCertRowTemplate.content.cloneNode(true);
    const rowElement = rowFragment.querySelector(".completion-cert-row");
    if (!(rowElement instanceof HTMLTableRowElement)) {
      return;
    }

    rowElement.dataset.rowId = rowData.id;
    setTextContent(rowElement, '[data-field="number"]', rowData.number);
    setTextContent(rowElement, '[data-field="kktixId"]', rowData.kktixId);
    setTextContent(rowElement, '[data-field="badgeName"]', rowData.badgeName);
    setTextContent(rowElement, '[data-field="ticketName"]', rowData.ticketName);
    setTextContent(rowElement, '[data-field="name"]', rowData.name);
    setTextContent(rowElement, '[data-field="email"]', rowData.email);

    const switchInput = rowElement.querySelector('[data-action="toggle-downloadable"]');
    if (switchInput instanceof HTMLInputElement) {
      const rowLabel = rowData.name || rowData.number || "此筆完訓證明";
      switchInput.setAttribute("aria-label", `${rowLabel} 簽到狀態`);
      switchInput.addEventListener("change", () => {
        setCompletionRowDownloadState(rowData.id, switchInput.checked);
      });
    }

    const editButton = rowElement.querySelector(".document-edit-button");
    if (editButton instanceof HTMLButtonElement) {
      editButton.addEventListener("click", () => {
        openCompletionEditDialog(rowData);
      });
    }

    applyCompletionRowDownloadState(rowElement, rowData);
    completionCertTableBody.append(rowElement);
  });

  updateCompletionBulkActionControls();
}

async function loadCompletionCertRows(eventId = getCompletionFilterEventName()) {
  if (!eventId) {
    completionCertRows = [];
    isLoadingCompletionCertRows = false;
    renderCompletionCertRows();
    return;
  }

  isLoadingCompletionCertRows = true;
  completionCertRows = completionCertRows.filter((row) => row.eventId !== eventId);
  renderCompletionCertRows();

  try {
    const response = await fetch(
      `${adminCompletionCertsApiPath}?eventId=${encodeURIComponent(eventId)}`,
      {
        headers: {
          Accept: "application/json",
        },
      }
    );
    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "完訓證明資料載入失敗。");
    }

    completionCertRows = [
      ...completionCertRows.filter((row) => row.eventId !== eventId),
      ...(Array.isArray(responsePayload.completionCerts)
        ? responsePayload.completionCerts.map((row) => normalizeCompletionCertRow(row))
        : []),
    ];
  } finally {
    isLoadingCompletionCertRows = false;
    renderCompletionCertRows();
  }
}

async function importCompletionCsvText(csvText, eventId = getCompletionUploadEventName()) {
  if (!eventId) {
    throw new Error("請先選擇活動。");
  }

  const response = await fetch(adminCompletionCertsImportApiPath, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Portal-CSRF-Token": portalCsrfToken,
    },
    body: JSON.stringify({ eventId, csvText }),
  });
  const responsePayload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw buildCompletionUploadImportError(responsePayload, "完訓證明資料匯入失敗。");
  }

  completionCertRows = [
    ...completionCertRows.filter((row) => row.eventId !== eventId),
    ...(Array.isArray(responsePayload.completionCerts)
      ? responsePayload.completionCerts.map((row) => normalizeCompletionCertRow(row))
      : []),
  ];
  applyCompletionEventFilterValue(eventId, { renderRows: false });
  renderCompletionCertRows();
}

async function importSelectedCompletionCsvFile() {
  if (!(completionUploadSubmitButton instanceof HTMLButtonElement)) {
    return;
  }

  const selectedFile = getSelectedCompletionUploadFile();
  if (!selectedFile || !isCompletionCsvFile(selectedFile)) {
    updateCompletionUploadFileName();
    completionUploadFileInput?.focus();
    return;
  }

  completionUploadSubmitButton.disabled = true;
  clearCompletionUploadErrors();
  if (completionUploadFileName) {
    completionUploadFileName.textContent = importingCompletionUploadFileName;
  }

  try {
    await importCompletionCsvText(await selectedFile.text());
    closeCompletionUploadDialog();
  } catch (error) {
    if (completionUploadFileName) {
      completionUploadFileName.textContent =
        error instanceof Error ? error.message : failedCompletionUploadFileName;
    }
    showCompletionUploadError(error);
  } finally {
    completionUploadSubmitButton.disabled = false;
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
  setCompletionUploadDragActive(false);
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
    completionEventFilterValue.textContent = resolveCompletionEventLabel(
      completionEventFilterOptions,
      normalizedValue
    );
  }

  completionEventFilterOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });

  if (renderRows) {
    void loadCompletionCertRows(normalizedValue).catch((error) => {
      completionCertRows = completionCertRows.filter(
        (row) => row.eventId !== normalizedValue
      );
      renderCompletionCertRows();
      if (completionEventFilterValue) {
        completionEventFilterValue.textContent =
          error instanceof Error ? error.message : "完訓證明資料載入失敗。";
      }
    });
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
  if (completionEventFilterOptions.length <= 1) {
    closeCompletionEventFilterSelect();
    return;
  }

  completionEventFilterSelect?.classList.add("is-open");
  completionEventFilterTrigger?.setAttribute("aria-expanded", "true");

  if (completionEventFilterMenu) {
    completionEventFilterMenu.hidden = false;
  }
}

function toggleCompletionEventFilterSelect() {
  if (completionEventFilterOptions.length <= 1) {
    return;
  }

  if (completionEventFilterSelect?.classList.contains("is-open")) {
    closeCompletionEventFilterSelect({ blurTrigger: true });
    return;
  }

  openCompletionEventFilterSelect();
}

function handleCompletionEventFilterTriggerKeydown(event) {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (completionEventFilterOptions.length <= 1) {
      return;
    }

    openCompletionEventFilterSelect();
    completionEventFilterOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeCompletionEventFilterSelect({ blurTrigger: true });
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

function toggleCompletionUploadEventSelect() {
  if (completionUploadEventOptions.length <= 1) {
    return;
  }

  if (completionUploadEventSelect?.classList.contains("is-open")) {
    closeCompletionUploadEventSelect({ blurTrigger: true });
    return;
  }

  openCompletionUploadEventSelect();
}

function handleCompletionUploadEventTriggerKeydown(event) {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (completionUploadEventOptions.length <= 1) {
      return;
    }

    openCompletionUploadEventSelect();
    completionUploadEventOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeCompletionUploadEventSelect({ blurTrigger: true });
  }
}

function openCompletionUploadEventSelect() {
  if (completionUploadEventOptions.length <= 1) {
    closeCompletionUploadEventSelect();
    return;
  }

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

completionEditCancelButton?.addEventListener("click", closeCompletionEditDialog);
completionEditSubmitButton?.addEventListener("click", () => {
  void submitCompletionEditDialog();
});

completionUploadFileInput?.addEventListener("change", updateCompletionUploadFileName);
["dragenter", "dragover"].forEach((eventName) => {
  document.addEventListener(eventName, handleCompletionUploadDrag);
});
["dragleave", "dragend"].forEach((eventName) => {
  document.addEventListener(eventName, handleCompletionUploadDragEnd);
});
document.addEventListener("drop", handleCompletionUploadDrop);

completionUploadEventTrigger?.addEventListener("click", toggleCompletionUploadEventSelect);
completionUploadEventTrigger?.addEventListener(
  "keydown",
  handleCompletionUploadEventTriggerKeydown
);

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

completionEventFilterTrigger?.addEventListener("click", toggleCompletionEventFilterSelect);
completionEventFilterTrigger?.addEventListener(
  "keydown",
  handleCompletionEventFilterTriggerKeydown
);

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

completionEditDialog?.addEventListener("click", (event) => {
  if (event.target === completionEditDialog) {
    closeCompletionEditDialog();
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

  if (message.type === completionUploadImportMessageType) {
    if (typeof message.eventId === "string" && Array.isArray(message.completionCerts)) {
      completionCertRows = [
        ...completionCertRows.filter((row) => row.eventId !== message.eventId),
        ...message.completionCerts.map((row) => normalizeCompletionCertRow(row)),
      ];
      applyCompletionEventFilterValue(message.eventId, { renderRows: false });
      renderCompletionCertRows();
      return;
    }

    if (typeof message.csvText === "string") {
      void importCompletionCsvText(
        message.csvText,
        typeof message.eventName === "string" ? message.eventName : defaultCompletionEventName
      ).catch((error) => {
        if (completionUploadFileName) {
          completionUploadFileName.textContent =
            error instanceof Error ? error.message : failedCompletionUploadFileName;
        }
        showCompletionUploadError(error);
      });
    }
  }
});

window.addEventListener("ipg:portal-events:updated", (event) => {
  const events = Array.isArray(event.detail?.events) ? event.detail.events : [];
  renderCompletionEventSelects(events);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && completionUploadDialog && !completionUploadDialog.hidden) {
    closeCompletionUploadDialog({ confirmUnsaved: true });
  }

  if (event.key === "Escape" && completionEditDialog && !completionEditDialog.hidden) {
    closeCompletionEditDialog();
  }
});

renderCompletionCertRows();
void loadCompletionEvents();
