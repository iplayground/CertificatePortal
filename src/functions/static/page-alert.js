const pageAlerts = Array.from(document.querySelectorAll("[data-page-alert]"));

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

pageAlerts.forEach((pageAlert) => {
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
});
