const homePage = document.body;
const htmlRoot = document.documentElement;
const homePageI18nScript = document.getElementById("home-page-i18n");
const documentRequestForm = document.getElementById("document-request-form");
const previewAction = document.getElementById("preview-action");
const feedback = document.getElementById("form-feedback");
const pageLoadingOverlay = document.getElementById("page-loading-overlay");
const certificateOptionsView = document.getElementById("certificate-options-view");
const certificateOptionsTitle = document.getElementById("certificate-options-title");
const certificateOptionsSubtitle = document.getElementById("certificate-options-subtitle");
const certificateNameOptionsLabel = document.getElementById("certificate-name-options-label");
const certificateNameOptions = document.getElementById("certificate-name-options");
const certificateCompanyOptionField = document.getElementById("certificate-company-option-field");
const certificateCompanyOptionLabel = document.getElementById("certificate-company-option-label");
const certificateCompanyOptionText = document.getElementById("certificate-company-option-text");
const certificateCompanyVisible = document.getElementById("certificate-company-visible");
const certificatePreview = document.getElementById("certificate-preview");
const certificatePreviewTitle = document.getElementById("certificate-preview-title");
const certificatePreviewSubtitle = document.getElementById("certificate-preview-subtitle");
const certificatePreviewImage = document.getElementById("certificate-preview-image");
const certificatePreviewLoading = document.getElementById("certificate-preview-loading");
const certificateOptionsBackAction = document.getElementById("certificate-options-back-action");
const certificateChangeRequestAction = document.getElementById("certificate-change-request-action");
const certificateGenerateAction = document.getElementById("certificate-generate-action");
const certificateGenerateWarning = document.getElementById("certificate-generate-warning");
const certificateChangeRequestProcessingFeedback = document.getElementById(
  "certificate-change-request-processing-feedback"
);
const certificateChangeRequestProcessingDefaultMessage =
  certificateChangeRequestProcessingFeedback?.textContent ?? "";
const certificateChangeRequestView = document.getElementById("certificate-change-request-view");
const certificateChangeRequestForm = document.getElementById("certificate-change-request-form");
const certificateChangeRequestTitle = document.getElementById("certificate-change-request-title");
const certificateChangeRequestSubtitle = document.getElementById("certificate-change-request-subtitle");
const certificateChangeRequestEventLabel = document.getElementById("certificate-change-request-event-label");
const certificateChangeRequestEventValue = document.getElementById("certificate-change-request-event-value");
const certificateChangeRequestRegistrationNumberLabel = document.getElementById(
  "certificate-change-request-registration-number-label"
);
const certificateChangeRequestRegistrationNumberValue = document.getElementById(
  "certificate-change-request-registration-number-value"
);
const certificateChangeRequestEmailLabel = document.getElementById("certificate-change-request-email-label");
const certificateChangeRequestEmailValue = document.getElementById("certificate-change-request-email-value");
const certificateChangeRequestNoteLabel = document.getElementById("certificate-change-request-note-label");
const certificateChangeRequestNote = document.getElementById("certificate-change-request-note");
const certificateChangeRequestNoteHint = document.getElementById("certificate-change-request-note-hint");
const certificateChangeRequestBackAction = document.getElementById("certificate-change-request-back-action");
const certificateChangeRequestSubmitAction = document.getElementById("certificate-change-request-submit-action");
const certificateChangeRequestFeedback = document.getElementById("certificate-change-request-feedback");
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
const documentLookupApiPath = homePage.dataset.documentLookupApiPath ?? "/api/v1/document-lookup";
const certificateChangeRequestApiPath =
  homePage.dataset.certificateChangeRequestApiPath ?? "/api/v1/completion-cert-change-requests";
const certificateIssueApiPath = homePage.dataset.certificateIssueApiPath ?? "/api/v1/completion-certs/issue";
const certificatePreviewApiPath =
  homePage.dataset.certificatePreviewApiPath ?? "/api/v1/completion-cert-previews";
const lookupBlockedStorageKey = "ipg_document_lookup_blocked_until";
const lookupBlockedClientCacheMs = 60 * 60 * 1000;
let emptyNameText = homePage.dataset.emptyNameText ?? "";
let emptyEmailText = homePage.dataset.emptyEmailText ?? "";
let previewFeedbackTemplate = homePage.dataset.previewFeedbackTemplate ?? "";
let lookupNotFoundMessage = homePage.dataset.lookupNotFoundMessage ?? "";
let lookupNotAvailableYetMessage = homePage.dataset.lookupNotAvailableYetMessage ?? "";
let lookupBlockedMessage = homePage.dataset.lookupBlockedMessage ?? "";
let lookupUnavailableMessage = homePage.dataset.lookupUnavailableMessage ?? "";
let lookupPendingMessage = homePage.dataset.lookupPendingMessage ?? "";
let certificateIssuePendingMessage =
  getLocaleBundle(currentLocale)?.certificate_issue_pending_message ?? "證書產生中，請稍候。";
