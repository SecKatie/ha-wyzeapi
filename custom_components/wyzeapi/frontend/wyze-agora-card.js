// Wyze Agora ("lake") live-view card. Plays the browser-side Agora RTC stream
// for Gwell cameras (Solar Cam Pan, Cam OG, Doorbell Pro, ...). Credentials
// come from the wyzeapi/agora_stream_info websocket command.

const ENCRYPTION_MODES = {
  1: "aes-128-xts",
  2: "aes-128-ecb",
  3: "aes-256-xts",
  4: "sm4-128-ecb",
  5: "aes-128-gcm",
  6: "aes-256-gcm",
  7: "aes-128-gcm2",
  8: "aes-256-gcm2",
};

function b64ToBytes(b64) {
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
}

class WyzeAgoraCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("wyze-agora-card: 'entity' is required");
    }
    this._config = config;
    if (!this._built) {
      this._build();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config && !this._started) {
      this._start();
    }
  }

  getCardSize() {
    return 5;
  }

  _build() {
    this._built = true;
    this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      .wrap { position: relative; width: 100%; background: #000; border-radius: var(--ha-card-border-radius, 12px); overflow: hidden; }
      .player { width: 100%; aspect-ratio: 16 / 9; }
      .msg { color: #ddd; font: 14px system-ui, sans-serif; padding: 12px; }
    `;
    this._wrap = document.createElement("div");
    this._wrap.className = "wrap";
    this._player = document.createElement("div");
    this._player.className = "player";
    this._msg = document.createElement("div");
    this._msg.className = "msg";
    this._wrap.appendChild(this._player);
    this._wrap.appendChild(this._msg);
    this.shadowRoot.appendChild(style);
    this.shadowRoot.appendChild(this._wrap);
  }

  _log(text) {
    this._msg.textContent = text;
  }

  async _start() {
    if (this._started) return;
    this._started = true;
    if (!window.AgoraRTC) {
      this._started = false;
      this._log("Agora SDK not loaded.");
      return;
    }
    try {
      const info = await this._hass.connection.sendMessagePromise({
        type: "wyzeapi/agora_stream_info",
        entity_id: this._config.entity,
      });
      if (info.provider !== "lake") {
        this._log("This camera uses the standard camera card, not this one.");
        return;
      }
      await this._join(info);
    } catch (e) {
      this._log("Failed to start stream: " + (e && e.message ? e.message : e));
    }
  }

  async _join(info) {
    const client = window.AgoraRTC.createClient({ mode: "rtc", codec: "h264" });
    this._client = client;

    if (info.encryption_key && info.encryption_salt) {
      const mode = ENCRYPTION_MODES[info.encryption_mode] || "aes-128-gcm2";
      client.setEncryptionConfig(
        mode,
        info.encryption_key,
        b64ToBytes(info.encryption_salt),
      );
    }

    client.on("user-published", async (user, mediaType) => {
      await client.subscribe(user, mediaType);
      if (mediaType === "video") {
        this._msg.textContent = "";
        this._rejoinAttempts = 0;
        user.videoTrack.play(this._player);
      } else if (mediaType === "audio") {
        user.audioTrack.play();
      }
    });
    client.on("connection-state-change", (cur) => {
      if (cur === "DISCONNECTED" || cur === "FAILED") {
        this._rejoin();
      }
    });

    this._log("Connecting…");
    await client.join(info.app_id, info.channel, info.token, info.uid);
  }

  async _rejoin() {
    if (this._rejoining || !this.isConnected) return;
    if ((this._rejoinAttempts || 0) >= 5) {
      this._log("Stream disconnected. Reload to retry.");
      return;
    }
    this._rejoining = true;
    this._rejoinAttempts = (this._rejoinAttempts || 0) + 1;
    try {
      await this._stop();
      this._started = false;
      const delay = Math.min(2000 * this._rejoinAttempts, 15000);
      await new Promise((resolve) => setTimeout(resolve, delay));
      if (!this.isConnected) return;
      await this._start();
    } finally {
      this._rejoining = false;
    }
  }

  async _stop() {
    // Capture and clear first: a concurrent _start() may reassign this._client
    // while leave() is awaiting, and we must not null out the new client.
    const client = this._client;
    this._client = null;
    try {
      if (client) await client.leave();
    } catch (e) {
      // ignore leave errors
    }
  }

  disconnectedCallback() {
    this._stop();
    this._started = false;
  }
}

customElements.define("wyze-agora-card", WyzeAgoraCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "wyze-agora-card",
  name: "Wyze Agora Camera",
  description: "Live view for Wyze Agora/lake cameras (Solar Cam, OG, ...).",
});
