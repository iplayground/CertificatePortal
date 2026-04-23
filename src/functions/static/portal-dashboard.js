const portalPage = document.body;
const contentFrame = document.getElementById("admin-content-frame");
const logoutButton = document.getElementById("portal-logout");

const portalEntryPath = portalPage.dataset.portalEntryPath ?? "/portal";
const logoutUrl =
  portalPage.dataset.logoutUrl ?? "/portal/auth/logout?post_logout_redirect_uri=/portal";
const welcomePagePath = portalPage.dataset.welcomePagePath ?? "/portal/dashboard/welcome";
const defaultPageTitle = document.title;

const viewButtons = Array.from(document.querySelectorAll("[data-view-target]"));

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

syncViewFromFrame();
syncPageTitleFromFrame();