let certificateDownloadPendingMessage =
  getLocaleBundle(currentLocale)?.certificate_download_pending_message ?? "證書下載準備中，請稍候。";
let isLookupInProgress = false;
let isChangeRequestInProgress = false;
let isChangeRequestSubmitted = false;
let isCertificateIssueInProgress = false;
let certificateOptionsChangeRequestStatus = null;
let currentCertificateDocument = null;
let certificatePreviewImageRequestId = 0;
let eventNameLoadingAnimationTimer = null;
let eventNameLoadingAnimationBaseText = "";
let eventNameLoadingAnimationDotCount = 0;
let isHomeEventsLoading = true;
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

function renderEventNameLoadingAnimationFrame() {
  if (!eventNameValue || !eventNameLoadingAnimationBaseText || eventNameInput.value) {
    return;
  }

  const dots = ".".repeat(eventNameLoadingAnimationDotCount);
  updateTextContent(eventNameValue, `${eventNameLoadingAnimationBaseText}${dots}`);
}

function startEventNameLoadingAnimation(baseText) {
  if (!baseText || eventNameInput.value || !isHomeEventsLoading) {
    return;
  }

  stopEventNameLoadingAnimation();
  eventNameLoadingAnimationBaseText = baseText;
  eventNameLoadingAnimationDotCount = 0;
  renderEventNameLoadingAnimationFrame();
  eventNameLoadingAnimationTimer = window.setInterval(() => {
    eventNameLoadingAnimationDotCount = (eventNameLoadingAnimationDotCount % 6) + 1;
    renderEventNameLoadingAnimationFrame();
  }, 250);
}

