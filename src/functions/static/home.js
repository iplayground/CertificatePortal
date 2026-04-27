const homePage = document.body;
const htmlRoot = document.documentElement;
const homePageI18nScript = document.getElementById("home-page-i18n");
const previewAction = document.getElementById("preview-action");
const feedback = document.getElementById("form-feedback");
const attendeeName = document.getElementById("attendee-name");
const email = document.getElementById("email");
const eventNameInput = document.getElementById("event-name");
const eventNameSelect = document.getElementById("event-name-select");
const eventNameTrigger = document.getElementById("event-name-trigger");
const eventNameValue = document.getElementById("event-name-value");
const eventNameOptions = Array.from(document.querySelectorAll("#event-name-options .custom-select-option"));
const documentTypeInput = document.getElementById("document-type");
const documentTypeSelect = document.getElementById("document-type-select");
const documentTypeTrigger = document.getElementById("document-type-trigger");
const documentTypeValue = document.getElementById("document-type-value");
const documentTypeOptions = Array.from(document.querySelectorAll("#document-type-options .custom-select-option"));
const localeSwitcher = document.getElementById("locale-switcher");
const localeTrigger = document.getElementById("locale-trigger");
const localeTriggerValue = localeTrigger?.querySelector(".locale-trigger-value") ?? null;
const localeMenu = document.getElementById("locale-options");
const localeOptions = Array.from(document.querySelectorAll(".locale-menu-option"));
const heroTitle = document.getElementById("page-title");
const heroLead = document.getElementById("hero-lead");
const formTitle = document.getElementById("form-title");
const formSubtitle = document.getElementById("form-subtitle");
const metaApplicationName = document.getElementById("meta-application-name");
const metaDescription = document.getElementById("meta-description");
const metaOgLocale = document.getElementById("meta-og-locale");
const metaOgTitle = document.getElementById("meta-og-title");
const metaOgDescription = document.getElementById("meta-og-description");
const metaOgImageAlt = document.getElementById("meta-og-image-alt");
const eventNameLabel = document.getElementById("event-name-label");
const eventNameHint = document.getElementById("event-name-hint");
const documentTypeLabel = document.getElementById("document-type-label");
const documentTypeHint = document.getElementById("document-type-hint");
const attendeeNameLabel = document.getElementById("attendee-name-label");
const emailLabel = document.getElementById("email-label");
const secondaryNote = document.getElementById("secondary-note");
const footnote = document.getElementById("footnote");
const copyrightNotice = document.getElementById("copyright-notice");
const homePageI18n = parseHomePageI18n();
let currentLocale = homePage.dataset.currentLocale ?? "zh-TW";
const localeCookieName = homePage.dataset.localeCookieName ?? "ipg_locale";
const localeCookieMaxAge = Number.parseInt(homePage.dataset.localeCookieMaxAge ?? "31536000", 10);
let emptyNameText = homePage.dataset.emptyNameText ?? "未填寫姓名";
let emptyEmailText = homePage.dataset.emptyEmailText ?? "未填寫 email";
let previewFeedbackTemplate = homePage.dataset.previewFeedbackTemplate ?? "";

function parseHomePageI18n() {
  if (!(homePageI18nScript instanceof HTMLScriptElement)) {
    return {};
  }

  try {
    const parsed = JSON.parse(homePageI18nScript.textContent ?? "{}");
    if (!parsed || typeof parsed !== "object") {
      return {};
    }

    return parsed;
  } catch {
    return {};
  }
}

function getLocaleBundle(locale) {
  const bundle = homePageI18n[locale];
  if (!bundle || typeof bundle !== "object") {
    return null;
  }

  return bundle;
}

function setLocalePreference(locale) {
  const encodedLocale = encodeURIComponent(locale);
  document.cookie = `${localeCookieName}=${encodedLocale}; Max-Age=${localeCookieMaxAge}; Path=/; SameSite=Lax`;
}

function updateTextContent(element, text) {
  if (!element || typeof text !== "string") {
    return;
  }

  element.textContent = text;
}

function updateMetaContent(element, content) {
  if (!(element instanceof HTMLMetaElement) || typeof content !== "string") {
    return;
  }

  element.content = content;
}

