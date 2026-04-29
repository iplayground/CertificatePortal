(function installPortalEventCache() {
  const adminEventsApiPath = "/api/v1/admin/events";
  const cacheKey = "ipg:portal:events:v1";
  let pendingEventsRequest = null;

  function normalizeEvent(eventData) {
    return eventData && typeof eventData === "object" ? eventData : {};
  }

  function readCachedEvents() {
    try {
      const cachedPayload = window.sessionStorage.getItem(cacheKey);
      if (!cachedPayload) {
        return null;
      }

      const parsedPayload = JSON.parse(cachedPayload);
      return Array.isArray(parsedPayload.events)
        ? parsedPayload.events.map((eventData) => normalizeEvent(eventData))
        : null;
    } catch (error) {
      void error;
      return null;
    }
  }

  function notifyEventCacheUpdated(events) {
    window.dispatchEvent(
      new CustomEvent("ipg:portal-events:updated", {
        detail: { events },
      })
    );
  }

  function writeCachedEvents(events) {
    const normalizedEvents = Array.isArray(events)
      ? events.map((eventData) => normalizeEvent(eventData))
      : [];

    try {
      window.sessionStorage.setItem(
        cacheKey,
        JSON.stringify({
          events: normalizedEvents,
          updatedAt: new Date().toISOString(),
        })
      );
    } catch (error) {
      void error;
    }

    notifyEventCacheUpdated(normalizedEvents);
    return normalizedEvents;
  }

  async function fetchEvents() {
    if (pendingEventsRequest) {
      return pendingEventsRequest;
    }

    pendingEventsRequest = fetch(adminEventsApiPath, {
      headers: {
        Accept: "application/json",
      },
    })
      .then(async (response) => {
        const responsePayload = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(responsePayload?.error?.message || "活動清單載入失敗。");
        }

        return writeCachedEvents(
          Array.isArray(responsePayload.events) ? responsePayload.events : []
        );
      })
      .finally(() => {
        pendingEventsRequest = null;
      });

    return pendingEventsRequest;
  }

  function upsertCachedEvent(eventData) {
    const nextEvent = normalizeEvent(eventData);
    const nextEventId = typeof nextEvent.id === "string" ? nextEvent.id : "";
    if (!nextEventId) {
      return readCachedEvents() ?? [];
    }

    const cachedEvents = readCachedEvents() ?? [];
    const existingIndex = cachedEvents.findIndex((item) => item?.id === nextEventId);
    const nextEvents = [...cachedEvents];

    if (existingIndex >= 0) {
      nextEvents[existingIndex] = nextEvent;
    } else {
      nextEvents.unshift(nextEvent);
    }

    return writeCachedEvents(nextEvents);
  }

  window.iPlaygroundPortalEvents = {
    getCachedEvents: readCachedEvents,
    preload: fetchEvents,
    refresh: fetchEvents,
    setCachedEvents: writeCachedEvents,
    upsertCachedEvent,
  };

  window.addEventListener("storage", (event) => {
    if (event.key !== cacheKey) {
      return;
    }

    const cachedEvents = readCachedEvents();
    if (Array.isArray(cachedEvents)) {
      notifyEventCacheUpdated(cachedEvents);
    }
  });
})();
