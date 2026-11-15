(() => {
  const NativeWebSocket = window.WebSocket;

  class InterceptedWebSocket extends NativeWebSocket {
    constructor(...args) {
      super(...args);
      this.addEventListener("message", (event) => {
        if (typeof event.data !== "string") {
          return;
        }

        try {
          const payload = JSON.parse(event.data);
          if (payload?.name !== "candle-generated") {
            return;
          }

          window.postMessage(
            { source: "IQ_TICK_BRIDGE", payload: event.data },
            window.location.origin
          );
        } catch {
          // Ignore non-JSON WebSocket messages.
        }
      });
    }
  }

  window.WebSocket = InterceptedWebSocket;
})();