function resolveDocumentTypeLabel(documentTypeValueText) {
  const selectedOption = documentTypeOptions.find((item) => item.dataset.value === documentTypeValueText);
  return selectedOption?.textContent?.trim() || documentTypeValueText;
}

function applyEventNameValue(nextValue) {
  const normalizedValue = nextValue?.trim();
  const currentBundle = getLocaleBundle(currentLocale);
  const currentHomePageCopy = currentBundle?.home_page ?? {};
  const emptyEventNameText = currentHomePageCopy.event_name_empty_option ?? "";

  eventNameInput.value = normalizedValue;
  eventNameValue.textContent = normalizedValue || emptyEventNameText;

  eventNameOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function applyDocumentTypeValue(nextValue) {
  const normalizedValue = nextValue?.trim();
  if (!normalizedValue) {
    return;
  }

  documentTypeInput.value = normalizedValue;
  documentTypeValue.textContent = resolveDocumentTypeLabel(normalizedValue);

  documentTypeOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });
}

function updateDocumentTypeOptionLabels(homePageCopy) {
  documentTypeOptions.forEach((item) => {
    const labelKey = item.dataset.labelKey ?? "";
    const label = homePageCopy[labelKey];
    if (typeof label === "string") {
      item.textContent = label;
    }
  });

  applyDocumentTypeValue(documentTypeInput.value);
}

function formatPreviewMessage(template, replacements) {
  return Object.entries(replacements).reduce((message, [key, value]) => {
    return message.split(`{${key}}`).join(value);
  }, template);
}

function updateLocaleOptionState(selectedLocale, localeOptionLabels) {
  localeOptions.forEach((button) => {
    const optionLocale = button.dataset.locale ?? "";
    const isCurrent = optionLocale === selectedLocale;

    button.textContent = localeOptionLabels[optionLocale] ?? optionLocale;
    button.classList.toggle("is-current", isCurrent);
    button.setAttribute("aria-selected", String(isCurrent));
  });
}

function updateFeedbackCopy(initialFeedbackText) {
  if (!feedback.classList.contains("is-active")) {
    updateTextContent(feedback, initialFeedbackText);
    return;
  }

  const name = attendeeName.value.trim() || emptyNameText;
  const emailValue = email.value.trim() || emptyEmailText;
  feedback.textContent = formatPreviewMessage(previewFeedbackTemplate, {
    eventName: eventNameInput.value,
    documentType: resolveDocumentTypeLabel(documentTypeInput.value),
    attendeeName: name,
    email: emailValue,
  });
}

