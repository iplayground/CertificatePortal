const portalPage = document.body;
const contentFrame = document.getElementById("admin-content-frame");
const logoutButton = document.getElementById("portal-logout");
const adminAccountDisplay = document.getElementById("admin-account-display");

const homePagePath = portalPage.dataset.homePagePath ?? "/";
const portalAccountStorageKey =
  portalPage.dataset.portalAccountStorageKey ?? "portalSignedInAccount";
const welcomePagePath = portalPage.dataset.welcomePagePath ?? "/portal/dashboard/welcome";
const defaultPageTitle = document.title;

const viewButtons = Array.from(document.querySelectorAll("[data-view-target]"));

function readSignedInAccount() {
  try {
    return window.sessionStorage.getItem(portalAccountStorageKey)?.trim() ?? "";
  } catch (error) {
    void error;
    return "";
  }
}

function syncSignedInAccount() {
  const displayValue = readSignedInAccount() || "管理者";
  adminAccountDisplay.textContent = displayValue;
}

function clearSignedInAccount() {
  try {
    window.sessionStorage.removeItem(portalAccountStorageKey);
  } catch (error) {
    void error;
  }
}

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
  const matchingButton =
    viewButtons.find((button) => button.dataset.viewPath === currentPath) ??
    viewButtons.find((button) => button.dataset.viewTarget === "welcome");

  if (!matchingButton) {
    return;
  }

  setActiveView(matchingButton.dataset.viewTarget ?? "welcome");
}

function syncPageTitleFromFrame() {
  const frameDocument = contentFrame.contentDocument;
  const nextTitle = frameDocument?.title?.trim() || defaultPageTitle;

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
  clearSignedInAccount();
  window.location.assign(homePagePath);
});

syncSignedInAccount();
syncViewFromFrame();
syncPageTitleFromFrame();
