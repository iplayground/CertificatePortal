const volunteerServiceFilterForm = document.querySelector(".document-filter-form");
const volunteerServiceEventFilter = document.getElementById("volunteer-service-event-filter");
let volunteerServiceEventFilterSelect = document.getElementById(
  "volunteer-service-event-filter-select"
);
let volunteerServiceEventFilterTrigger = document.getElementById(
  "volunteer-service-event-filter-trigger"
);
let volunteerServiceEventFilterValue = document.getElementById(
  "volunteer-service-event-filter-value"
);
let volunteerServiceEventFilterMenu = document.getElementById(
  "volunteer-service-event-filter-options"
);
let volunteerServiceEventFilterOptions = Array.from(
  document.querySelectorAll("#volunteer-service-event-filter-options .custom-select-option")
);

const adminEventsApiPath = "/api/v1/admin/events";
const adminVolunteerServiceCertsApiPath = "/api/v1/admin/volunteer-service-certs";
const portalCsrfToken = document.body?.dataset.portalCsrfToken || "";
const emptyVolunteerServiceEventName = "尚無活動資料";
let volunteerServiceEventsSignature = "";
const volunteerServiceTableBody = document.querySelector(".document-list-table tbody");

function handlePortalUnauthorizedResponse(response) {
  return window.iPlaygroundPortalAuth?.handleUnauthorizedResponse?.(response) === true;
}

function normalizeVolunteerServiceEvent(eventData) {
  return {
    id: typeof eventData?.id === "string" ? eventData.id : "",
    name: typeof eventData?.name === "string" ? eventData.name.trim() : "",
  };
}

function getVolunteerServiceEventValue(eventData) {
  return eventData.id;
}

function getVolunteerServiceEventLabel(eventData) {
  return eventData.name || eventData.id || "未命名活動";
}

function formatVolunteerServiceValue(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  const text = String(value).trim();
  return text || "-";
}

function resolveVolunteerServiceCertStatusLabel(status) {
  const labels = {
    failed: "產生失敗",
    issued: "已發行",
    notIssued: "尚未發行",
  };
  return labels[status] || status || "尚未發行";
}

function normalizeVolunteerServiceCertRow(rowData) {
  return {
    certStatus:
      typeof rowData?.certStatus === "string" && rowData.certStatus
        ? rowData.certStatus
        : "notIssued",
    downloadEnabled: rowData?.downloadEnabled === true,
    email: typeof rowData?.email === "string" ? rowData.email : "",
    eventId: typeof rowData?.eventId === "string" ? rowData.eventId : "",
    id: typeof rowData?.id === "string" ? rowData.id : "",
    name: typeof rowData?.name === "string" ? rowData.name : "",
    number:
      typeof rowData?.number === "number" || typeof rowData?.number === "string"
        ? String(rowData.number)
        : "",
    serviceEndDate:
      typeof rowData?.serviceEndDate === "string" ? rowData.serviceEndDate : "",
    serviceHours:
      typeof rowData?.serviceHours === "number" || typeof rowData?.serviceHours === "string"
        ? String(rowData.serviceHours)
        : "",
    serviceOrganization:
      typeof rowData?.serviceOrganization === "string" ? rowData.serviceOrganization : "",
    serviceStartDate:
      typeof rowData?.serviceStartDate === "string" ? rowData.serviceStartDate : "",
  };
}

function renderVolunteerServiceDownloadSwitch(rowData) {
  const cell = document.createElement("td");
  cell.className = "volunteer-service-download-cell";

  const label = document.createElement("label");
  label.className = "event-status-switch-option document-row-status-switch";

  const input = document.createElement("input");
  input.className = "event-status-switch-input document-download-switch-input";
  input.type = "checkbox";
  input.checked = rowData.downloadEnabled;
  input.setAttribute(
    "aria-label",
    `${rowData.name || rowData.email || rowData.number || "此筆志工服務證明"} 可否下載`
  );

  const track = document.createElement("span");
  track.className = "event-status-switch-track";
  track.setAttribute("aria-hidden", "true");

  const thumb = document.createElement("span");
  thumb.className = "event-status-switch-thumb";

  track.append(thumb);
  label.append(input, track);
  cell.append(label);

  input.addEventListener("change", () => {
    void updateVolunteerServiceDownloadEnabled(rowData, input.checked, input);
  });

  return cell;
}

