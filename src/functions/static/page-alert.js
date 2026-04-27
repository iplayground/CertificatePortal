const dismissPageAlert = (pageAlert) => {
  if (
    !pageAlert ||
    pageAlert.classList.contains("is-closing") ||
    pageAlert.classList.contains("is-hidden")
  ) {
    return;
  }

  pageAlert.classList.add("is-closing");
};

const initializePageAlert = (pageAlert) => {
  const dismissButton = pageAlert.querySelector("[data-page-alert-dismiss]");

  pageAlert.addEventListener("animationend", (event) => {
    if (event.target !== pageAlert || event.animationName !== "page-alert-dissolve") {
      return;
    }

    pageAlert.classList.remove("is-closing");
    pageAlert.classList.add("is-hidden");
  });

  dismissButton?.addEventListener("click", () => {
    dismissPageAlert(pageAlert);
  });

  const dismissDelay = Number.parseInt(pageAlert.dataset.pageAlertDismissDelay ?? "", 10);
  if (Number.isFinite(dismissDelay) && dismissDelay >= 0) {
    window.setTimeout(() => {
      dismissPageAlert(pageAlert);
    }, dismissDelay);
  }
};

const createPageAlert = ({ dismissDelay = 6000, message = "", title = "", tone = "info" } = {}) => {
  const normalizedTone = ["error", "info", "success"].includes(tone) ? tone : "info";
  const pageAlert = document.createElement("div");
  const frame = document.createElement("div");
  const content = document.createElement("div");
  const body = document.createElement("div");
  const titleElement = document.createElement("strong");
  const messageElement = document.createElement("p");
  const closeButton = document.createElement("button");

  pageAlert.className = "page-alert";
  pageAlert.dataset.pageAlert = "";
  pageAlert.dataset.pageAlertTone = normalizedTone;
  pageAlert.setAttribute("role", "alert");
  pageAlert.setAttribute("aria-live", "assertive");

  if (Number.isFinite(dismissDelay) && dismissDelay >= 0) {
    pageAlert.dataset.pageAlertDismissDelay = String(dismissDelay);
  }

  frame.className = "page-alert-frame";
  frame.setAttribute("aria-hidden", "true");
  content.className = "page-alert-content";
  body.className = "page-alert-body";
  titleElement.className = "page-alert-title";
  messageElement.className = "page-alert-message";
  closeButton.className = "page-alert-close";
  closeButton.type = "button";
  closeButton.dataset.pageAlertDismiss = "";
  closeButton.setAttribute("aria-label", "關閉提示");
  closeButton.textContent = "關閉";
  titleElement.textContent = title;
  messageElement.textContent = message;

  body.append(titleElement, messageElement);
  content.append(body, closeButton);
  pageAlert.append(frame, content);
  document.body.querySelector("[data-page-alert]")?.remove();
  document.body.prepend(pageAlert);
  initializePageAlert(pageAlert);
  return pageAlert;
};

document.querySelectorAll("[data-page-alert]").forEach(initializePageAlert);

window.iPlaygroundPageAlert = {
  show: createPageAlert,
};
