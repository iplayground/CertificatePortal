const homePage = document.body;
const htmlRoot = document.documentElement;
const homePageI18nScript = document.getElementById("home-page-i18n");
const previewAction = document.getElementById("preview-action");
const feedback = document.getElementById("form-feedback");
const registrationNumber = document.getElementById("registration-number");
const attendeeName = document.getElementById("attendee-name");
const email = document.getElementById("email");
const businessTaxId = document.getElementById("business-tax-id");
const generatedAt = document.getElementById("generated-at");
const eventNameControl = document.getElementById("event-name-control");
let eventNameInput = document.getElementById("event-name");
let eventNameSelect = document.getElementById("event-name-select");
let eventNameTrigger = document.getElementById("event-name-trigger");
let eventNameValue = document.getElementById("event-name-value");
let eventNameOptions = Array.from(document.querySelectorAll("#event-name-options .custom-select-option"));
const documentTypeInput = document.getElementById("document-type");
const documentTypeField = document.getElementById("document-type-field");
const documentTypeSelect = document.getElementById("document-type-select");
const documentTypeTrigger = document.getElementById("document-type-trigger");
const documentTypeValue = document.getElementById("document-type-value");
const documentTypeStaticValue = document.getElementById("document-type-static-value");
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
const documentTypeLabel = document.getElementById("document-type-label");
const registrationNumberLabel = document.getElementById("registration-number-label");
const attendeeNameLabel = document.getElementById("attendee-name-label");
const emailLabel = document.getElementById("email-label");
const businessTaxIdLabel = document.getElementById("business-tax-id-label");
const generatedAtLabel = document.getElementById("generated-at-label");
const copyrightNotice = document.getElementById("copyright-notice");
const homePageI18n = parseHomePageI18n();
let currentLocale = homePage.dataset.currentLocale ?? "zh-TW";
const localeCookieName = homePage.dataset.localeCookieName ?? "ipg_locale";
const localeCookieMaxAge = Number.parseInt(homePage.dataset.localeCookieMaxAge ?? "31536000", 10);
const eventsApiPath = homePage.dataset.eventsApiPath ?? "/api/v1/events";
let emptyNameText = homePage.dataset.emptyNameText ?? "未填寫姓名";
let emptyEmailText = homePage.dataset.emptyEmailText ?? "未填寫 email";
let previewFeedbackTemplate = homePage.dataset.previewFeedbackTemplate ?? "";
const { installDateTimePicker } = window.iPlaygroundPortalDateTime ?? {};

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

function syncEventNameControlRefs() {
  eventNameInput = document.getElementById("event-name");
  eventNameSelect = document.getElementById("event-name-select");
  eventNameTrigger = document.getElementById("event-name-trigger");
  eventNameValue = document.getElementById("event-name-value");
  eventNameOptions = Array.from(document.querySelectorAll("#event-name-options .custom-select-option"));
}

function resolveDocumentTypeLabel(documentTypeValueText) {
  const selectedOption = documentTypeOptions.find((item) => item.dataset.value === documentTypeValueText);
  return selectedOption?.textContent?.trim() || documentTypeValueText;
}

function findEventNameOption(normalizedEventName) {
  return eventNameOptions.find((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    return optionValue === normalizedEventName;
  });
}