function renderVolunteerServiceEmptyRow(message) {
  if (!volunteerServiceTableBody) {
    return;
  }

  const row = document.createElement("tr");
  row.className = "document-empty-row";
  const cell = document.createElement("td");
  cell.colSpan = 7;
  cell.textContent = message;
  row.append(cell);
  volunteerServiceTableBody.replaceChildren(row);
}

function renderVolunteerServiceCertRows(rows) {
  if (!volunteerServiceTableBody) {
    return;
  }

  if (rows.length === 0) {
    renderVolunteerServiceEmptyRow("志工服務證明資料尚未建立。");
    return;
  }

  volunteerServiceTableBody.replaceChildren(
    ...rows.map((rowData) => {
      const row = document.createElement("tr");
      row.className = "document-list-row";
      [
        rowData.name || rowData.email || rowData.number,
        rowData.serviceOrganization,
        rowData.serviceStartDate,
        rowData.serviceEndDate,
        rowData.serviceHours,
        resolveVolunteerServiceCertStatusLabel(rowData.certStatus),
      ].forEach((value, index) => {
        const cell = document.createElement("td");
        cell.textContent = formatVolunteerServiceValue(value);
        if (index === 5) {
          cell.className = "volunteer-service-status-cell";
        }
        row.append(cell);
      });
      row.insertBefore(renderVolunteerServiceDownloadSwitch(rowData), row.children[5] ?? null);
      return row;
    })
  );
}

