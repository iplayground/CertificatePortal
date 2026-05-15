(function () {
  const minDateTimeYear = 2018;
  const maxDateTimeYear = 2099;
  const taipeiUtcOffsetMinutes = 8 * 60;

  function padDateTimePart(value) {
    return String(value).padStart(2, "0");
  }

  function formatDateTimeInputValue(year, month, day, hour, minute, second = null) {
    const parts = [
      year,
      " / ",
      padDateTimePart(month),
      " / ",
      padDateTimePart(day),
      " ",
      padDateTimePart(hour),
      ":",
      padDateTimePart(minute),
    ];

    if (second !== null) {
      parts.push(":", padDateTimePart(second));
    }

    return parts.join("");
  }

  function formatDateInputValue(year, month, day) {
    return [
      year,
      " / ",
      padDateTimePart(month),
      " / ",
      padDateTimePart(day),
    ].join("");
  }

  function formatCurrentDateTimeInputValue(options = {}) {
    const now = new Date(Date.now() + taipeiUtcOffsetMinutes * 60 * 1000);
    return formatDateTimeInputValue(
      now.getUTCFullYear(),
      now.getUTCMonth() + 1,
      now.getUTCDate(),
      now.getUTCHours(),
      now.getUTCMinutes(),
      options.includeSeconds ? now.getUTCSeconds() : null
    );
  }

  function getDaysInMonth(year, month) {
    return new Date(year, month, 0).getDate();
  }

  function isValidDateTimeParts(year, month, day, hour, minute, second = 0) {
    return (
      year >= minDateTimeYear &&
      year <= maxDateTimeYear &&
      month >= 1 &&
      month <= 12 &&
      day >= 1 &&
      day <= getDaysInMonth(year, month) &&
      hour >= 0 &&
      hour <= 23 &&
      minute >= 0 &&
      minute <= 59 &&
      second >= 0 &&
      second <= 59
    );
  }

  function parseDisplayDateTimeParts(value, options = {}) {
    const match = value
      .trim()
      .match(/^([0-9]{4}) \/ ([0-9]{2}) \/ ([0-9]{2}) ([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?$/);

    if (!match) {
      return null;
    }

    if (options.includeSeconds && typeof match[6] !== "string") {
      return null;
    }

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);
    const hourValue = Number(match[4]);
    const minuteValue = Number(match[5]);
    const secondValue = typeof match[6] === "string" ? Number(match[6]) : 0;

    if (!isValidDateTimeParts(yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue)) {
      return null;
    }

    return {
      year: yearValue,
      month: monthValue,
      day: dayValue,
      hour: hourValue,
      minute: minuteValue,
      second: secondValue,
      hasSecond: typeof match[6] === "string",
    };
  }

  function parseDisplayDateParts(value) {
    const match = value
      .trim()
      .match(/^([0-9]{4}) \/ ([0-9]{2}) \/ ([0-9]{2})$/);

    if (!match) {
      return null;
    }

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);

    if (
      yearValue < minDateTimeYear ||
      yearValue > maxDateTimeYear ||
      monthValue < 1 ||
      monthValue > 12 ||
      dayValue < 1 ||
      dayValue > getDaysInMonth(yearValue, monthValue)
    ) {
      return null;
    }

    return {
      year: yearValue,
      month: monthValue,
      day: dayValue,
    };
  }

  function parseDisplayDateTimeValue(value, options = {}) {
    const parts = parseDisplayDateTimeParts(value, options);
    if (!parts) {
      return "";
    }

    const output = [
      String(parts.year).padStart(4, "0"),
      "-",
      padDateTimePart(parts.month),
      "-",
      padDateTimePart(parts.day),
      "T",
      padDateTimePart(parts.hour),
      ":",
      padDateTimePart(parts.minute),
    ];

    if (options.includeSeconds || parts.hasSecond) {
      output.push(":", padDateTimePart(parts.second));
    }

    return output.join("");
  }

  function parseUtcIsoDateTimeValue(value) {
    const match = value
      .trim()
      .match(/^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$/);

    if (!match) {
      return null;
    }

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);
    const hourValue = Number(match[4]);
    const minuteValue = Number(match[5]);
    const secondValue = Number(match[6]);

    if (
      monthValue < 1 ||
      monthValue > 12 ||
      dayValue < 1 ||
      dayValue > getDaysInMonth(yearValue, monthValue) ||
      hourValue < 0 ||
      hourValue > 23 ||
      minuteValue < 0 ||
      minuteValue > 59 ||
      secondValue < 0 ||
      secondValue > 59
    ) {
      return null;
    }

    return {
      year: yearValue,
      month: monthValue,
      day: dayValue,
      hour: hourValue,
      minute: minuteValue,
      second: secondValue,
    };
  }

  function parseIsoDateValue(value) {
    const match = value.trim().match(/^([0-9]{4})-([0-9]{2})-([0-9]{2})$/);
    if (!match) {
      return null;
    }

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);

    if (
      yearValue < minDateTimeYear ||
      yearValue > maxDateTimeYear ||
      monthValue < 1 ||
      monthValue > 12 ||
      dayValue < 1 ||
      dayValue > getDaysInMonth(yearValue, monthValue)
    ) {
      return null;
    }

    return {
      year: yearValue,
      month: monthValue,
      day: dayValue,
    };
  }

  function formatUtcIsoDateTimeValue(date) {
    return [
      date.getUTCFullYear(),
      "-",
      padDateTimePart(date.getUTCMonth() + 1),
      "-",
      padDateTimePart(date.getUTCDate()),
      "T",
      padDateTimePart(date.getUTCHours()),
      ":",
      padDateTimePart(date.getUTCMinutes()),
      ":",
      padDateTimePart(date.getUTCSeconds()),
      "Z",
    ].join("");
  }

  function formatDateTimeInputValueFromUtcIso(value, options = {}) {
    const parts = parseUtcIsoDateTimeValue(value);
    if (!parts) {
      return "";
    }

    const taipeiDate = new Date(
      Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) +
        taipeiUtcOffsetMinutes * 60 * 1000
    );
    const taipeiYear = taipeiDate.getUTCFullYear();
    const taipeiMonth = taipeiDate.getUTCMonth() + 1;
    const taipeiDay = taipeiDate.getUTCDate();
    const taipeiHour = taipeiDate.getUTCHours();
    const taipeiMinute = taipeiDate.getUTCMinutes();
    const taipeiSecond = taipeiDate.getUTCSeconds();

    if (!isValidDateTimeParts(taipeiYear, taipeiMonth, taipeiDay, taipeiHour, taipeiMinute, taipeiSecond)) {
      return "";
    }

    return formatDateTimeInputValue(
      taipeiYear,
      taipeiMonth,
      taipeiDay,
      taipeiHour,
      taipeiMinute,
      options.includeSeconds ? taipeiSecond : null
    );
  }

  function normalizeDateTimeInputValue(value, options = {}) {
    return parseDisplayDateTimeValue(value, options)
      ? value
      : formatDateTimeInputValueFromUtcIso(value, options);
  }

  function normalizeDateInputValue(value) {
    const displayParts = parseDisplayDateParts(value);
    if (displayParts) {
      return formatDateInputValue(displayParts.year, displayParts.month, displayParts.day);
    }

    const isoParts = parseIsoDateValue(value);
    if (!isoParts) {
      return "";
    }

    return formatDateInputValue(isoParts.year, isoParts.month, isoParts.day);
  }

  function formatIsoDateInputValue(value) {
    const parts = parseDisplayDateParts(value);
    if (!parts) {
      return "";
    }

    return [
      String(parts.year).padStart(4, "0"),
      "-",
      padDateTimePart(parts.month),
      "-",
      padDateTimePart(parts.day),
    ].join("");
  }

  function formatUtcIsoDateTimeInputValue(value) {
    const parts = parseDisplayDateTimeParts(value);
    if (!parts) {
      return "";
    }

    const utcDate = new Date(
      Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) -
        taipeiUtcOffsetMinutes * 60 * 1000
    );
    return formatUtcIsoDateTimeValue(utcDate);
  }

  function installDateTimePicker(textInput, options = {}) {
    if (!(textInput instanceof HTMLInputElement)) {
      return;
    }
    const includeSeconds = options.includeSeconds === true;

    const picker = document.createElement("div");
    const dateGroup = document.createElement("div");
    const timeGroup = document.createElement("div");
    const yearInput = document.createElement("input");
    const monthInput = document.createElement("input");
    const dayInput = document.createElement("input");
    const dateInput = document.createElement("input");
    const hourInput = document.createElement("input");
    const minuteInput = document.createElement("input");
    const secondInput = document.createElement("input");

    textInput.hidden = true;
    picker.className = "form-datetime-picker form-datetime-picker-inline";
    dateGroup.className = "form-datetime-picker-date";
    timeGroup.className = "form-datetime-picker-time";
    yearInput.type = "text";
    monthInput.type = "text";
    dayInput.type = "text";
    dateInput.type = "date";
    hourInput.type = "text";
    minuteInput.type = "text";
    secondInput.type = "text";
    yearInput.inputMode = "numeric";
    monthInput.inputMode = "numeric";
    dayInput.inputMode = "numeric";
    hourInput.inputMode = "numeric";
    minuteInput.inputMode = "numeric";
    secondInput.inputMode = "numeric";
    yearInput.maxLength = 4;
    monthInput.maxLength = 2;
    dayInput.maxLength = 2;
    hourInput.maxLength = 2;
    minuteInput.maxLength = 2;
    secondInput.maxLength = 2;
    yearInput.className = "form-datetime-picker-date-part is-year";
    monthInput.className = "form-datetime-picker-date-part";
    dayInput.className = "form-datetime-picker-date-part";
    dateInput.className = "form-datetime-picker-date-native";
    hourInput.className = "form-datetime-picker-time-input";
    minuteInput.className = "form-datetime-picker-time-input";
    secondInput.className = "form-datetime-picker-time-input";
    yearInput.setAttribute("aria-label", "年");
    monthInput.setAttribute("aria-label", "月");
    dayInput.setAttribute("aria-label", "日");
    dateInput.setAttribute("aria-label", "日期選擇器");
    hourInput.setAttribute("aria-label", "小時");
    minuteInput.setAttribute("aria-label", "分鐘");
    secondInput.setAttribute("aria-label", "秒");
    dateGroup.append(
      yearInput,
      document.createTextNode("/"),
      monthInput,
      document.createTextNode("/"),
      dayInput,
      dateInput
    );
    timeGroup.append(hourInput, document.createTextNode(":"), minuteInput);
    if (includeSeconds) {
      timeGroup.append(document.createTextNode(":"), secondInput);
    }
    picker.append(dateGroup, timeGroup);
    textInput.insertAdjacentElement("afterend", picker);
    let isApplyingPickerValue = false;
    let restoreDisplayValue = "";

    function normalizeDatePart(value) {
      const digits = value.replace(/\D/g, "").slice(0, 2);
      if (digits === "") {
        return "";
      }

      return padDateTimePart(digits);
    }

    function normalizeYearValue(value) {
      const digits = value.replace(/\D/g, "").slice(0, 4);
      if (digits.length !== 4) {
        return "";
      }

      return digits;
    }

    function normalizeTimeValue(value) {
      const digits = value.replace(/\D/g, "").slice(0, 2);
      if (digits === "") {
        return "";
      }

      return padDateTimePart(digits);
    }

    function syncPickerControls() {
      const normalizedDisplayValue = normalizeDateTimeInputValue(textInput.value, { includeSeconds });
      if (normalizedDisplayValue && textInput.value !== normalizedDisplayValue) {
        textInput.value = normalizedDisplayValue;
      }

      const value = parseDisplayDateTimeValue(normalizedDisplayValue || textInput.value, { includeSeconds }) ||
        parseDisplayDateTimeValue(formatCurrentDateTimeInputValue({ includeSeconds }), { includeSeconds });
      const [dateValue, timeValue] = value.split("T");
      const [yearValue, monthValue, dayValue] = dateValue.split("-");
      const [hourValue, minuteValue, secondValue = "00"] = timeValue.split(":");
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      dateInput.value = dateValue;
      hourInput.value = hourValue;
      minuteInput.value = minuteValue;
      secondInput.value = secondValue;
    }

    function getRestoreDisplayValue() {
      return normalizeDateTimeInputValue(textInput.value, { includeSeconds })
        ? normalizeDateTimeInputValue(textInput.value, { includeSeconds })
        : formatCurrentDateTimeInputValue({ includeSeconds });
    }

    function isPickerValueComplete() {
      return (
        yearInput.value.length === 4 &&
        monthInput.value.length === 2 &&
        dayInput.value.length === 2 &&
        hourInput.value.length === 2 &&
        minuteInput.value.length === 2 &&
        (!includeSeconds || secondInput.value.length === 2)
      );
    }

    function isPickerValueValid() {
      return isValidDateTimeParts(
        Number(yearInput.value),
        Number(monthInput.value),
        Number(dayInput.value),
        Number(hourInput.value),
        Number(minuteInput.value),
        includeSeconds ? Number(secondInput.value) : 0
      );
    }

    function restorePreviousPickerValue() {
      textInput.value = restoreDisplayValue || getRestoreDisplayValue();
      isApplyingPickerValue = true;
      textInput.dispatchEvent(new Event("input", { bubbles: true }));
      isApplyingPickerValue = false;
      syncPickerControls();
    }

    function applyPickerValue() {
      if (!isPickerValueComplete() || !isPickerValueValid()) {
        return false;
      }

      const yearValue = normalizeYearValue(yearInput.value);
      const monthValue = normalizeDatePart(monthInput.value);
      const dayValue = normalizeDatePart(dayInput.value);
      const hourValue = normalizeTimeValue(hourInput.value);
      const minuteValue = normalizeTimeValue(minuteInput.value);
      const secondValue = normalizeTimeValue(secondInput.value);
      const dateValue = `${yearValue}-${monthValue}-${dayValue}`;
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      hourInput.value = hourValue;
      minuteInput.value = minuteValue;
      secondInput.value = secondValue;
      dateInput.value = dateValue;
      textInput.value = includeSeconds
        ? `${yearValue} / ${monthValue} / ${dayValue} ${hourValue}:${minuteValue}:${secondValue}`
        : `${yearValue} / ${monthValue} / ${dayValue} ${hourValue}:${minuteValue}`;
      isApplyingPickerValue = true;
      textInput.dispatchEvent(new Event("input", { bubbles: true }));
      isApplyingPickerValue = false;
      restoreDisplayValue = textInput.value;
      return true;
    }

    function handleDateInput(input, nextInput, maxLength) {
      input.value = input.value.replace(/\D/g, "").slice(0, maxLength);
      if (input.value.length === maxLength && nextInput instanceof HTMLInputElement) {
        nextInput.focus();
        nextInput.select();
      }
      applyPickerValue();
    }

    function normalizeAndApplyDateInput(input) {
      if (input === yearInput) {
        input.value = normalizeYearValue(input.value);
      } else {
        input.value = normalizeDatePart(input.value);
      }
      if (!applyPickerValue()) {
        restorePreviousPickerValue();
      }
    }

    function handleNativeDateInput() {
      if (!dateInput.value) {
        return;
      }

      const [yearValue, monthValue, dayValue] = dateInput.value.split("-");
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      applyPickerValue();
    }

    function handleTimeInput(input, nextInput = null) {
      input.value = input.value.replace(/\D/g, "").slice(0, 2);
      if (input.value.length === 2 && nextInput instanceof HTMLInputElement) {
        nextInput.focus();
        nextInput.select();
      }
      applyPickerValue();
    }

    function normalizeAndApplyTimeInput(input) {
      input.value = normalizeTimeValue(input.value);
      if (!applyPickerValue()) {
        restorePreviousPickerValue();
      }
    }

    function selectDateTimeInputValue(event) {
      if (event.currentTarget instanceof HTMLInputElement) {
        restoreDisplayValue = getRestoreDisplayValue();
        event.currentTarget.select();
      }
    }

    function installSelectAllOnFocus(input) {
      input.addEventListener("focus", selectDateTimeInputValue);
      input.addEventListener("click", selectDateTimeInputValue);
    }

    function syncInlinePicker() {
      if (isApplyingPickerValue) {
        return;
      }
      syncPickerControls();
    }

    syncInlinePicker();
    textInput.addEventListener("input", syncInlinePicker);
    const pickerPartInputs = [yearInput, monthInput, dayInput, hourInput, minuteInput];
    if (includeSeconds) {
      pickerPartInputs.push(secondInput);
    }
    const pickerControlInputs = [...pickerPartInputs, dateInput];

    function syncPickerDisabledState() {
      const isDisabled = textInput.disabled;
      picker.classList.toggle("is-disabled", isDisabled);
      pickerControlInputs.forEach((input) => {
        input.disabled = isDisabled;
      });
    }

    syncPickerDisabledState();
    new MutationObserver(syncPickerDisabledState).observe(textInput, {
      attributeFilter: ["disabled"],
      attributes: true,
    });

    function handlePickerPartNavigation(event) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
        return;
      }

      const currentIndex = pickerPartInputs.indexOf(event.currentTarget);
      if (currentIndex < 0) {
        return;
      }

      event.preventDefault();
      const direction = event.key === "ArrowLeft" ? -1 : 1;
      const nextInput = pickerPartInputs[currentIndex + direction];
      if (nextInput instanceof HTMLInputElement) {
        nextInput.focus();
        nextInput.select();
      }
    }

    function handlePickerReturn(event) {
      const isFinalTimeInput = includeSeconds
        ? event.currentTarget === secondInput
        : event.currentTarget === minuteInput;
      if (event.key !== "Enter" || event.isComposing || !isFinalTimeInput) {
        return;
      }

      event.preventDefault();
      normalizeAndApplyTimeInput(event.currentTarget);
      event.currentTarget.blur();
      textInput.dispatchEvent(new CustomEvent("datetime-picker-return", { bubbles: true }));
    }

    pickerPartInputs.forEach((input) => {
      installSelectAllOnFocus(input);
      input.addEventListener("keydown", handlePickerPartNavigation);
      input.addEventListener("keydown", handlePickerReturn);
    });
    yearInput.addEventListener("input", () => handleDateInput(yearInput, monthInput, 4));
    monthInput.addEventListener("input", () => handleDateInput(monthInput, dayInput, 2));
    dayInput.addEventListener("input", () => handleDateInput(dayInput, hourInput, 2));
    yearInput.addEventListener("blur", () => normalizeAndApplyDateInput(yearInput));
    monthInput.addEventListener("blur", () => normalizeAndApplyDateInput(monthInput));
    dayInput.addEventListener("blur", () => normalizeAndApplyDateInput(dayInput));
    dateInput.addEventListener("input", handleNativeDateInput);
    hourInput.addEventListener("input", () => handleTimeInput(hourInput, minuteInput));
    minuteInput.addEventListener("input", () => handleTimeInput(minuteInput, includeSeconds ? secondInput : null));
    secondInput.addEventListener("input", () => handleTimeInput(secondInput));
    hourInput.addEventListener("blur", () => normalizeAndApplyTimeInput(hourInput));
    minuteInput.addEventListener("blur", () => normalizeAndApplyTimeInput(minuteInput));
    secondInput.addEventListener("blur", () => normalizeAndApplyTimeInput(secondInput));
  }

  function installDatePicker(textInput) {
    if (!(textInput instanceof HTMLInputElement)) {
      return;
    }

    const picker = document.createElement("div");
    const dateGroup = document.createElement("div");
    const yearInput = document.createElement("input");
    const monthInput = document.createElement("input");
    const dayInput = document.createElement("input");
    const dateInput = document.createElement("input");

    textInput.hidden = true;
    picker.className = "form-datetime-picker form-date-picker-inline";
    dateGroup.className = "form-datetime-picker-date";
    yearInput.type = "text";
    monthInput.type = "text";
    dayInput.type = "text";
    dateInput.type = "date";
    yearInput.inputMode = "numeric";
    monthInput.inputMode = "numeric";
    dayInput.inputMode = "numeric";
    yearInput.maxLength = 4;
    monthInput.maxLength = 2;
    dayInput.maxLength = 2;
    yearInput.className = "form-datetime-picker-date-part is-year";
    monthInput.className = "form-datetime-picker-date-part";
    dayInput.className = "form-datetime-picker-date-part";
    dateInput.className = "form-datetime-picker-date-native";
    yearInput.setAttribute("aria-label", "年");
    monthInput.setAttribute("aria-label", "月");
    dayInput.setAttribute("aria-label", "日");
    dateInput.setAttribute("aria-label", "日期選擇器");
    dateGroup.append(
      yearInput,
      document.createTextNode("/"),
      monthInput,
      document.createTextNode("/"),
      dayInput,
      dateInput
    );
    picker.append(dateGroup);
    textInput.insertAdjacentElement("afterend", picker);

    let isApplyingPickerValue = false;
    let restoreDisplayValue = "";

    function normalizeDatePart(value) {
      const digits = value.replace(/\D/g, "").slice(0, 2);
      return digits ? padDateTimePart(digits) : "";
    }

    function normalizeYearValue(value) {
      const digits = value.replace(/\D/g, "").slice(0, 4);
      return digits.length === 4 ? digits : "";
    }

    function syncPickerControls() {
      const normalizedDisplayValue = normalizeDateInputValue(textInput.value);
      if (normalizedDisplayValue && textInput.value !== normalizedDisplayValue) {
        textInput.value = normalizedDisplayValue;
      }

      const isoValue = formatIsoDateInputValue(normalizedDisplayValue || textInput.value);
      if (!isoValue) {
        yearInput.value = "";
        monthInput.value = "";
        dayInput.value = "";
        dateInput.value = "";
        return;
      }

      const [yearValue, monthValue, dayValue] = isoValue.split("-");
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      dateInput.value = isoValue;
    }

    function getRestoreDisplayValue() {
      return normalizeDateInputValue(textInput.value) || normalizeDateInputValue(dateInput.value);
    }

    function isPickerValueComplete() {
      return (
        yearInput.value.length === 4 &&
        monthInput.value.length === 2 &&
        dayInput.value.length === 2
      );
    }

    function isPickerValueValid() {
      return Boolean(
        parseIsoDateValue(`${yearInput.value}-${monthInput.value}-${dayInput.value}`)
      );
    }

    function restorePreviousPickerValue() {
      textInput.value = restoreDisplayValue || getRestoreDisplayValue();
      isApplyingPickerValue = true;
      textInput.dispatchEvent(new Event("input", { bubbles: true }));
      isApplyingPickerValue = false;
      syncPickerControls();
    }

    function applyPickerValue() {
      if (!isPickerValueComplete() || !isPickerValueValid()) {
        return false;
      }

      const yearValue = normalizeYearValue(yearInput.value);
      const monthValue = normalizeDatePart(monthInput.value);
      const dayValue = normalizeDatePart(dayInput.value);
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      dateInput.value = `${yearValue}-${monthValue}-${dayValue}`;
      textInput.value = `${yearValue} / ${monthValue} / ${dayValue}`;
      isApplyingPickerValue = true;
      textInput.dispatchEvent(new Event("input", { bubbles: true }));
      isApplyingPickerValue = false;
      restoreDisplayValue = textInput.value;
      return true;
    }

    function handleDateInput(input, nextInput, maxLength) {
      input.value = input.value.replace(/\D/g, "").slice(0, maxLength);
      if (input.value.length === maxLength && nextInput instanceof HTMLInputElement) {
        nextInput.focus();
        nextInput.select();
      }
      applyPickerValue();
    }

    function normalizeAndApplyDateInput(input) {
      input.value = input === yearInput
        ? normalizeYearValue(input.value)
        : normalizeDatePart(input.value);
      if (!applyPickerValue()) {
        restorePreviousPickerValue();
      }
    }

    function handleNativeDateInput() {
      if (!dateInput.value) {
        return;
      }

      const [yearValue, monthValue, dayValue] = dateInput.value.split("-");
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      applyPickerValue();
    }

    function selectDateInputValue(event) {
      if (event.currentTarget instanceof HTMLInputElement) {
        restoreDisplayValue = getRestoreDisplayValue();
        event.currentTarget.select();
      }
    }

    function handlePickerPartNavigation(event) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") {
        return;
      }

      const pickerPartInputs = [yearInput, monthInput, dayInput];
      const currentIndex = pickerPartInputs.indexOf(event.currentTarget);
      if (currentIndex < 0) {
        return;
      }

      event.preventDefault();
      const direction = event.key === "ArrowLeft" ? -1 : 1;
      const nextInput = pickerPartInputs[currentIndex + direction];
      if (nextInput instanceof HTMLInputElement) {
        nextInput.focus();
        nextInput.select();
      }
    }

    function syncInlinePicker() {
      if (!isApplyingPickerValue) {
        syncPickerControls();
      }
    }

    syncInlinePicker();
    textInput.addEventListener("input", syncInlinePicker);
    [yearInput, monthInput, dayInput].forEach((input) => {
      input.addEventListener("focus", selectDateInputValue);
      input.addEventListener("click", selectDateInputValue);
      input.addEventListener("keydown", handlePickerPartNavigation);
    });
    yearInput.addEventListener("input", () => handleDateInput(yearInput, monthInput, 4));
    monthInput.addEventListener("input", () => handleDateInput(monthInput, dayInput, 2));
    dayInput.addEventListener("input", () => handleDateInput(dayInput, null, 2));
    yearInput.addEventListener("blur", () => normalizeAndApplyDateInput(yearInput));
    monthInput.addEventListener("blur", () => normalizeAndApplyDateInput(monthInput));
    dayInput.addEventListener("blur", () => normalizeAndApplyDateInput(dayInput));
    dateInput.addEventListener("input", handleNativeDateInput);
  }

  window.iPlaygroundPortalDateTime = {
    formatIsoDateInputValue,
    formatDateTimeInputValueFromUtcIso,
    formatCurrentDateTimeInputValue,
    formatUtcIsoDateTimeInputValue,
    installDatePicker,
    installDateTimePicker,
    normalizeDateInputValue,
    normalizeDateTimeInputValue,
    parseDisplayDateParts,
    parseDisplayDateTimeValue,
  };
})();