function parseDocumentTypesValue(rawDocumentTypes) {
  return rawDocumentTypes
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function getCurrentEventDocumentTypes() {
  return parseDocumentTypesValue(
    eventNameInput.dataset.eventDocumentTypes ?? eventNameValue?.dataset.eventDocumentTypes ?? "",
  );
}

function syncCurrentEventMetadata(selectedOption) {
  const rawDocumentTypes = selectedOption?.dataset.eventDocumentTypes ?? "";
  const eventId = selectedOption?.dataset.eventId ?? "";

  eventNameInput.dataset.eventId = eventId;
  eventNameInput.dataset.eventDocumentTypes = rawDocumentTypes;

  if (eventNameValue) {
    eventNameValue.dataset.eventDocumentTypes = rawDocumentTypes;
  }

  return parseDocumentTypesValue(rawDocumentTypes);
}

function getSelectedEventDocumentTypes(normalizedEventName) {
  const selectedOption = findEventNameOption(normalizedEventName);
  if (selectedOption) {
    return syncCurrentEventMetadata(selectedOption);
  }

  return getCurrentEventDocumentTypes();
}

function getVisibleDocumentTypeOptions() {
  return documentTypeOptions.filter((item) => !item.hidden);
}

function applyAvailableDocumentTypes(availableDocumentTypes) {
  if (!Array.isArray(availableDocumentTypes) || availableDocumentTypes.length === 0) {
    documentTypeOptions.forEach((item) => {
      item.hidden = true;
    });
    const currentBundle = getLocaleBundle(currentLocale);
    const currentHomePageCopy = currentBundle?.home_page ?? {};
    const emptyDocumentTypeText = currentHomePageCopy.document_type_empty_option ?? "";
    documentTypeInput.value = "";
    updateTextContent(documentTypeValue, emptyDocumentTypeText);
    updateTextContent(documentTypeStaticValue, emptyDocumentTypeText);
    updateUserDataFieldsForDocumentType("");
    updateDocumentTypeControlMode();
    updatePreviewActionState();
    return;
  }

  documentTypeOptions.forEach((item) => {
    item.hidden = !availableDocumentTypes.includes(item.dataset.value ?? "");
  });

  const selectedOption = documentTypeOptions.find((item) => {
    return item.dataset.value === documentTypeInput.value && !item.hidden;
  });
  if (selectedOption) {
    applyDocumentTypeValue(documentTypeInput.value);
    updateDocumentTypeControlMode();
    return;
  }

  const firstAvailableOption = getVisibleDocumentTypeOptions()[0];
  applyDocumentTypeValue(firstAvailableOption?.dataset.value ?? "");
  updateDocumentTypeControlMode();
}

function applyDocumentTypeLoadingState(homePageCopy) {
  const loadingText = homePageCopy.document_type_loading_option ?? "";
  if (!loadingText) {
    return;
  }

  updateTextContent(documentTypeValue, loadingText);
  updateTextContent(documentTypeStaticValue, loadingText);
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

  applyAvailableDocumentTypes(getSelectedEventDocumentTypes(normalizedValue));
}

function applyDocumentTypeValue(nextValue) {
  const normalizedValue = nextValue?.trim();
  if (!normalizedValue) {
    updateUserDataFieldsForDocumentType("");
    return;
  }

  documentTypeInput.value = normalizedValue;
  documentTypeValue.textContent = resolveDocumentTypeLabel(normalizedValue);
  updateTextContent(documentTypeStaticValue, resolveDocumentTypeLabel(normalizedValue));

  documentTypeOptions.forEach((item) => {
    const optionValue = item.dataset.value ?? item.textContent?.trim() ?? "";
    const isSelected = optionValue === normalizedValue;
    item.classList.toggle("is-selected", isSelected);
    item.setAttribute("aria-selected", String(isSelected));
  });

  updateUserDataFieldsForDocumentType(normalizedValue);
  updatePreviewActionState();
}

function updateDocumentTypeControlMode() {
  const useStaticValue = getVisibleDocumentTypeOptions().length <= 1;

  if (documentTypeStaticValue) {
    documentTypeStaticValue.hidden = !useStaticValue;
  }

  if (documentTypeTrigger) {
    documentTypeTrigger.hidden = useStaticValue;
    documentTypeTrigger.setAttribute("aria-hidden", String(useStaticValue));
    documentTypeTrigger.tabIndex = useStaticValue ? -1 : 0;
  }

  if (useStaticValue) {
    closeDocumentTypeSelect();
  }
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

function buildEventDocumentTypesValue(documentTypes) {
  if (!Array.isArray(documentTypes)) {
    return "";
  }

  return documentTypes
    .map((item) => String(item).trim())
    .filter(Boolean)
    .join(",");
}

function buildEmptyEventControlHtml(emptyEventNameText) {
  return `<input id="event-name" name="eventName" type="hidden" value="">` +
    `<div class="field-static-value" id="event-name-value">${emptyEventNameText}</div>`;
}

function buildSingleEventControlHtml(eventData) {
  return `<input id="event-name" name="eventName" type="hidden">` +
    `<div class="field-static-value" id="event-name-value"></div>`;
}

function setDocumentTypeFieldVisible(isVisible) {
  if (documentTypeField) {
    documentTypeField.hidden = !isVisible;
  }

  if (!isVisible) {
    closeDocumentTypeSelect();
    updateUserDataFieldsForDocumentType("");
  }
}

function renderSingleEventControl(eventData) {
  eventNameControl.innerHTML = buildSingleEventControlHtml(eventData);
  syncEventNameControlRefs();
  eventNameInput.value = eventData.name;
  eventNameInput.dataset.eventId = eventData.id;
  eventNameInput.dataset.eventDocumentTypes = buildEventDocumentTypesValue(eventData.documentTypes);
  eventNameValue.textContent = eventData.name;
  eventNameValue.dataset.eventDocumentTypes = eventNameInput.dataset.eventDocumentTypes;
}

function renderMultipleEventControl(events) {
  eventNameControl.innerHTML = `
    <div class="custom-select" id="event-name-select">
      <input id="event-name" name="eventName" type="hidden">
      <button class="custom-select-trigger" id="event-name-trigger" type="button"
        aria-expanded="false" aria-haspopup="listbox" aria-controls="event-name-options"
        aria-labelledby="event-name-label event-name-value">
        <span id="event-name-value" class="custom-select-value"></span>
        <span class="select-caret" aria-hidden="true"></span>
      </button>
      <div class="custom-select-menu" id="event-name-options" role="listbox" hidden></div>
    </div>
  `;
  syncEventNameControlRefs();

  const eventNameMenu = document.getElementById("event-name-options");
  events.forEach((eventData, index) => {
    const option = document.createElement("button");
    option.className = `custom-select-option${index === 0 ? " is-selected" : ""}`;
    option.type = "button";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(index === 0));
    option.dataset.value = eventData.name;
    option.dataset.eventId = eventData.id;
    option.dataset.eventDocumentTypes = buildEventDocumentTypesValue(eventData.documentTypes);
    option.textContent = eventData.name;
    eventNameMenu?.append(option);
  });

  syncEventNameControlRefs();
  applyEventNameValue(events[0]?.name ?? "");
}

function renderHomeEvents(events) {
  const normalizedEvents = Array.isArray(events)
    ? events.filter((eventData) => {
        return eventData?.id && eventData?.name && Array.isArray(eventData.documentTypes);
      })
    : [];

  const currentBundle = getLocaleBundle(currentLocale);
  const currentHomePageCopy = currentBundle?.home_page ?? {};
  const emptyEventNameText = currentHomePageCopy.event_name_empty_option ?? "";

  if (normalizedEvents.length === 0) {
    eventNameControl.innerHTML = buildEmptyEventControlHtml(emptyEventNameText);
    syncEventNameControlRefs();
    setDocumentTypeFieldVisible(false);
    applyAvailableDocumentTypes([]);
    applyDocumentTypeValue("completionCert");
    return;
  }

  if (normalizedEvents.length === 1) {
    renderSingleEventControl(normalizedEvents[0]);
    setDocumentTypeFieldVisible(true);
    applyAvailableDocumentTypes(normalizedEvents[0].documentTypes);
    return;
  }

  setDocumentTypeFieldVisible(true);
  renderMultipleEventControl(normalizedEvents);
}

async function loadHomeEvents() {
  try {
    const response = await fetch(eventsApiPath, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      return;
    }

    const payload = await response.json();
    renderHomeEvents(payload?.events);
  } catch {
    return;
  }
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

function getVisibleUserDataInputs() {
  return Array.from(document.querySelectorAll("[data-user-data-field] input, [data-user-data-field] select, [data-user-data-field] textarea"))
    .filter((input) => {
      const field = input.closest("[data-user-data-field]");
      return field && !field.hidden && !input.disabled;
    });
}

function updateUserDataFieldsForDocumentType(documentType) {
  const fields = Array.from(document.querySelectorAll("[data-user-data-field]"));
  fields.forEach((field) => {
    const supportedDocumentTypes = (field.dataset.documentTypes ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    field.hidden = documentTypeField?.hidden || !supportedDocumentTypes.includes(documentType);
  });

  updatePreviewActionState();
}

function isUserDataComplete() {
  const inputs = getVisibleUserDataInputs();
  if (inputs.length === 0) {
    return false;
  }

  return inputs.every((input) => {
    if (input instanceof HTMLInputElement && input.type === "checkbox") {
      return input.checked;
    }

    return input.value.trim() !== "" && input.checkValidity();
  });
}

function updatePreviewActionState() {
  previewAction.disabled = !isUserDataComplete();
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
  if (!eventNameInput.value && eventNameValue) {
    updateTextContent(
      eventNameValue,
      homePageCopy.event_name_loading_option ?? homePageCopy.event_name_empty_option,
    );
  } else {
    applyEventNameValue(eventNameInput.value);
  }
  updateTextContent(documentTypeLabel, homePageCopy.document_type_label);
  updateDocumentTypeOptionLabels(homePageCopy);
  if (!eventNameInput.value) {
    applyDocumentTypeLoadingState(homePageCopy);
  }
  updateTextContent(registrationNumberLabel, homePageCopy.registration_number_label);
  updateTextContent(attendeeNameLabel, homePageCopy.attendee_name_label);
  updateTextContent(emailLabel, homePageCopy.email_label);
  updateTextContent(businessTaxIdLabel, homePageCopy.business_tax_id_label);
  updateTextContent(generatedAtLabel, homePageCopy.generated_at_label);
  updateTextContent(previewAction, homePageCopy.preview_action_label);
  updateTextContent(copyrightNotice, homePageCopy.copyright_notice);

  if (typeof homePageCopy.registration_number_placeholder === "string") {
    registrationNumber.placeholder = homePageCopy.registration_number_placeholder;
  }

  if (typeof homePageCopy.attendee_name_placeholder === "string") {
    attendeeName.placeholder = homePageCopy.attendee_name_placeholder;
  }

  if (typeof homePageCopy.email_placeholder === "string") {
    email.placeholder = homePageCopy.email_placeholder;
  }

  if (typeof homePageCopy.business_tax_id_placeholder === "string") {
    businessTaxId.placeholder = homePageCopy.business_tax_id_placeholder;
  }

  if (typeof homePageCopy.generated_at_placeholder === "string") {
    generatedAt.placeholder = homePageCopy.generated_at_placeholder;
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
  const visibleOptions = getVisibleDocumentTypeOptions();
  if (visibleOptions.length <= 1) {
    closeDocumentTypeSelect();
    return;
  }

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

eventNameControl?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }

  if (target.closest("#event-name-trigger")) {
    if (!canOpenEventNameSelect()) {
      return;
    }

    if (eventNameSelect?.classList.contains("is-open")) {
      closeEventNameSelect({ blurTrigger: true });
      return;
    }

    openEventNameSelect();
    return;
  }

  const option = target.closest("#event-name-options .custom-select-option");
  if (!(option instanceof HTMLButtonElement)) {
    return;
  }

  applyEventNameValue(option.dataset.value ?? option.textContent?.trim() ?? "");
  closeEventNameSelect({ blurTrigger: true });
});

eventNameControl?.addEventListener("keydown", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) {
    return;
  }

  if (target.closest("#event-name-trigger")) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!canOpenEventNameSelect()) {
        return;
      }

      openEventNameSelect();
      eventNameOptions[0]?.focus();
      return;
    }

    if (event.key === "Escape") {
      closeEventNameSelect({ blurTrigger: true });
    }
    return;
  }

  const option = target.closest("#event-name-options .custom-select-option");
  if (!(option instanceof HTMLButtonElement)) {
    return;
  }

  const optionIndex = eventNameOptions.indexOf(option);
  if (event.key === "Escape") {
    event.preventDefault();
    closeEventNameSelect({ blurTrigger: true });
    return;
  }

  if (event.key === "ArrowDown") {
    event.preventDefault();
    eventNameOptions[(optionIndex + 1) % eventNameOptions.length]?.focus();
    return;
  }

  if (event.key === "ArrowUp") {
    event.preventDefault();
    eventNameOptions[(optionIndex - 1 + eventNameOptions.length) % eventNameOptions.length]?.focus();
    return;
  }

  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    applyEventNameValue(option.dataset.value ?? option.textContent?.trim() ?? "");
    closeEventNameSelect({ blurTrigger: true });
    return;
  }

  if (event.key === "Tab") {
    closeEventNameSelect();
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

applyAvailableDocumentTypes(getSelectedEventDocumentTypes(eventNameInput.value));

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
    getVisibleDocumentTypeOptions()[0]?.focus();
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
      const visibleOptions = getVisibleDocumentTypeOptions();
      const visibleIndex = visibleOptions.indexOf(option);
      visibleOptions[(visibleIndex + 1) % visibleOptions.length]?.focus();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      const visibleOptions = getVisibleDocumentTypeOptions();
      const visibleIndex = visibleOptions.indexOf(option);
      visibleOptions[(visibleIndex - 1 + visibleOptions.length) % visibleOptions.length]?.focus();
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
  updatePreviewActionState();
  if (previewAction.disabled) {
    return;
  }

  const name = attendeeName.value.trim() || emptyNameText;
  const emailValue = email.value.trim() || emptyEmailText;

  feedback.hidden = false;
  feedback.classList.add("is-active");
  feedback.textContent = formatPreviewMessage(previewFeedbackTemplate, {
    eventName: eventNameInput.value,
    documentType: resolveDocumentTypeLabel(documentTypeInput.value),
    attendeeName: name,
    email: emailValue,
  });
});

[registrationNumber, attendeeName, email, businessTaxId, generatedAt].forEach((input) => {
  input.addEventListener("input", updatePreviewActionState);
});
if (typeof installDateTimePicker === "function") {
  installDateTimePicker(generatedAt, { includeSeconds: true });
}
updatePreviewActionState();
loadHomeEvents();