function stopEventNameLoadingAnimation() {
  if (eventNameLoadingAnimationTimer !== null) {
    window.clearInterval(eventNameLoadingAnimationTimer);
    eventNameLoadingAnimationTimer = null;
  }

  eventNameLoadingAnimationBaseText = "";
  eventNameLoadingAnimationDotCount = 0;
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
  isHomeEventsLoading = false;
  stopEventNameLoadingAnimation();
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
  isHomeEventsLoading = true;
  const currentBundle = getLocaleBundle(currentLocale);
  const currentHomePageCopy = currentBundle?.home_page ?? {};
  startEventNameLoadingAnimation(currentHomePageCopy.event_name_loading_option ?? "");

  try {
    const response = await fetch(eventsApiPath, {
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      isHomeEventsLoading = false;
      stopEventNameLoadingAnimation();
      return;
    }

    const payload = await response.json();
    renderHomeEvents(payload?.events);
  } catch {
    isHomeEventsLoading = false;
    stopEventNameLoadingAnimation();
    return;
  }
}

function formatPreviewMessage(template, replacements) {
  return Object.entries(replacements).reduce((message, [key, value]) => {
    return message.split(`{${key}}`).join(value);
  }, template);
}

function resolveCertificateOptionCopy(key, fallback = "") {
  const bundle = getLocaleBundle(currentLocale);
  const homePageCopy = bundle?.home_page ?? {};
  const value = homePageCopy[key];
  return typeof value === "string" ? value : fallback;
}

function normalizeLookupDocumentText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function buildCertificateNameChoices(documentData) {
  const name = normalizeLookupDocumentText(documentData?.name);
  const badgeName = normalizeLookupDocumentText(documentData?.badgeName);
  const choices = [];
  const seenLabels = new Set();

  [
    { value: "name", label: name },
    { value: "badgeName", label: badgeName },
    {
      value: "nameWithBadge",
      label: name && badgeName && name !== badgeName ? `${name} (${badgeName})` : "",
    },
  ].forEach((choice) => {
    if (!choice.label || seenLabels.has(choice.label)) {
      return;
    }

    seenLabels.add(choice.label);
    choices.push(choice);
  });

  return choices;
}

function renderCertificateNameOptions(documentData) {
  if (!certificateNameOptions) {
    return;
  }

  const choices = buildCertificateNameChoices(documentData);
  certificateNameOptions.replaceChildren();
  choices.forEach((choice, index) => {
    const option = document.createElement("label");
    option.className = "certificate-choice-option";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = "certificateNameDisplay";
    input.value = choice.value;
    input.checked = index === 0;

    const label = document.createElement("span");
    label.textContent = choice.label;

    option.append(input, label);
    certificateNameOptions.append(option);
  });
}

function setCertificateDisplayControlsLocked(isLocked) {
  certificateNameOptions
    ?.querySelectorAll('input[name="certificateNameDisplay"]')
    .forEach((input) => {
      input.disabled = isLocked;
    });
  if (certificateCompanyVisible) {
    certificateCompanyVisible.disabled = isLocked;
  }
}

function renderCertificateGenerateAction(documentData) {
  const isIssued = documentData?.certStatus === "issued";
  updateTextContent(
    certificateOptionsSubtitle,
    resolveCertificateOptionCopy(
      isIssued ? "certificate_options_download_subtitle" : "certificate_options_subtitle",
    ),
  );
  if (certificateGenerateWarning) {
    certificateGenerateWarning.hidden = isIssued;
  }
  updateTextContent(
    certificateGenerateAction,
    resolveCertificateOptionCopy(
      isIssued ? "certificate_download_action_label" : "certificate_generate_action_label",
    ),
  );
}

function renderCertificateCompanyOption(documentData) {
  const organization = normalizeLookupDocumentText(documentData?.organization);
  if (!certificateCompanyOptionField || !certificateCompanyOptionText || !certificateCompanyVisible) {
    return;
  }

  certificateCompanyOptionField.hidden = !organization;
  certificateCompanyVisible.checked = Boolean(organization);
  if (organization) {
    certificateCompanyOptionText.textContent = formatPreviewMessage(
      resolveCertificateOptionCopy("certificate_company_option_text"),
      { organization },
    );
  }
}

function renderCertificateOptionsStatus(documentData) {
  const isChangeRequested = documentData?.certStatus === "changeRequested";
  const canRequestChanges = typeof documentData?.canRequestChanges === "boolean"
    ? documentData.canRequestChanges
    : documentData?.certStatus === "notIssued";
  const reviewStatus = documentData?.changeRequestReview?.status;
  const reviewNote = typeof documentData?.changeRequestReview?.reviewNote === "string"
    ? documentData.changeRequestReview.reviewNote.trim()
    : "";
  let completedReviewMessage = "";
  let completedReviewTone = "success";
  if (reviewStatus === "approved") {
    completedReviewMessage = resolveCertificateOptionCopy(
      "certificate_change_request_approved_message",
    );
  } else if (reviewStatus === "rejected") {
    completedReviewMessage = resolveCertificateOptionCopy(
      "certificate_change_request_rejected_message",
    );
    completedReviewTone = "error";
  }
  if (completedReviewMessage && reviewNote) {
    const reviewNoteLabel = resolveCertificateOptionCopy("certificate_change_request_review_note_label");
    completedReviewMessage = `${completedReviewMessage}\n${reviewNoteLabel}: ${reviewNote}`;
  }
  if (certificateChangeRequestAction) {
    certificateChangeRequestAction.hidden = !canRequestChanges;
  }
  if (certificateChangeRequestProcessingFeedback) {
    const statusMessage = certificateOptionsChangeRequestStatus?.message
      || completedReviewMessage
      || (isChangeRequested ? certificateChangeRequestProcessingDefaultMessage : "");
    const statusTone = certificateOptionsChangeRequestStatus?.tone
      || (completedReviewMessage ? completedReviewTone : "warning");
    certificateChangeRequestProcessingFeedback.hidden = !statusMessage;
    certificateChangeRequestProcessingFeedback.textContent = statusMessage;
    certificateChangeRequestProcessingFeedback.classList.toggle("is-active", Boolean(statusMessage));
    certificateChangeRequestProcessingFeedback.classList.toggle("is-success", Boolean(statusMessage) && statusTone === "success");
    certificateChangeRequestProcessingFeedback.classList.toggle("is-warning", Boolean(statusMessage) && statusTone === "warning");
    certificateChangeRequestProcessingFeedback.classList.toggle("is-error", Boolean(statusMessage) && statusTone === "error");
  }
  const isIssued = documentData?.certStatus === "issued";
  setCertificateDisplayControlsLocked(isIssued);
  if (isIssued) {
    resetCertificateIssuePreview();
  }
  renderCertificateGenerateAction(documentData);
}

function setCertificateOptionsChangeRequestStatus(message, tone) {
  certificateOptionsChangeRequestStatus = { message, tone };
  if (currentCertificateDocument) {
    renderCertificateOptionsStatus(currentCertificateDocument);
  }
}

function clearCertificateOptionsChangeRequestStatus() {
  certificateOptionsChangeRequestStatus = null;
}

function updateCertificateChangeRequestSubmitState() {
  if (!certificateChangeRequestSubmitAction || !certificateChangeRequestNote) {
    return;
  }

  certificateChangeRequestSubmitAction.disabled =
    isChangeRequestInProgress || isChangeRequestSubmitted || certificateChangeRequestNote.value.trim().length === 0;
}

function clearCertificateChangeRequestFeedback() {
  if (!certificateChangeRequestFeedback) {
    return;
  }

  certificateChangeRequestFeedback.hidden = true;
  certificateChangeRequestFeedback.classList.remove("is-active", "is-success", "is-error");
  certificateChangeRequestFeedback.textContent = "";
}

function showCertificateChangeRequestFeedback(message) {
  if (!certificateChangeRequestFeedback) {
    return;
  }

  certificateChangeRequestFeedback.hidden = false;
  certificateChangeRequestFeedback.classList.add("is-active", "is-success");
  certificateChangeRequestFeedback.classList.remove("is-error");
  certificateChangeRequestFeedback.textContent = message;
}

function showCertificateChangeRequestError(message) {
  if (!certificateChangeRequestFeedback) {
    return;
  }

  certificateChangeRequestFeedback.hidden = false;
  certificateChangeRequestFeedback.classList.add("is-active", "is-error");
  certificateChangeRequestFeedback.classList.remove("is-success");
  certificateChangeRequestFeedback.textContent = message;
}

function setChangeRequestBusy(isBusy) {
  isChangeRequestInProgress = isBusy;
  certificateChangeRequestForm?.classList.toggle("is-lookup-busy", isBusy);
  certificateChangeRequestForm?.setAttribute("aria-busy", String(isBusy));
  [certificateChangeRequestBackAction].filter(Boolean).forEach((control) => {
    control.disabled = isBusy;
  });
  if (certificateChangeRequestNote) {
    certificateChangeRequestNote.disabled = isBusy || isChangeRequestSubmitted;
  }
  updateCertificateChangeRequestSubmitState();
}

function setChangeRequestSubmitted(isSubmitted) {
  isChangeRequestSubmitted = isSubmitted;
  if (certificateChangeRequestNote) {
    certificateChangeRequestNote.disabled = isSubmitted;
  }
  updateCertificateChangeRequestSubmitState();
}

function renderCertificateChangeRequestSummary() {
  updateTextContent(certificateChangeRequestEventValue, eventNameInput.value || emptyNameText);
  updateTextContent(certificateChangeRequestRegistrationNumberValue, registrationNumber.value.trim() || emptyNameText);
  updateTextContent(certificateChangeRequestEmailValue, email.value.trim() || emptyEmailText);
}

function buildCertificateChangeRequestPayload() {
  return {
    documentType: "completionCert",
    email: email.value.trim(),
    eventId: eventNameInput.dataset.eventId ?? "",
    registrationNumber: registrationNumber.value.trim(),
    requesterNote: certificateChangeRequestNote?.value.trim() ?? "",
  };
}

function getSelectedCertificateNameDisplay() {
  const selectedOption = certificateNameOptions?.querySelector(
    'input[name="certificateNameDisplay"]:checked',
  );
  return selectedOption instanceof HTMLInputElement ? selectedOption.value : "name";
}

function buildCertificateIssuePayload() {
  return {
    documentType: "completionCert",
    email: email.value.trim(),
    eventId: eventNameInput.dataset.eventId ?? "",
    locale: currentLocale,
    nameDisplay: getSelectedCertificateNameDisplay(),
    registrationNumber: registrationNumber.value.trim(),
    showOrganization: Boolean(certificateCompanyVisible?.checked),
  };
}

function buildCertificatePreviewImageId() {
  const nameDisplay = getSelectedCertificateNameDisplay();
  const organizationDisplay = certificateCompanyVisible?.checked ? "org" : "no-org";
  return `${currentLocale}-${nameDisplay}-${organizationDisplay}.png`;
}

function renderCertificateIssuePreview() {
  if (!certificatePreviewImage) {
    return;
  }

  const imageId = buildCertificatePreviewImageId();
  const imageSrc = `${certificatePreviewApiPath}/${encodeURIComponent(imageId)}`;
  if (certificatePreviewImage.dataset.previewImageId === imageId) {
    return;
  }

  const requestId = ++certificatePreviewImageRequestId;
  certificatePreviewImage.dataset.previewImageId = imageId;
  certificatePreviewImage.classList.add("is-loading");
  if (certificatePreviewLoading) {
    certificatePreviewLoading.hidden = false;
  }

  const nextImage = new Image();
  nextImage.onload = () => {
    if (requestId !== certificatePreviewImageRequestId) {
      return;
    }
    certificatePreviewImage.src = imageSrc;
    certificatePreviewImage.classList.remove("is-loading");
    if (certificatePreviewLoading) {
      certificatePreviewLoading.hidden = true;
    }
  };
  nextImage.onerror = () => {
    if (requestId !== certificatePreviewImageRequestId) {
      return;
    }
    certificatePreviewImage.classList.remove("is-loading");
    if (certificatePreviewLoading) {
      certificatePreviewLoading.hidden = true;
    }
  };
  nextImage.src = imageSrc;
  certificatePreviewImage.alt = resolveCertificateOptionCopy(
    "certificate_preview_title",
  );
}

function showCertificateIssuePreview() {
  if (currentCertificateDocument?.certStatus === "issued") {
    resetCertificateIssuePreview();
    renderCertificateGenerateAction(currentCertificateDocument);
    return;
  }
  renderCertificateIssuePreview();
  if (certificatePreview) {
    certificatePreview.hidden = false;
  }
  renderCertificateGenerateAction(currentCertificateDocument);
  certificatePreview?.scrollIntoView?.({ block: "nearest" });
}

function resetCertificateIssuePreview() {
  if (certificatePreview) {
    certificatePreview.hidden = true;
  }
  if (certificatePreviewImage) {
    certificatePreviewImage.removeAttribute("src");
    certificatePreviewImage.removeAttribute("data-preview-image-id");
    certificatePreviewImage.classList.remove("is-loading");
  }
  certificatePreviewImageRequestId += 1;
  if (certificatePreviewLoading) {
    certificatePreviewLoading.hidden = true;
  }
  updateTextContent(
    certificateGenerateAction,
    resolveCertificateOptionCopy("certificate_generate_action_label"),
  );
}

function resolveCertificateIssueFailureMessage(payload) {
  const code = payload?.error?.code;
  const fallbackByCode = {
    certificate_issue_not_allowed: resolveCertificateOptionCopy(
      "certificate_issue_not_allowed_message",
    ),
    invalid_certificate_issue: resolveCertificateOptionCopy(
      "certificate_issue_invalid_message",
    ),
    same_origin_required: resolveCertificateOptionCopy(
      "certificate_issue_forbidden_message",
    ),
  };

  return fallbackByCode[code] || resolveCertificateOptionCopy(
    "certificate_issue_unavailable_message",
  );
}

function setCertificateIssueBusy(isBusy) {
  isCertificateIssueInProgress = isBusy;
  const isCertificateIssued = currentCertificateDocument?.certStatus === "issued";
  updatePageLoadingText(
    isBusy
      ? (isCertificateIssued ? certificateDownloadPendingMessage : certificateIssuePendingMessage)
      : lookupPendingMessage,
  );
  setCertificateDisplayControlsLocked(isBusy || isCertificateIssued);
  if (certificateGenerateAction) {
    certificateGenerateAction.disabled = isBusy;
  }
  [
    certificateOptionsBackAction,
    certificateChangeRequestAction,
  ].filter(Boolean).forEach((control) => {
    control.disabled = isBusy;
  });
  certificateOptionsView?.classList.toggle("is-lookup-busy", isBusy);
  certificateOptionsView?.setAttribute("aria-busy", String(isBusy));
  if (pageLoadingOverlay) {
    pageLoadingOverlay.hidden = !isBusy;
  }
}

function resolveCertificatePdfFilename(response) {
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/i);
  return match?.[1] || "certificate.pdf";
}