function applyHomePageLocale(nextLocale) {
  const bundle = getLocaleBundle(nextLocale);
  if (!bundle) {
    setLocalePreference(nextLocale);
    window.location.reload();
    return;
  }

  const homePageCopy = bundle.home_page;
  const localeOptionLabels = bundle.locale_option_labels;
  if (!homePageCopy || typeof homePageCopy !== "object" || !localeOptionLabels || typeof localeOptionLabels !== "object") {
    setLocalePreference(nextLocale);
    window.location.reload();
    return;
  }

  currentLocale = nextLocale;
  setLocalePreference(nextLocale);

  homePage.dataset.currentLocale = nextLocale;

  if (typeof bundle.html_lang === "string") {
    htmlRoot.lang = bundle.html_lang;
  }

  if (typeof bundle.open_graph_locale === "string") {
    updateMetaContent(metaOgLocale, bundle.open_graph_locale);
  }

  if (typeof homePageCopy.page_title === "string") {
    document.title = homePageCopy.page_title;
    updateMetaContent(metaApplicationName, homePageCopy.page_title);
    updateMetaContent(metaOgTitle, homePageCopy.page_title);
  }

  if (typeof homePageCopy.page_description === "string") {
    updateMetaContent(metaDescription, homePageCopy.page_description);
    updateMetaContent(metaOgDescription, homePageCopy.page_description);
  }

  if (typeof homePageCopy.meta_image_alt === "string") {
    updateMetaContent(metaOgImageAlt, homePageCopy.meta_image_alt);
  }

  if (typeof homePageCopy.locale_switcher_label === "string") {
    localeTrigger?.setAttribute("aria-label", homePageCopy.locale_switcher_label);
  }

  updateTextContent(localeTriggerValue, localeOptionLabels[nextLocale] ?? nextLocale);
  updateLocaleOptionState(nextLocale, localeOptionLabels);
  updateTextContent(heroTitle, homePageCopy.hero_title);
  updateTextContent(heroLead, homePageCopy.hero_lead);
  updateTextContent(formTitle, homePageCopy.form_title);
  updateTextContent(formSubtitle, homePageCopy.form_subtitle);
  updateTextContent(eventNameLabel, homePageCopy.event_name_label);
  updateTextContent(eventNameHint, homePageCopy.event_name_hint);
  applyEventNameValue(eventNameInput.value);
  updateTextContent(documentTypeLabel, homePageCopy.document_type_label);
  updateTextContent(documentTypeHint, homePageCopy.document_type_hint);
  updateDocumentTypeOptionLabels(homePageCopy);
  updateTextContent(attendeeNameLabel, homePageCopy.attendee_name_label);
  updateTextContent(emailLabel, homePageCopy.email_label);
  updateTextContent(previewAction, homePageCopy.preview_action_label);
  updateTextContent(secondaryNote, homePageCopy.secondary_note);
  updateTextContent(footnote, homePageCopy.footnote);
  updateTextContent(copyrightNotice, homePageCopy.copyright_notice);

  if (typeof homePageCopy.attendee_name_placeholder === "string") {
    attendeeName.placeholder = homePageCopy.attendee_name_placeholder;
  }

  if (typeof homePageCopy.email_placeholder === "string") {
    email.placeholder = homePageCopy.email_placeholder;
  }

  if (typeof homePageCopy.empty_name_text === "string") {
    emptyNameText = homePageCopy.empty_name_text;
    homePage.dataset.emptyNameText = emptyNameText;
  }

  if (typeof homePageCopy.empty_email_text === "string") {
    emptyEmailText = homePageCopy.empty_email_text;
    homePage.dataset.emptyEmailText = emptyEmailText;
  }

  if (typeof homePageCopy.preview_feedback_template === "string") {
    previewFeedbackTemplate = homePageCopy.preview_feedback_template;
    homePage.dataset.previewFeedbackTemplate = previewFeedbackTemplate;
  }

  updateFeedbackCopy(homePageCopy.form_feedback_initial);
  closeLocaleMenu({ blurTrigger: true });
}

function applyLocaleSelection(nextLocale) {
  if (!nextLocale || nextLocale === currentLocale) {
    closeLocaleMenu({ blurTrigger: true });
    return;
  }

  applyHomePageLocale(nextLocale);
}

function closeEventNameSelect({ blurTrigger = false } = {}) {
  eventNameSelect?.classList.remove("is-open");
  eventNameTrigger?.setAttribute("aria-expanded", "false");
  const eventNameMenu = document.getElementById("event-name-options");
  if (eventNameMenu) {
    eventNameMenu.hidden = true;
  }

  if (blurTrigger) {
    eventNameTrigger?.blur();
  }
}

function canOpenEventNameSelect() {
  return eventNameOptions.length > 1;
}

function openEventNameSelect() {
  if (!canOpenEventNameSelect()) {
    closeEventNameSelect();
    return;
  }

  eventNameSelect?.classList.add("is-open");
  eventNameTrigger?.setAttribute("aria-expanded", "true");
  const eventNameMenu = document.getElementById("event-name-options");
  if (eventNameMenu) {
    eventNameMenu.hidden = false;
  }
}

function closeDocumentTypeSelect({ blurTrigger = false } = {}) {
  documentTypeSelect.classList.remove("is-open");
  documentTypeTrigger.setAttribute("aria-expanded", "false");
  document.getElementById("document-type-options").hidden = true;
  if (blurTrigger) {
    documentTypeTrigger.blur();
  }
}

function openDocumentTypeSelect() {
  documentTypeSelect.classList.add("is-open");
  documentTypeTrigger.setAttribute("aria-expanded", "true");
  document.getElementById("document-type-options").hidden = false;
}

function closeLocaleMenu({ blurTrigger = false } = {}) {
  homePage.classList.remove("is-locale-menu-open");
  localeSwitcher?.classList.remove("is-open");
  localeTrigger?.setAttribute("aria-expanded", "false");

  if (localeMenu) {
    localeMenu.hidden = true;
  }

  if (blurTrigger) {
    localeTrigger?.blur();
  }
}

