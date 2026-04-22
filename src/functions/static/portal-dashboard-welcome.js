const welcomePage = document.body;
const welcomeAccountDisplay = document.getElementById("welcome-account-display");

const portalAccountStorageKey =
  welcomePage.dataset.portalAccountStorageKey ?? "portalSignedInAccount";

function readSignedInAccount() {
  try {
    return window.sessionStorage.getItem(portalAccountStorageKey)?.trim() ?? "";
  } catch (error) {
    void error;
    return "";
  }
}

function syncSignedInAccount() {
  const displayValue = readSignedInAccount() || "管理者";
  welcomeAccountDisplay.textContent = displayValue;
}

syncSignedInAccount();