function downloadPdfBlob(pdfBlob, filename) {
  const objectUrl = window.URL.createObjectURL(pdfBlob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl);
  }, 1000);
}

async function issueCompletionCertificate() {
  if (isCertificateIssueInProgress || !currentCertificateDocument) {
    return;
  }

  setCertificateIssueBusy(true);
  try {
    const response = await fetch(certificateIssueApiPath, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/pdf, application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildCertificateIssuePayload()),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      setCertificateOptionsChangeRequestStatus(resolveCertificateIssueFailureMessage(payload), "error");
      return;
    }

    const pdfBlob = await response.blob();
    downloadPdfBlob(pdfBlob, resolveCertificatePdfFilename(response));
    currentCertificateDocument.certStatus = "issued";
    currentCertificateDocument.canRequestChanges = false;
    renderCertificateOptionsStatus(currentCertificateDocument);
  } catch {
    setCertificateOptionsChangeRequestStatus(
      resolveCertificateOptionCopy(
        "certificate_issue_unavailable_message",
      ),
      "error",
    );
  } finally {
    setCertificateIssueBusy(false);
  }
}

function resolveChangeRequestFailureMessage(payload) {
  const code = payload?.error?.code;
  const fallbackByCode = {
    change_request_not_allowed: resolveCertificateOptionCopy(
      "certificate_change_request_not_allowed_message",
    ),
    invalid_change_request: resolveCertificateOptionCopy(
      "certificate_change_request_invalid_message",
    ),
    same_origin_required: resolveCertificateOptionCopy(
      "certificate_change_request_forbidden_message",
    ),
  };

  return fallbackByCode[code] || resolveCertificateOptionCopy(
    "certificate_change_request_unavailable_message",
  );
}