function openLocaleMenu() {
  homePage.classList.add("is-locale-menu-open");
  localeSwitcher?.classList.add("is-open");
  localeTrigger?.setAttribute("aria-expanded", "true");

  if (localeMenu) {
    localeMenu.hidden = false;
  }
}

eventNameTrigger?.addEventListener("click", () => {
  if (!canOpenEventNameSelect()) {
    return;
  }

  if (eventNameSelect?.classList.contains("is-open")) {
    closeEventNameSelect({ blurTrigger: true });
    return;
  }

  openEventNameSelect();
});

eventNameTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (!canOpenEventNameSelect()) {
      return;
    }

    openEventNameSelect();
    eventNameOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeEventNameSelect({ blurTrigger: true });
  }
});

eventNameOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyEventNameValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeEventNameSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeEventNameSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      eventNameOptions[(index + 1) % eventNameOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      eventNameOptions[(index - 1 + eventNameOptions.length) % eventNameOptions.length]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeEventNameSelect();
    }
  });
});

documentTypeTrigger.addEventListener("click", () => {
  if (documentTypeSelect.classList.contains("is-open")) {
    closeDocumentTypeSelect({ blurTrigger: true });
    return;
  }

  openDocumentTypeSelect();
});

documentTypeTrigger.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openDocumentTypeSelect();
    documentTypeOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeDocumentTypeSelect({ blurTrigger: true });
  }
});

documentTypeOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    applyDocumentTypeValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeDocumentTypeSelect({ blurTrigger: true });
  });

  option.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeDocumentTypeSelect({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      documentTypeOptions[(index + 1) % documentTypeOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      documentTypeOptions[(index - 1 + documentTypeOptions.length) % documentTypeOptions.length]?.focus();
      return;
    }

    if (event.key === "Tab") {
      closeDocumentTypeSelect();
    }
  });
});

document.addEventListener("click", (event) => {
  if (eventNameSelect instanceof HTMLElement && !eventNameSelect.contains(event.target)) {
    closeEventNameSelect();
  }

  if (!documentTypeSelect.contains(event.target)) {
    closeDocumentTypeSelect();
  }
});

localeTrigger?.addEventListener("click", () => {
  if (localeSwitcher?.classList.contains("is-open")) {
    closeLocaleMenu({ blurTrigger: true });
    return;
  }

  openLocaleMenu();
});

localeTrigger?.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openLocaleMenu();

    const currentOption =
      localeOptions.find((button) => button.classList.contains("is-current")) ?? localeOptions[0];
    currentOption?.focus();
    return;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    closeLocaleMenu({ blurTrigger: true });
  }
});

localeOptions.forEach((button, index) => {
  button.addEventListener("click", () => {
    applyLocaleSelection(button.dataset.locale);
  });

  button.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeLocaleMenu({ blurTrigger: true });
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      localeOptions[(index + 1) % localeOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      localeOptions[(index - 1 + localeOptions.length) % localeOptions.length]?.focus();
      return;
    }

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      applyLocaleSelection(button.dataset.locale);
      return;
    }

    if (event.key === "Tab") {
      closeLocaleMenu();
    }
  });
});

localeMenu?.addEventListener("pointerdown", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }

  const option = event.target.closest(".locale-menu-option");
  if (!(option instanceof HTMLButtonElement)) {
    return;
  }

  event.preventDefault();
  applyLocaleSelection(option.dataset.locale);
});

document.addEventListener("click", (event) => {
  if (localeSwitcher?.classList.contains("is-open") && !localeSwitcher.contains(event.target)) {
    closeLocaleMenu();
  }
});

previewAction.addEventListener("click", () => {
  const name = attendeeName.value.trim() || emptyNameText;
  const emailValue = email.value.trim() || emptyEmailText;

  feedback.classList.add("is-active");
  feedback.textContent = formatPreviewMessage(previewFeedbackTemplate, {
    eventName: eventNameInput.value,
    documentType: resolveDocumentTypeLabel(documentTypeInput.value),
    attendeeName: name,
    email: emailValue,
  });
});
