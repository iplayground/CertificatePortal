const portalPage = document.body;
const loginForm = document.getElementById("portal-login-form");
const accountInput = document.getElementById("portal-account");
const passwordInput = document.getElementById("portal-password");
const togglePasswordButton = document.getElementById("toggle-password");
const submitButton = document.getElementById("login-submit");
const feedback = document.getElementById("form-feedback");

const emptyAccountMessage = portalPage.dataset.emptyAccountMessage ?? "請輸入管理者帳號。";
const invalidAccountMessage = portalPage.dataset.invalidAccountMessage ?? "請輸入有效的電子郵件地址。";
const emptyPasswordMessage = portalPage.dataset.emptyPasswordMessage ?? "請輸入密碼。";
const defaultFeedbackMessage =
  portalPage.dataset.defaultFeedbackMessage ?? "請輸入帳號與密碼後送出，先確認登入頁版型與欄位狀態。";
const readyFeedbackMessage =
  portalPage.dataset.readyFeedbackMessage ?? "前端欄位檢查已通過，實際驗證與授權流程尚未接入。";
const showPasswordLabel = portalPage.dataset.showPasswordLabel ?? "顯示密碼";
const hidePasswordLabel = portalPage.dataset.hidePasswordLabel ?? "隱藏密碼";

function setFeedbackState(state, message) {
  feedback.textContent = message;
  feedback.classList.toggle("is-error", state === "error");
  feedback.classList.toggle("is-success", state === "success");
}

function setFieldErrorState(field, hasError) {
  field.setAttribute("aria-invalid", String(hasError));
  field.closest(".field")?.classList.toggle("has-error", hasError);
}

function validateLoginForm() {
  const errors = [];

  if (!accountInput.value.trim()) {
    setFieldErrorState(accountInput, true);
    errors.push(emptyAccountMessage);
  } else if (!accountInput.checkValidity()) {
    setFieldErrorState(accountInput, true);
    errors.push(invalidAccountMessage);
  } else {
    setFieldErrorState(accountInput, false);
  }

  if (!passwordInput.value.trim()) {
    setFieldErrorState(passwordInput, true);
    errors.push(emptyPasswordMessage);
  } else {
    setFieldErrorState(passwordInput, false);
  }

  return errors;
}

function updateSubmitState() {
  const hasAccountValue = accountInput.value.trim().length > 0;
  const hasPasswordValue = passwordInput.value.trim().length > 0;
  submitButton.disabled = !(hasAccountValue && hasPasswordValue && accountInput.checkValidity());
}

function syncPasswordToggleLabel(isPasswordHidden) {
  const label = isPasswordHidden ? showPasswordLabel : hidePasswordLabel;
  togglePasswordButton.textContent = label === "顯示密碼" ? "顯示" : "隱藏";
  togglePasswordButton.setAttribute("aria-label", label);
}

togglePasswordButton.addEventListener("click", () => {
  const isPasswordHidden = passwordInput.type === "password";
  passwordInput.type = isPasswordHidden ? "text" : "password";
  syncPasswordToggleLabel(!isPasswordHidden);
});

[accountInput, passwordInput].forEach((field) => {
  field.addEventListener("input", () => {
    if (field.value.trim()) {
      setFieldErrorState(field, false);
    }

    if (field === accountInput && field.value.trim() && !field.checkValidity()) {
      setFieldErrorState(field, true);
    }

    if (
      accountInput.getAttribute("aria-invalid") !== "true" &&
      passwordInput.getAttribute("aria-invalid") !== "true"
    ) {
      setFeedbackState("idle", defaultFeedbackMessage);
    }

    updateSubmitState();
  });
});

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const errors = validateLoginForm();
  if (errors.length > 0) {
    setFeedbackState("error", errors.join(" "));

    if (accountInput.getAttribute("aria-invalid") === "true") {
      accountInput.focus();
      return;
    }

    passwordInput.focus();
    return;
  }

  setFeedbackState("success", readyFeedbackMessage);
});

syncPasswordToggleLabel(true);
updateSubmitState();
