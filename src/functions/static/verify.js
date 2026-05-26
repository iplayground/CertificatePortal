(function () {
  const verifyPage = document.body;
  const htmlRoot = document.documentElement;
  const verifyPageI18nScript = document.getElementById("verify-page-i18n");
  const localeTrigger = document.getElementById("locale-trigger");
  const localeTriggerValue = localeTrigger?.querySelector(".locale-trigger-value") ?? null;
  const localeOptions = Array.from(document.querySelectorAll(".locale-menu-option"));
  const metaDescription = document.getElementById("meta-description");
  const metaOgLocale = document.getElementById("meta-og-locale");
  const metaOgTitle = document.getElementById("meta-og-title");
  const metaOgDescription = document.getElementById("meta-og-description");
  const brandLogo = document.getElementById("brand-logo");
  const verifyTitle = document.getElementById("verify-title");
  const verifySummary = document.getElementById("verify-summary");
  const statusLabel = document.getElementById("status-label");
  const privacyNote = document.getElementById("privacy-note");
  const copyrightNotice = document.getElementById("copyright-notice");
  const homeAction = document.getElementById("home-action");
  const verifyPageI18n = parseVerifyPageI18n();
  const resultKind = resolveResultKind();
  let currentLocale = verifyPage.dataset.currentLocale ?? "zh-TW";

  window.iPlaygroundLocaleSwitcher?.installLocaleSwitcher({
    cookieMaxAge: Number.parseInt(verifyPage.dataset.localeCookieMaxAge ?? "31536000", 10),
    cookieName: verifyPage.dataset.localeCookieName ?? "ipg_locale",
    currentLocale,
    onSelect: applyLocaleSelection,
    root: verifyPage,
  });

  formatLocalDateTimes(currentLocale);

  function parseVerifyPageI18n() {
    if (!verifyPageI18nScript?.textContent) {
      return {};
    }

    try {
      const payload = JSON.parse(verifyPageI18nScript.textContent);
      return payload && typeof payload === "object" ? payload : {};
    } catch {
      return {};
    }
  }

  function resolveResultKind() {
    const match = Array.from(verifyPage.classList)
      .find((className) => className.startsWith("verify-page--"))
      ?.replace("verify-page--", "");
    return match || "invalid";
  }

  function updateTextContent(element, value) {
    if (element && typeof value === "string") {
      element.textContent = value;
    }
  }

  function updateMetaContent(element, value) {
    if (element && typeof value === "string") {
      element.setAttribute("content", value);
    }
  }

  function updateLocaleOptionState(selectedLocale, localeOptionLabels) {
    localeOptions.forEach((button) => {
      const optionLocale = button.dataset.locale ?? "";
      const isCurrent = optionLocale === selectedLocale;
      button.classList.toggle("is-current", isCurrent);
      button.setAttribute("aria-selected", isCurrent ? "true" : "false");
      button.textContent = localeOptionLabels[optionLocale] ?? optionLocale;
    });
  }

  function updateDetailLabels(copy) {
    const labelByKey = {
      certificateType: copy.certificate_type_label,
      certificateNumber: copy.certificate_number_label,
      eventName: copy.event_name_label,
      issuedAt: copy.issued_at_label,
      organization: copy.organization_label,
      recipientName: copy.recipient_name_label,
      status: copy.status_label,
    };

    Object.entries(labelByKey).forEach(([key, label]) => {
      const labelElement = document.querySelector(`[data-detail-key="${key}"] .verification-detail-label`);
      updateTextContent(labelElement, label);
    });
  }

  function updateStatusValue(copy) {
    const statusValue = copy[`status_${resultKind}`];
    const statusValueElement = document.querySelector('[data-detail-key="status"] .verification-detail-value');
    updateTextContent(statusValueElement, statusValue);
  }

  function updateInvalidEmptyValues(copy) {
    if (resultKind !== "invalid") {
      return;
    }

    document.querySelectorAll('[data-detail-key]:not([data-detail-key="status"]) .verification-detail-value')
      .forEach((element) => updateTextContent(element, copy.empty_value));
  }

  function applyVerifyPageLocale(nextLocale) {
    const bundle = verifyPageI18n[nextLocale];
    if (!bundle) {
      window.iPlaygroundLocaleSwitcher?.setLocalePreference({
        locale: nextLocale,
        cookieMaxAge: Number.parseInt(verifyPage.dataset.localeCookieMaxAge ?? "31536000", 10),
        cookieName: verifyPage.dataset.localeCookieName ?? "ipg_locale",
      });
      window.location.reload();
      return;
    }

    const copy = bundle.verify_page;
    const localeOptionLabels = bundle.locale_option_labels;
    if (!copy || typeof copy !== "object" || !localeOptionLabels || typeof localeOptionLabels !== "object") {
      window.location.reload();
      return;
    }

    currentLocale = nextLocale;
    window.iPlaygroundLocaleSwitcher?.setLocalePreference({
      locale: nextLocale,
      cookieMaxAge: Number.parseInt(verifyPage.dataset.localeCookieMaxAge ?? "31536000", 10),
      cookieName: verifyPage.dataset.localeCookieName ?? "ipg_locale",
    });
    verifyPage.dataset.currentLocale = nextLocale;

    if (typeof bundle.html_lang === "string") {
      htmlRoot.lang = bundle.html_lang;
    }

    if (typeof bundle.open_graph_locale === "string") {
      updateMetaContent(metaOgLocale, bundle.open_graph_locale);
    }

    if (typeof copy.page_title === "string") {
      document.title = copy.page_title;
      updateMetaContent(metaOgTitle, copy.page_title);
    }

    updateMetaContent(metaDescription, copy.page_description);
    updateMetaContent(metaOgDescription, copy.page_description);
    localeTrigger?.setAttribute("aria-label", copy.locale_switcher_label);
    updateTextContent(localeTriggerValue, localeOptionLabels[nextLocale] ?? nextLocale);
    updateLocaleOptionState(nextLocale, localeOptionLabels);
    brandLogo?.setAttribute("alt", copy.brand_alt ?? "iPlayground");
    updateTextContent(statusLabel, copy.status_label);
    updateTextContent(verifyTitle, copy[`${resultKind}_title`]);
    updateTextContent(verifySummary, copy[`${resultKind}_summary`]);
    updateDetailLabels(copy);
    updateStatusValue(copy);
    updateInvalidEmptyValues(copy);
    updateTextContent(privacyNote, copy.privacy_note);
    updateTextContent(copyrightNotice, copy.copyright_notice);
    updateTextContent(homeAction, copy.home_action_label);
    formatLocalDateTimes(nextLocale);
  }

  function applyLocaleSelection(nextLocale) {
    if (!nextLocale || nextLocale === currentLocale) {
      return;
    }

    applyVerifyPageLocale(nextLocale);
  }

  function formatLocalDateTimes(locale) {
    const issuedAtElements = document.querySelectorAll(".local-datetime[datetime]");
    if (!issuedAtElements.length || typeof Intl === "undefined") {
      return;
    }

    let formatter;
    try {
      formatter = new Intl.DateTimeFormat(locale || navigator.language, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZoneName: "short",
      });
    } catch {
      return;
    }

    issuedAtElements.forEach((element) => {
      const issuedAt = new Date(element.dateTime);
      if (Number.isNaN(issuedAt.getTime())) {
        return;
      }

      element.textContent = formatter.format(issuedAt);
    });
  }
})();
