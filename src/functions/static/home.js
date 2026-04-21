const previewAction = document.getElementById("preview-action");
const feedback = document.getElementById("form-feedback");
const attendeeName = document.getElementById("attendee-name");
const email = document.getElementById("email");
const eventNameInput = document.getElementById("event-name");
const eventNameSelect = document.getElementById("event-name-select");
const eventNameTrigger = document.getElementById("event-name-trigger");
const eventNameValue = document.getElementById("event-name-value");
const eventNameOptions = Array.from(document.querySelectorAll(".custom-select-option"));

function closeEventNameSelect({ blurTrigger = false } = {}) {
  eventNameSelect.classList.remove("is-open");
  eventNameTrigger.setAttribute("aria-expanded", "false");
  document.getElementById("event-name-options").hidden = true;
  if (blurTrigger) {
    eventNameTrigger.blur();
  }
}

function openEventNameSelect() {
  eventNameSelect.classList.add("is-open");
  eventNameTrigger.setAttribute("aria-expanded", "true");
  document.getElementById("event-name-options").hidden = false;
}

eventNameTrigger.addEventListener("click", () => {
  if (eventNameSelect.classList.contains("is-open")) {
    closeEventNameSelect({ blurTrigger: true });
    return;
  }

  openEventNameSelect();
});

eventNameTrigger.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    openEventNameSelect();
    eventNameOptions[0]?.focus();
  }

  if (event.key === "Escape") {
    closeEventNameSelect({ blurTrigger: true });
  }
});

eventNameOptions.forEach((option, index) => {
  option.addEventListener("click", () => {
    const nextValue = option.dataset.value ?? option.textContent?.trim() ?? "";

    eventNameInput.value = nextValue;
    eventNameValue.textContent = nextValue;

    eventNameOptions.forEach((item) => {
      const isSelected = item === option;
      item.classList.toggle("is-selected", isSelected);
      item.setAttribute("aria-selected", String(isSelected));
    });

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

document.addEventListener("click", (event) => {
  if (!eventNameSelect.contains(event.target)) {
    closeEventNameSelect();
  }
});

previewAction.addEventListener("click", () => {
  const name = attendeeName.value.trim() || "未填寫姓名";
  const emailValue = email.value.trim() || "未填寫 email";

  feedback.classList.add("is-active");
  feedback.textContent =
    `已確認目前首頁欄位配置。活動名：${eventNameInput.value}；報名人姓名：${name}；email：${emailValue}。目前尚未串接資料庫、驗證與證明生成流程。`;
});
