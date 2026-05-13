(function () {
  function setLocalePreference({ locale, cookieMaxAge, cookieName }) {
    const encodedLocale = encodeURIComponent(locale);
    document.cookie = `${cookieName}=${encodedLocale}; Max-Age=${cookieMaxAge}; Path=/; SameSite=Lax`;
  }

  function installLocaleSwitcher({
    cookieMaxAge = 31536000,
    cookieName = "ipg_locale",
    currentLocale = "zh-TW",
    onSelect,
    root = document.body,
  } = {}) {
    const localeSwitcher = document.getElementById("locale-switcher");
    const localeTrigger = document.getElementById("locale-trigger");
    const localeMenu = document.getElementById("locale-options");
    const localeOptions = Array.from(document.querySelectorAll(".locale-menu-option"));

    if (!localeSwitcher || !localeTrigger || !localeMenu || !localeOptions.length) {
      return null;
    }

    function close({ blurTrigger = false } = {}) {
      root.classList.remove("is-locale-menu-open");
      localeSwitcher.classList.remove("is-open");
      localeTrigger.setAttribute("aria-expanded", "false");
      localeMenu.hidden = true;

      if (blurTrigger) {
        localeTrigger.blur();
      }
    }

    function open() {
      root.classList.add("is-locale-menu-open");
      localeSwitcher.classList.add("is-open");
      localeTrigger.setAttribute("aria-expanded", "true");
      localeMenu.hidden = false;
    }

    function select(nextLocale) {
      if (!nextLocale || nextLocale === currentLocale) {
        close({ blurTrigger: true });
        return;
      }

      if (typeof onSelect === "function") {
        onSelect(nextLocale, {
          close,
          setLocalePreference: () =>
            setLocalePreference({
              locale: nextLocale,
              cookieMaxAge,
              cookieName,
            }),
        });
        currentLocale = nextLocale;
        close({ blurTrigger: true });
        return;
      }

      setLocalePreference({
        locale: nextLocale,
        cookieMaxAge,
        cookieName,
      });
      currentLocale = nextLocale;
      window.location.reload();
    }

    localeTrigger.addEventListener("click", () => {
      if (localeSwitcher.classList.contains("is-open")) {
        close({ blurTrigger: true });
        return;
      }

      open();
    });

    localeTrigger.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();

        const currentOption =
          localeOptions.find((button) => button.classList.contains("is-current")) ??
          localeOptions[0];
        currentOption?.focus();
        return;
      }

      if (event.key === "Escape") {
        event.preventDefault();
        close({ blurTrigger: true });
      }
    });

    localeOptions.forEach((button, index) => {
      button.addEventListener("click", () => {
        select(button.dataset.locale);
      });

      button.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          close({ blurTrigger: true });
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
          select(button.dataset.locale);
          return;
        }

        if (event.key === "Tab") {
          close();
        }
      });
    });

    localeMenu.addEventListener("pointerdown", (event) => {
      if (!(event.target instanceof Element)) {
        return;
      }

      const option = event.target.closest(".locale-menu-option");
      if (!(option instanceof HTMLButtonElement)) {
        return;
      }

      event.preventDefault();
      select(option.dataset.locale);
    });

    document.addEventListener("click", (event) => {
      if (localeSwitcher.classList.contains("is-open") && !localeSwitcher.contains(event.target)) {
        close();
      }
    });

    return { close, open };
  }

  window.iPlaygroundLocaleSwitcher = {
    installLocaleSwitcher,
    setLocalePreference,
  };
})();
