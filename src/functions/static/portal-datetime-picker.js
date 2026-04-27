(function () {
  const minDateTimeYear = 2018;
  const maxDateTimeYear = 2099;
  const taipeiUtcOffsetMinutes = 8 * 60;

  function padDateTimePart(value) {
    return String(value).padStart(2, "0");
  }

  function formatDateTimeInputValue(year, month, day, hour, minute) {
    return [
      year,
      " / ",
      padDateTimePart(month),
      " / ",
      padDateTimePart(day),
      " ",
      padDateTimePart(hour),
      ":",
      padDateTimePart(minute),
    ].join("");
  }

  function formatCurrentDateTimeInputValue() {
    const now = new Date(Date.now() + taipeiUtcOffsetMinutes * 60 * 1000);
    return formatDateTimeInputValue(
      now.getUTCFullYear(),
      now.getUTCMonth() + 1,
      now.getUTCDate(),
      now.getUTCHours(),
      now.getUTCMinutes()
    );
  }

  function getDaysInMonth(year, month) {
    return new Date(year, month, 0).getDate();
  }

  function isValidDateTimeParts(year, month, day, hour, minute) {
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
      minute <= 59
    );
  }

  function parseDisplayDateTimeParts(value) {
    const match = value
      .trim()
      .match(/^([0-9]{4}) \/ ([0-9]{2}) \/ ([0-9]{2}) ([0-9]{2}):([0-9]{2})$/);

    if (!match) {
      return null;
    }

    const yearValue = Number(match[1]);
    const monthValue = Number(match[2]);
    const dayValue = Number(match[3]);
    const hourValue = Number(match[4]);
    const minuteValue = Number(match[5]);

    if (!isValidDateTimeParts(yearValue, monthValue, dayValue, hourValue, minuteValue)) {
      return null;
    }

    return {
      year: yearValue,
      month: monthValue,
      day: dayValue,
      hour: hourValue,
      minute: minuteValue,
    };
  }

  function parseDisplayDateTimeValue(value) {
    const parts = parseDisplayDateTimeParts(value);
    if (!parts) {
      return "";
    }

    return [
      String(parts.year).padStart(4, "0"),
      "-",
      padDateTimePart(parts.month),
      "-",
      padDateTimePart(parts.day),
      "T",
      padDateTimePart(parts.hour),
      ":",
      padDateTimePart(parts.minute),
    ].join("");
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

  function formatDateTimeInputValueFromUtcIso(value) {
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

    if (!isValidDateTimeParts(taipeiYear, taipeiMonth, taipeiDay, taipeiHour, taipeiMinute)) {
      return "";
    }

    return formatDateTimeInputValue(
      taipeiYear,
      taipeiMonth,
      taipeiDay,
      taipeiHour,
      taipeiMinute
    );
  }

  function normalizeDateTimeInputValue(value) {
    return parseDisplayDateTimeValue(value)
      ? value
      : formatDateTimeInputValueFromUtcIso(value);
  }

  function formatUtcIsoDateTimeInputValue(value) {
    const parts = parseDisplayDateTimeParts(value);
    if (!parts) {
      return "";
    }

    const utcDate = new Date(
      Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, 0) -
        taipeiUtcOffsetMinutes * 60 * 1000
    );
    return formatUtcIsoDateTimeValue(utcDate);
  }

  function installDateTimePicker(textInput) {
    if (!(textInput instanceof HTMLInputElement)) {
      return;
    }

    const picker = document.createElement("div");
    const dateGroup = document.createElement("div");
    const timeGroup = document.createElement("div");
    const yearInput = document.createElement("input");
    const monthInput = document.createElement("input");
    const dayInput = document.createElement("input");
    const dateInput = document.createElement("input");
    const hourInput = document.createElement("input");
    const minuteInput = document.createElement("input");

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
    yearInput.inputMode = "numeric";
    monthInput.inputMode = "numeric";
    dayInput.inputMode = "numeric";
    hourInput.inputMode = "numeric";
    minuteInput.inputMode = "numeric";
    yearInput.maxLength = 4;
    monthInput.maxLength = 2;
    dayInput.maxLength = 2;
    hourInput.maxLength = 2;
    minuteInput.maxLength = 2;
    yearInput.className = "form-datetime-picker-date-part is-year";
    monthInput.className = "form-datetime-picker-date-part";
    dayInput.className = "form-datetime-picker-date-part";
    dateInput.className = "form-datetime-picker-date-native";
    hourInput.className = "form-datetime-picker-time-input";
    minuteInput.className = "form-datetime-picker-time-input";
    yearInput.setAttribute("aria-label", "年");
    monthInput.setAttribute("aria-label", "月");
    dayInput.setAttribute("aria-label", "日");
    dateInput.setAttribute("aria-label", "日期選擇器");
    hourInput.setAttribute("aria-label", "小時");
    minuteInput.setAttribute("aria-label", "分鐘");
    dateGroup.append(
      yearInput,
      document.createTextNode("/"),
      monthInput,
      document.createTextNode("/"),
      dayInput,
      dateInput
    );
    timeGroup.append(hourInput, document.createTextNode(":"), minuteInput);
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
      const normalizedDisplayValue = normalizeDateTimeInputValue(textInput.value);
      if (normalizedDisplayValue && textInput.value !== normalizedDisplayValue) {
        textInput.value = normalizedDisplayValue;
      }

      const value = parseDisplayDateTimeValue(normalizedDisplayValue || textInput.value) ||
        parseDisplayDateTimeValue(formatCurrentDateTimeInputValue());
      const [dateValue, timeValue] = value.split("T");
      const [yearValue, monthValue, dayValue] = dateValue.split("-");
      const [hourValue, minuteValue] = timeValue.split(":");
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      dateInput.value = dateValue;
      hourInput.value = hourValue;
      minuteInput.value = minuteValue;
    }

    function getRestoreDisplayValue() {
      return normalizeDateTimeInputValue(textInput.value)
        ? normalizeDateTimeInputValue(textInput.value)
        : formatCurrentDateTimeInputValue();
    }

    function isPickerValueComplete() {
      return (
        yearInput.value.length === 4 &&
        monthInput.value.length === 2 &&
        dayInput.value.length === 2 &&
        hourInput.value.length === 2 &&
        minuteInput.value.length === 2
      );
    }

    function isPickerValueValid() {
      return isValidDateTimeParts(
        Number(yearInput.value),
        Number(monthInput.value),
        Number(dayInput.value),
        Number(hourInput.value),
        Number(minuteInput.value)
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
      const dateValue = `${yearValue}-${monthValue}-${dayValue}`;
      yearInput.value = yearValue;
      monthInput.value = monthValue;
      dayInput.value = dayValue;
      hourInput.value = hourValue;
      minuteInput.value = minuteValue;
      dateInput.value = dateValue;
      textInput.value =
        `${yearValue} / ${monthValue} / ${dayValue} ${hourValue}:${minuteValue}`;
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

    pickerPartInputs.forEach((input) => {
      installSelectAllOnFocus(input);
      input.addEventListener("keydown", handlePickerPartNavigation);
    });
    yearInput.addEventListener("input", () => handleDateInput(yearInput, monthInput, 4));
    monthInput.addEventListener("input", () => handleDateInput(monthInput, dayInput, 2));
    dayInput.addEventListener("input", () => handleDateInput(dayInput, hourInput, 2));
    yearInput.addEventListener("blur", () => normalizeAndApplyDateInput(yearInput));
    monthInput.addEventListener("blur", () => normalizeAndApplyDateInput(monthInput));
    dayInput.addEventListener("blur", () => normalizeAndApplyDateInput(dayInput));
    dateInput.addEventListener("input", handleNativeDateInput);
    hourInput.addEventListener("input", () => handleTimeInput(hourInput, minuteInput));
    minuteInput.addEventListener("input", () => handleTimeInput(minuteInput));
    hourInput.addEventListener("blur", () => normalizeAndApplyTimeInput(hourInput));
    minuteInput.addEventListener("blur", () => normalizeAndApplyTimeInput(minuteInput));
  }

  window.iPlaygroundPortalDateTime = {
    formatDateTimeInputValueFromUtcIso,
    formatCurrentDateTimeInputValue,
    formatUtcIsoDateTimeInputValue,
    installDateTimePicker,
    normalizeDateTimeInputValue,
    parseDisplayDateTimeValue,
  };
})();