async function submitCertificateChangeRequest() {
  updateCertificateChangeRequestSubmitState();
  if (certificateChangeRequestSubmitAction?.disabled) {
    return;
  }

  setChangeRequestBusy(true);
  try {
    const response = await fetch(certificateChangeRequestApiPath, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildCertificateChangeRequestPayload()),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMessage = resolveChangeRequestFailureMessage(payload);
      showCertificateChangeRequestError(errorMessage);
      setCertificateOptionsChangeRequestStatus(errorMessage, "error");
      return;
    }

    const message = resolveCertificateOptionCopy(
      "certificate_change_request_submitted_message",
    );
    showCertificateChangeRequestFeedback(message);
    if (currentCertificateDocument) {
      currentCertificateDocument.certStatus = "changeRequested";
      currentCertificateDocument.canRequestChanges = false;
    }
    setCertificateOptionsChangeRequestStatus(message, "success");
    setChangeRequestSubmitted(true);
  } catch {
    const errorMessage = resolveCertificateOptionCopy(
      "certificate_change_request_unavailable_message",
    );
    showCertificateChangeRequestError(errorMessage);
    setCertificateOptionsChangeRequestStatus(errorMessage, "error");
  } finally {
    setChangeRequestBusy(false);
  }
}

function showCertificateChangeRequest() {
  if (!certificateChangeRequestView || !currentCertificateDocument) {
    return;
  }

  renderCertificateChangeRequestSummary();
  certificateOptionsView.hidden = true;
  certificateChangeRequestView.hidden = false;
  clearCertificateChangeRequestFeedback();
  setChangeRequestSubmitted(currentCertificateDocument.certStatus === "changeRequested");
  updateCertificateChangeRequestSubmitState();
  certificateChangeRequestView.focus?.();
}