async function updateVolunteerServiceDownloadEnabled(rowData, downloadEnabled, input) {
  if (!(input instanceof HTMLInputElement)) {
    return;
  }

  const previousValue = rowData.downloadEnabled;
  input.disabled = true;
  try {
    const response = await fetch(
      `${adminVolunteerServiceCertsApiPath}/${encodeURIComponent(rowData.id)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-Portal-CSRF-Token": portalCsrfToken,
        },
        body: JSON.stringify({
          downloadEnabled,
          eventId: rowData.eventId,
        }),
      }
    );
    if (handlePortalUnauthorizedResponse(response)) {
      return;
    }

    const responsePayload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(responsePayload?.error?.message || "可否下載更新失敗。");
    }

    rowData.downloadEnabled =
      responsePayload?.volunteerServiceCert?.downloadEnabled === true;
    input.checked = rowData.downloadEnabled;
  } catch (error) {
    rowData.downloadEnabled = previousValue;
    input.checked = previousValue;
    window.alert(error instanceof Error ? error.message : "可否下載更新失敗。");
  } finally {
    input.disabled = false;
  }
}

async function loadVolunteerServiceCertsForSelectedEvent() {
  const eventId =
    volunteerServiceEventFilter instanceof HTMLInputElement
      ? volunteerServiceEventFilter.value.trim()
      : "";
  if (!eventId) {
    renderVolunteerServiceEmptyRow("請先選擇活動。");
    return;
  }

  renderVolunteerServiceEmptyRow("志工服務證明資料載入中。");
  try {
    const response = await fetch(
      `${adminVolunteerServiceCertsApiPath}?eventId=${encodeURIComponent(eventId)}`,
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
      throw new Error(responsePayload?.error?.message || "志工服務證明資料載入失敗。");
    }

    const rows = Array.isArray(responsePayload.volunteerServiceCerts)
      ? responsePayload.volunteerServiceCerts.map((rowData) =>
          normalizeVolunteerServiceCertRow(rowData)
        )
      : [];
    renderVolunteerServiceCertRows(rows);
  } catch (error) {
    renderVolunteerServiceEmptyRow(
      error instanceof Error ? error.message : "志工服務證明資料載入失敗。"
    );
  }
}

function buildVolunteerServiceEventOption(eventData, index) {
  const option = document.createElement("button");
  option.className = `custom-select-option${index === 0 ? " is-selected" : ""}`;
  option.type = "button";
  option.setAttribute("role", "option");
  option.dataset.value = getVolunteerServiceEventValue(eventData);
  option.setAttribute("aria-selected", String(index === 0));
  option.textContent = getVolunteerServiceEventLabel(eventData);

  option.addEventListener("click", () => {
    applyVolunteerServiceEventFilterValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeVolunteerServiceEventFilterSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeVolunteerServiceEventFilterSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      volunteerServiceEventFilterOptions[
        (index + 1) % volunteerServiceEventFilterOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      volunteerServiceEventFilterOptions[
        (index - 1 + volunteerServiceEventFilterOptions.length) %
          volunteerServiceEventFilterOptions.length
      ]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeVolunteerServiceEventFilterSelect();
    }
  });

  return option;
}

function buildVolunteerServiceEventSelect({ isSingleOption = false }) {
  const select = document.createElement("div");
  select.className = `custom-select${isSingleOption ? " is-single-option" : ""}`;
  select.id = "volunteer-service-event-filter-select";

  const trigger = document.createElement("button");
  trigger.className = "custom-select-trigger";
  trigger.id = "volunteer-service-event-filter-trigger";
  trigger.type = "button";
  if (isSingleOption) {
    trigger.setAttribute("aria-disabled", "true");
    trigger.setAttribute("tabindex", "-1");
  } else {
    trigger.setAttribute("aria-haspopup", "listbox");
  }
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute(
    "aria-labelledby",
    "volunteer-service-event-filter-label volunteer-service-event-filter-value"
  );

  const value = document.createElement("span");
  value.className = "custom-select-value";
  value.id = "volunteer-service-event-filter-value";
  value.textContent = emptyVolunteerServiceEventName;

  const menu = document.createElement("div");
  menu.className = "custom-select-menu";
  menu.id = "volunteer-service-event-filter-options";
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

function renderVolunteerServiceEventSelect(events) {
  if (!(volunteerServiceEventFilter instanceof HTMLInputElement)) {
    return;
  }

  const normalizedEvents = events
    .map((eventData) => normalizeVolunteerServiceEvent(eventData))
    .filter((eventData) => getVolunteerServiceEventValue(eventData));
  const nextEventsSignature = JSON.stringify(normalizedEvents);

  if (nextEventsSignature === volunteerServiceEventsSignature) {
    return;
  }

  volunteerServiceEventsSignature = nextEventsSignature;

  if (normalizedEvents.length === 0) {
    if (volunteerServiceEventFilterValue) {
      volunteerServiceEventFilterValue.textContent = emptyVolunteerServiceEventName;
    }
    volunteerServiceEventFilter.value = "";
    return;
  }

  const currentEventValue = volunteerServiceEventFilter.value;
  const firstEventValue = getVolunteerServiceEventValue(normalizedEvents[0] ?? {});
  const nextEventValue = normalizedEvents.some(
    (eventData) => getVolunteerServiceEventValue(eventData) === currentEventValue
  )
    ? currentEventValue
    : firstEventValue;
  const filterSelect = buildVolunteerServiceEventSelect({
    isSingleOption: normalizedEvents.length === 1,
  });

  volunteerServiceEventFilterValue?.replaceWith(filterSelect.select);
  volunteerServiceEventFilterSelect = filterSelect.select;
  volunteerServiceEventFilterTrigger = filterSelect.trigger;
  volunteerServiceEventFilterValue = filterSelect.value;
  volunteerServiceEventFilterMenu = filterSelect.menu;
  volunteerServiceEventFilterOptions = normalizedEvents.map((eventData, index) =>
    buildVolunteerServiceEventOption(eventData, index)
  );
  volunteerServiceEventFilterMenu.replaceChildren(...volunteerServiceEventFilterOptions);
  volunteerServiceEventFilterTrigger.addEventListener(
    "click",
    toggleVolunteerServiceEventFilterSelect
  );
  volunteerServiceEventFilterTrigger.addEventListener(
    "keydown",
    handleVolunteerServiceEventFilterTriggerKeydown
  );

  applyVolunteerServiceEventFilterValue(nextEventValue);
}

async function loadVolunteerServiceEvents() {
  const eventCache = window.iPlaygroundPortalEvents;
  const cachedEvents = eventCache?.getCachedEvents?.();
  let cachedEventsSignature = "";

  if (Array.isArray(cachedEvents)) {
    cachedEventsSignature = JSON.stringify(
      cachedEvents
        .map((eventData) => normalizeVolunteerServiceEvent(eventData))
        .filter((eventData) => getVolunteerServiceEventValue(eventData))
    );
    renderVolunteerServiceEventSelect(cachedEvents);
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
        .map((eventData) => normalizeVolunteerServiceEvent(eventData))
        .filter((eventData) => getVolunteerServiceEventValue(eventData))
    );
    if (refreshedEventsSignature !== cachedEventsSignature) {
      renderVolunteerServiceEventSelect(events);
    }
  } catch (error) {
    if (Array.isArray(cachedEvents)) {
      return;
    }
    if (volunteerServiceEventFilterValue) {
      volunteerServiceEventFilterValue.textContent =
        error instanceof Error ? error.message : "活動清單載入失敗。";
    }
  }
}

function resolveVolunteerServiceEventLabel(eventId) {
  const selectedOption = volunteerServiceEventFilterOptions.find((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    return optionValue === eventId;
  });
  return selectedOption?.textContent?.trim() || eventId || emptyVolunteerServiceEventName;
}

function applyVolunteerServiceEventFilterValue(nextValue) {
  const normalizedValue = nextValue?.trim();
  if (!normalizedValue) {
    return;
  }

  if (volunteerServiceEventFilter instanceof HTMLInputElement) {
    volunteerServiceEventFilter.value = normalizedValue;
  }

  if (volunteerServiceEventFilterValue) {
    volunteerServiceEventFilterValue.textContent =
      resolveVolunteerServiceEventLabel(normalizedValue);
  }

  volunteerServiceEventFilterOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });

  void loadVolunteerServiceCertsForSelectedEvent();
}

function closeVolunteerServiceEventFilterSelect({ blurTrigger = false } = {}) {
  volunteerServiceEventFilterSelect?.classList.remove("is-open");
  volunteerServiceEventFilterTrigger?.setAttribute("aria-expanded", "false");

  if (volunteerServiceEventFilterMenu) {
    volunteerServiceEventFilterMenu.hidden = true;
  }

  if (blurTrigger) {
    volunteerServiceEventFilterTrigger?.blur();
  }
}

function openVolunteerServiceEventFilterSelect() {
  if (volunteerServiceEventFilterOptions.length <= 1) {
    closeVolunteerServiceEventFilterSelect();
    return;
  }

  volunteerServiceEventFilterSelect?.classList.add("is-open");
  volunteerServiceEventFilterTrigger?.setAttribute("aria-expanded", "true");

  if (volunteerServiceEventFilterMenu) {
    volunteerServiceEventFilterMenu.hidden = false;
  }
}

function toggleVolunteerServiceEventFilterSelect() {
  if (volunteerServiceEventFilterOptions.length <= 1) {
    return;
  }

  if (volunteerServiceEventFilterSelect?.classList.contains("is-open")) {
    closeVolunteerServiceEventFilterSelect({ blurTrigger: true });
    return;
  }

  openVolunteerServiceEventFilterSelect();
}

function handleVolunteerServiceEventFilterTriggerKeydown(event) {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (volunteerServiceEventFilterOptions.length <= 1) {
      return;
    }

    openVolunteerServiceEventFilterSelect();
    volunteerServiceEventFilterOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeVolunteerServiceEventFilterSelect({ blurTrigger: true });
  }
}

volunteerServiceFilterForm?.addEventListener("submit", (event) => {
  event.preventDefault();
});

document.addEventListener("click", (event) => {
  if (
    volunteerServiceEventFilterSelect instanceof HTMLElement &&
    !volunteerServiceEventFilterSelect.contains(event.target)
  ) {
    closeVolunteerServiceEventFilterSelect();
  }
});

window.addEventListener("ipg:portal-events:updated", (event) => {
  const events = Array.isArray(event.detail?.events) ? event.detail.events : [];
  renderVolunteerServiceEventSelect(events);
});

void loadVolunteerServiceEvents();
