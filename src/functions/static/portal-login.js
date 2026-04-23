const actionLinks = Array.from(document.querySelectorAll(".portal-action-link"));

actionLinks.forEach((link) => {
  link.addEventListener("click", () => {
    if (link.getAttribute("aria-disabled") === "true") {
      return;
    }

    const loadingLabel = link.dataset.loadingLabel?.trim();
    if (loadingLabel) {
      link.textContent = loadingLabel;
    }

    link.setAttribute("aria-disabled", "true");
    link.classList.add("is-busy");
  });
});
