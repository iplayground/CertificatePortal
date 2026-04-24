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
const dashboardEventDocumentTypeInputs = Array.from(
  document.querySelectorAll("#portal-event-create-dialog [data-document-type]")
);

const portalEntryPath = portalPage.dataset.portalEntryPath ?? "/portal";
const logoutUrl =
  portalPage.dataset.logoutUrl ?? "/portal/auth/logout?post_logout_redirect_uri=/portal";
const welcomePagePath = portalPage.dataset.welcomePagePath ?? "/portal/dashboard/welcome";
const eventFormOpenMessageType = "ipg:event-form:open";
const defaultPageTitle = document.title;

const viewButtons = Array.from(document.querySelectorAll("[data-view-target]"));
let dashboardEventCreatePreviousFocus = null;
let dashboardEventDialogMode = "create";
let dashboardEventInitialState = "";

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
  });
}

function setDashboardEventDialogMode(mode = "create", eventData = {}) {
  const isEditMode = mode === "edit";
  const documentTypes = resolveDashboardEventDocumentTypes(mode, eventData);
  dashboardEventDialogMode = isEditMode ? "edit" : "create";

  if (dashboardEventCreateTitle) {
    dashboardEventCreateTitle.textContent = isEditMode ? "編輯活動" : "建立活動";
  }

  if (dashboardEventFormSubmitButton) {
    dashboardEventFormSubmitButton.textContent = isEditMode ? "儲存變更" : "建立活動";
  }

  if (dashboardEventNameInput instanceof HTMLInputElement) {
    dashboardEventNameInput.value = eventData.name ?? (isEditMode ? "" : "iPlayground 2026");
  }

  applyDashboardEventStatusValue(eventData.status ?? "open");

  dashboardEventDocumentTypeInputs.forEach((input) => {
    if (input instanceof HTMLInputElement) {
      input.checked = documentTypes.includes(input.value);
    }
  });

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

dashboardEventStatusCheckbox?.addEventListener("change", () => {
  applyDashboardEventStatusValue(dashboardEventStatusCheckbox.checked ? "open" : "unlisted");
});

dashboardEventCreateDialog?.addEventListener("click", (event) => {
  if (event.target === dashboardEventCreateDialog) {
    closeDashboardEventCreateDialog({ confirmUnsaved: true });
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
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && dashboardEventCreateDialog && !dashboardEventCreateDialog.hidden) {
    closeDashboardEventCreateDialog({ confirmUnsaved: true });
  }
});

syncViewFromFrame();
syncPageTitleFromFrame();