function showCertificateOptionsFromChangeRequest() {
  if (currentCertificateDocument) {
    renderCertificateOptionsStatus(currentCertificateDocument);
  }
  certificateChangeRequestView.hidden = true;
  certificateOptionsView.hidden = false;
  certificateOptionsView.focus?.();
}

function setDocumentLookupFieldsLocked(isLocked) {
  documentRequestForm.classList.toggle("is-certificate-options-active", isLocked);
  [
    eventNameTrigger,
    documentTypeTrigger,
    registrationNumber,
    email,
  ].filter(Boolean).forEach((control) => {
    control.disabled = isLocked;
  });

  previewAction.hidden = isLocked;
}

function showCertificateOptions(documentData) {
  currentCertificateDocument = documentData;
  clearCertificateOptionsChangeRequestStatus();
  resetCertificateIssuePreview();
  renderCertificateNameOptions(documentData);
  renderCertificateCompanyOption(documentData);
  renderCertificateOptionsStatus(documentData);
  if (documentData?.certStatus !== "issued") {
    showCertificateIssuePreview();
  }
  setDocumentLookupFieldsLocked(true);
  certificateChangeRequestView.hidden = true;
  certificateOptionsView.hidden = false;
  certificateOptionsView.focus?.();
}

function showDocumentLookupForm() {
  certificateOptionsView.hidden = true;
  certificateChangeRequestView.hidden = true;
  currentCertificateDocument = null;
  clearCertificateOptionsChangeRequestStatus();
  resetCertificateIssuePreview();
  setChangeRequestSubmitted(false);
  clearCertificateChangeRequestFeedback();
  setDocumentLookupFieldsLocked(false);
  updatePreviewActionState();
  previewAction.focus();
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

  const name = attendeeName?.value.trim() || emptyNameText;
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
  previewAction.disabled = isLookupInProgress || !isUserDataComplete();
}

function updatePageLoadingText(message) {
  const pageLoadingText = pageLoadingOverlay?.querySelector(".page-loading-text");
  updateTextContent(pageLoadingText, message);
}

function setLookupBusy(isBusy) {
  isLookupInProgress = isBusy;
  updatePageLoadingText(lookupPendingMessage);
  documentRequestForm.classList.toggle("is-lookup-busy", isBusy);
  homePage.classList.toggle("is-lookup-busy", isBusy);
  documentRequestForm.setAttribute("aria-busy", String(isBusy));
  if (pageLoadingOverlay) {
    pageLoadingOverlay.hidden = !isBusy;
  }

  documentRequestForm
    .querySelectorAll("input, button, select, textarea")
    .forEach((control) => {
      if (!("disabled" in control)) {
        return;
      }

      if (isBusy) {
        control.dataset.lookupWasDisabled = String(control.disabled);
        control.disabled = true;
        return;
      }

      control.disabled = control.dataset.lookupWasDisabled === "true";
      delete control.dataset.lookupWasDisabled;
    });

  updatePreviewActionState();
}

function buildDocumentLookupPayload() {
  const documentType = documentTypeInput.value.trim();
  const payload = {
    documentType,
    eventId: eventNameInput.dataset.eventId ?? "",
  };

  if (documentType === "completionCert") {
    payload.registrationNumber = registrationNumber.value.trim();
    payload.email = email.value.trim();
    return payload;
  }

  if (documentType === "taxReceipt") {
    payload.businessTaxId = businessTaxId.value.trim();
    payload.generatedAt = generatedAt.value.trim();
  }

  return payload;
}

function resolveLookupFailureMessage(payload) {
  const code = payload?.error?.code;
  const message = payload?.error?.message;
  if (code === "lookup_blocked") {
    if (typeof message === "string" && message.trim()) {
      return message;
    }

    return lookupBlockedMessage;
  }

  if (code === "lookup_unavailable") {
    return lookupUnavailableMessage;
  }

  if (code === "document_not_available_yet") {
    if (typeof message === "string" && message.trim()) {
      return message;
    }

    return lookupNotAvailableYetMessage;
  }

  return lookupNotFoundMessage;
}

function showLookupFeedback(message, tone = "success") {
  feedback.hidden = false;
  feedback.classList.add("is-active");
  feedback.classList.toggle("is-success", tone === "success");
  feedback.classList.toggle("is-error", tone === "error");
  feedback.textContent = message;
}

function clearLookupFeedback() {
  feedback.hidden = true;
  feedback.classList.remove("is-active", "is-success", "is-error");
  feedback.textContent = "";
}

function shouldShowCertificateOptions(documentData) {
  return ["notIssued", "changeRequested", "issued"].includes(documentData?.certStatus);
}

