(function () {
  const verifyPage = document.body;
  window.iPlaygroundLocaleSwitcher?.installLocaleSwitcher({
    cookieMaxAge: Number.parseInt(verifyPage.dataset.localeCookieMaxAge ?? "31536000", 10),
    cookieName: verifyPage.dataset.localeCookieName ?? "ipg_locale",
    currentLocale: verifyPage.dataset.currentLocale ?? "zh-TW",
    root: verifyPage,
  });

  const issuedAtElements = document.querySelectorAll(".local-datetime[datetime]");
  if (!issuedAtElements.length || typeof Intl === "undefined") {
    return;
  }

  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  let formatter;
  try {
    formatter = new Intl.DateTimeFormat(languages, {
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
})();
