const welcomeAccountDisplay = document.getElementById("welcome-account-display");

function ensureWelcomeAccountDisplay() {
  if (!welcomeAccountDisplay) {
    return;
  }

  if (!welcomeAccountDisplay.textContent?.trim()) {
    welcomeAccountDisplay.textContent = "管理者";
  }
}

ensureWelcomeAccountDisplay();