function readClientLookupBlockedUntil() {
  try {
    const value = window.localStorage.getItem(lookupBlockedStorageKey);
    if (!value) {
      return null;
    }

    if (value.trim().startsWith("{")) {
      const payload = JSON.parse(value);
      const timestamp = Number.parseInt(String(payload?.until ?? ""), 10);
      if (!Number.isFinite(timestamp)) {
        window.localStorage.removeItem(lookupBlockedStorageKey);
        return null;
      }

      if (timestamp <= Date.now()) {
        window.localStorage.removeItem(lookupBlockedStorageKey);
        return null;
      }

      return {
        message:
          typeof payload?.message === "string" && payload.message.trim()
            ? payload.message
            : lookupBlockedMessage,
        until: timestamp,
      };
    }

    const timestamp = Number.parseInt(value, 10);
    if (!Number.isFinite(timestamp)) {
      window.localStorage.removeItem(lookupBlockedStorageKey);
      return null;
    }

    if (timestamp <= Date.now()) {
      window.localStorage.removeItem(lookupBlockedStorageKey);
      return null;
    }

    return {
      message: lookupBlockedMessage,
      until: timestamp,
    };
  } catch {
    return null;
  }
}

function rememberClientLookupBlock(message = lookupBlockedMessage) {
  try {
    window.localStorage.setItem(lookupBlockedStorageKey, JSON.stringify({
      message,
      until: Date.now() + lookupBlockedClientCacheMs,
    }));
  } catch {
    return;
  }
}

function clearClientLookupBlock() {
  try {
    window.localStorage.removeItem(lookupBlockedStorageKey);
  } catch {
    return;
  }
}

async function submitDocumentLookup() {
  const clientLookupBlock = readClientLookupBlockedUntil();
  if (clientLookupBlock !== null) {
    showLookupFeedback(clientLookupBlock.message, "error");
    return;
  }

  updatePreviewActionState();
  if (previewAction.disabled) {
    return;
  }

  const documentLookupPayload = buildDocumentLookupPayload();
  setLookupBusy(true);
  let successfulDocument = null;

  try {
    const response = await fetch(documentLookupApiPath, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(documentLookupPayload),
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      if (payload?.error?.code === "lookup_blocked") {
        rememberClientLookupBlock(resolveLookupFailureMessage(payload));
      }
      showLookupFeedback(resolveLookupFailureMessage(payload), "error");
      return;
    }

    clearClientLookupBlock();
    successfulDocument = payload?.document ?? {};
  } catch {
    showLookupFeedback(lookupUnavailableMessage, "error");
  } finally {
    setLookupBusy(false);
  }

  if (successfulDocument === null) {
    return;
  }

  clearLookupFeedback();
  if (!shouldShowCertificateOptions(successfulDocument)) {
    showLookupFeedback(formatPreviewMessage(previewFeedbackTemplate, {
      eventName: eventNameInput.value,
      documentType: resolveDocumentTypeLabel(documentTypeInput.value),
      attendeeName: emptyNameText,
      email: email.value.trim() || emptyEmailText,
    }));
    return;
  }

  showCertificateOptions(successfulDocument);
}

