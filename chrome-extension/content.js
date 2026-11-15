const SERVER_URL = "ws://localhost:8765";
const RECONNECT_DELAY_MS = 2000;
const MAX_QUEUED_MESSAGES = 500;
const pendingMessages = [];
let localSocket = null;
let reconnectTimer = null;

function connectToPython() {
  if (
    localSocket &&
    (localSocket.readyState === WebSocket.CONNECTING ||
      localSocket.readyState === WebSocket.OPEN)
  ) {
    return;
  }

  try {
    localSocket = new WebSocket(SERVER_URL);

    localSocket.onopen = () => {
      console.info("[Tick Bridge] Connected to local Python server.");
      while (pendingMessages.length > 0 && localSocket.readyState === WebSocket.OPEN) {
        localSocket.send(pendingMessages.shift());
      }
    };

    localSocket.onclose = () => {
      localSocket = null;
      scheduleReconnect();
    };

    localSocket.onerror = () => {
      localSocket.close();
    };
  } catch (error) {
    console.error("[Tick Bridge] Could not connect to local server.", error);
    localSocket = null;
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer === null) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectToPython();
    }, RECONNECT_DELAY_MS);
  }
}

connectToPython();

window.addEventListener("message", (event) => {
  if (
    event.source !== window ||
    event.origin !== window.location.origin ||
    event.data?.source !== "IQ_TICK_BRIDGE" ||
    typeof event.data.payload !== "string"
  ) {
    return;
  }

  if (localSocket?.readyState === WebSocket.OPEN) {
    localSocket.send(event.data.payload);
    return;
  }

  if (pendingMessages.length === MAX_QUEUED_MESSAGES) {
    pendingMessages.shift();
    console.warn("[Tick Bridge] Queue full; dropping the oldest candle message.");
  }
  pendingMessages.push(event.data.payload);
});