function submitDocumentLookupFromCompletionCertInput(event) {
  if (event.key !== "Enter" || event.isComposing) {
    return;
  }

  event.preventDefault();
  updatePreviewActionState();
  if (previewAction.disabled) {
    return;
  }

  void submitDocumentLookup();
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
    if (isHomeEventsLoading) {
      startEventNameLoadingAnimation(homePageCopy.event_name_loading_option ?? "");
      updateTextContent(
        eventNameValue,
        eventNameLoadingAnimationBaseText || homePageCopy.event_name_empty_option,
      );
      renderEventNameLoadingAnimationFrame();
    } else {
      stopEventNameLoadingAnimation();
      updateTextContent(eventNameValue, homePageCopy.event_name_empty_option);
    }
  } else {
    stopEventNameLoadingAnimation();
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
  updateTextContent(certificateOptionsTitle, homePageCopy.certificate_options_title);
  updateTextContent(certificateOptionsSubtitle, homePageCopy.certificate_options_subtitle);
  updateTextContent(certificateNameOptionsLabel, homePageCopy.certificate_name_options_label);
  updateTextContent(certificateCompanyOptionLabel, homePageCopy.certificate_company_option_label);
  updateTextContent(certificatePreviewTitle, homePageCopy.certificate_preview_title);
  updateTextContent(certificatePreviewSubtitle, homePageCopy.certificate_preview_subtitle);
  updateTextContent(certificateOptionsBackAction, homePageCopy.certificate_options_back_action_label);
  updateTextContent(certificateChangeRequestAction, homePageCopy.certificate_change_request_action_label);
  updateTextContent(certificateGenerateAction, homePageCopy.certificate_generate_action_label);
  updateTextContent(certificateGenerateWarning, homePageCopy.certificate_generate_warning);
  updateTextContent(
    certificateChangeRequestProcessingFeedback,
    homePageCopy.certificate_change_request_processing_message,
  );
  updateTextContent(certificateChangeRequestTitle, homePageCopy.certificate_change_request_title);
  updateTextContent(certificateChangeRequestSubtitle, homePageCopy.certificate_change_request_subtitle);
  updateTextContent(certificateChangeRequestEventLabel, homePageCopy.certificate_change_request_event_label);
  updateTextContent(certificateChangeRequestRegistrationNumberLabel, homePageCopy.registration_number_label);
  updateTextContent(certificateChangeRequestEmailLabel, homePageCopy.email_label);
  updateTextContent(certificateChangeRequestNoteLabel, homePageCopy.certificate_change_request_note_label);
  updateTextContent(certificateChangeRequestNoteHint, homePageCopy.certificate_change_request_note_hint);
  updateTextContent(certificateChangeRequestBackAction, homePageCopy.certificate_change_request_back_action_label);
  updateTextContent(certificateChangeRequestSubmitAction, homePageCopy.certificate_change_request_submit_action_label);
  updateTextContent(copyrightNotice, homePageCopy.copyright_notice);

  if (typeof homePageCopy.registration_number_placeholder === "string") {
    registrationNumber.placeholder = homePageCopy.registration_number_placeholder;
  }

  if (attendeeName && typeof homePageCopy.attendee_name_placeholder === "string") {
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

  if (certificateChangeRequestNote && typeof homePageCopy.certificate_change_request_note_placeholder === "string") {
    certificateChangeRequestNote.placeholder = homePageCopy.certificate_change_request_note_placeholder;
  }

  if (currentCertificateDocument && !certificateChangeRequestView.hidden) {
    renderCertificateChangeRequestSummary();
  }

  if (currentCertificateDocument && !certificateOptionsView.hidden) {
    renderCertificateCompanyOption(currentCertificateDocument);
    renderCertificateOptionsStatus(currentCertificateDocument);
  }

  if (currentCertificateDocument && !certificatePreview.hidden) {
    renderCertificateIssuePreview();
    renderCertificateGenerateAction(currentCertificateDocument);
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

  if (typeof homePageCopy.lookup_not_found_message === "string") {
    lookupNotFoundMessage = homePageCopy.lookup_not_found_message;
    homePage.dataset.lookupNotFoundMessage = lookupNotFoundMessage;
  }

  if (typeof homePageCopy.lookup_not_available_yet_message === "string") {
    lookupNotAvailableYetMessage = homePageCopy.lookup_not_available_yet_message;
    homePage.dataset.lookupNotAvailableYetMessage = lookupNotAvailableYetMessage;
  }

  if (typeof homePageCopy.lookup_blocked_message === "string") {
    lookupBlockedMessage = homePageCopy.lookup_blocked_message;
    homePage.dataset.lookupBlockedMessage = lookupBlockedMessage;
  }

  if (typeof homePageCopy.lookup_unavailable_message === "string") {
    lookupUnavailableMessage = homePageCopy.lookup_unavailable_message;
    homePage.dataset.lookupUnavailableMessage = lookupUnavailableMessage;
  }

  if (typeof homePageCopy.lookup_pending_message === "string") {
    lookupPendingMessage = homePageCopy.lookup_pending_message;
    homePage.dataset.lookupPendingMessage = lookupPendingMessage;
    updatePageLoadingText(lookupPendingMessage);
  }

  if (typeof homePageCopy.certificate_issue_pending_message === "string") {
    certificateIssuePendingMessage = homePageCopy.certificate_issue_pending_message;
  }

  if (typeof homePageCopy.certificate_download_pending_message === "string") {
    certificateDownloadPendingMessage = homePageCopy.certificate_download_pending_message;
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

documentRequestForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  void submitDocumentLookup();
});

previewAction.addEventListener("click", () => {
  void submitDocumentLookup();
});

[registrationNumber, email].filter(Boolean).forEach((input) => {
  input.addEventListener("keydown", submitDocumentLookupFromCompletionCertInput);
});

certificateOptionsBackAction?.addEventListener("click", () => {
  showDocumentLookupForm();
});

certificateChangeRequestAction?.addEventListener("click", () => {
  showCertificateChangeRequest();
});

certificateGenerateAction?.addEventListener("click", () => {
  void issueCompletionCertificate();
});

certificateNameOptions?.addEventListener("change", () => {
  renderCertificateIssuePreview();
});

certificateCompanyVisible?.addEventListener("change", () => {
  renderCertificateIssuePreview();
});

certificateChangeRequestBackAction?.addEventListener("click", () => {
  showCertificateOptionsFromChangeRequest();
});

certificateChangeRequestNote?.addEventListener("input", () => {
  clearCertificateChangeRequestFeedback();
  updateCertificateChangeRequestSubmitState();
});

certificateChangeRequestForm?.addEventListener("submit", (event) => {
  event.preventDefault();
  void submitCertificateChangeRequest();
});

[registrationNumber, attendeeName, email, businessTaxId, generatedAt].filter(Boolean).forEach((input) => {
  input.addEventListener("input", updatePreviewActionState);
});
if (typeof installDateTimePicker === "function") {
  installDateTimePicker(generatedAt, { includeSeconds: true });
}
updatePreviewActionState();
loadHomeEvents();
