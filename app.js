/* Shamba Smart front end: subscribes to farm telemetry over MQTT (WebSockets)
   and sends the latest reading with each question to /api/chat. */
(() => {
  const cfg = window.SMARTFARM;
  const $ = (s) => document.querySelector(s);
  const params = new URLSearchParams(location.search);

  const T = {
    en: {
      tagline: "Farm advice from live sensor data", farm: "Farm", crop: "Crop", live: "Live sensors",
      connecting: "connecting…", online: "live", offline: "offline", manual_mode: "manual values",
      soil_moisture: "Soil moisture", air_temperature: "Air temperature", air_humidity: "Air humidity",
      soil_temperature: "Soil temperature", light: "Light", rainfall: "Rainfall", pump: "Pump",
      toggle_pump: "Toggle pump", manual: "No sensors? Enter values by hand", use_values: "Use these values",
      findings: "What the rules see", ask: "Ask the advisor", placeholder: "Type your question…", send: "Send",
      footer: "Advice is generated from sensor data and simple rules. Always check with your extension officer.",
      mode_llm: "Claude + rules", mode_rules: "rules only", waiting: "Waiting for sensor data…",
      hello: "Hello! I watch your farm's sensors. Ask me about watering, heat, rain or plant disease risk.",
      chips: ["Should I irrigate today?", "Is there a disease risk?", "Is it too hot for my crop?", "What should I do this evening?"],
      error: "Sorry, I could not reach the advisor. Check your internet connection.",
    },
    sw: {
      tagline: "Ushauri wa shamba kutoka data ya vihisi", farm: "Shamba", crop: "Zao", live: "Vihisi hai",
      connecting: "inaunganisha…", online: "hai", offline: "nje ya mtandao", manual_mode: "thamani za mkono",
      soil_moisture: "Unyevu wa udongo", air_temperature: "Joto la hewa", air_humidity: "Unyevu wa hewa",
      soil_temperature: "Joto la udongo", light: "Mwanga", rainfall: "Mvua", pump: "Pampu",
      toggle_pump: "Washa/zima pampu", manual: "Huna vihisi? Weka thamani kwa mkono", use_values: "Tumia thamani hizi",
      findings: "Kanuni zinaona nini", ask: "Muulize mshauri", placeholder: "Andika swali lako…", send: "Tuma",
      footer: "Ushauri unatokana na data ya vihisi na kanuni rahisi. Daima wasiliana na afisa ugani.",
      mode_llm: "Claude + kanuni", mode_rules: "kanuni tu", waiting: "Inasubiri data ya vihisi…",
      hello: "Habari! Ninafuatilia vihisi vya shamba lako. Niulize kuhusu umwagiliaji, joto, mvua au hatari ya magonjwa.",
      chips: ["Je, nimwagilie leo?", "Kuna hatari ya ugonjwa?", "Je, joto ni kali mno kwa zao langu?", "Nifanye nini jioni hii?"],
      error: "Samahani, sikuweza kumfikia mshauri. Angalia muunganisho wako wa intaneti.",
    },
  };

  let lang = params.get("lang") === "sw" ? "sw" : "en";
  let reading = null;
  let manual = false;
  let client = null;
  let history = [];
  let llm = false;

  const farmInput = $("#farm");
  farmInput.value = params.get("farm") || cfg.defaultFarm;
  if (params.get("crop")) $("#crop").value = params.get("crop");
  const topic = (suffix) => `${cfg.root}/${farmInput.value.trim() || cfg.defaultFarm}/${suffix}`;

  function t(key) { return T[lang][key] ?? key; }

  function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    document.querySelectorAll(".lang button").forEach((b) => b.classList.toggle("on", b.dataset.lang === lang));
    const chips = $("#chips");
    chips.innerHTML = "";
    t("chips").forEach((q) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.textContent = q;
      b.onclick = () => ask(q);
      chips.appendChild(b);
    });
    setMode();
    setConn(connState);
    if (reading) refreshFindings();
  }

  let connState = "connecting";
  function setConn(state) {
    connState = state;
    const el = $("#conn");
    el.className = "pill " + (state === "online" ? "on" : state === "manual" ? "warn" : "off");
    el.textContent = state === "manual" ? t("manual_mode") : t(state);
  }

  function setMode() {
    $("#mode").textContent = llm ? t("mode_llm") : t("mode_rules");
    $("#mode").className = "pill " + (llm ? "on" : "warn");
  }

  function show(r) {
    document.querySelectorAll(".card").forEach((card) => {
      const v = r[card.dataset.key];
      card.querySelector(".v").textContent = v === undefined || v === null ? "–" : v;
    });
    $("#pump").textContent = r.pump ?? "–";
    $("#stamp").textContent = r.ts ? new Date(r.ts).toLocaleTimeString() + (r.sim_time ? ` (farm ${r.sim_time})` : "") : t("manual_mode");
    $("#pumpBtn").disabled = !client || manual;
    const sm = r.soil_moisture;
    const card = document.querySelector('.card[data-key="soil_moisture"]');
    card.classList.toggle("alert", sm !== undefined && (sm < 25 || sm > 48));
  }

  let findingsTimer = null;
  function refreshFindings() {
    clearTimeout(findingsTimer);
    findingsTimer = setTimeout(async () => {
      const res = await post({ message: "", reading, crop: $("#crop").value, lang }).catch(() => null);
      if (!res) return;
      const ul = $("#findings");
      ul.innerHTML = "";
      res.findings.forEach((f) => {
        const li = document.createElement("li");
        li.className = f.level;
        li.textContent = f[lang];
        ul.appendChild(li);
      });
    }, 400);
  }

  function connect() {
    if (client) client.end(true);
    setConn("connecting");
    client = mqtt.connect(cfg.brokerUrl, { clientId: "chat-" + Math.random().toString(16).slice(2, 10), reconnectPeriod: 4000, connectTimeout: 8000 });
    client.on("connect", () => { setConn("online"); client.subscribe(topic("telemetry")); });
    client.on("close", () => { if (!manual) setConn("offline"); });
    client.on("message", (_topic, buf) => {
      if (manual) return;
      try { reading = JSON.parse(buf.toString()); } catch { return; }
      show(reading);
      refreshFindings();
    });
  }

  async function post(body) {
    const r = await fetch("api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  function bubble(role, text, extra) {
    const div = document.createElement("div");
    div.className = "msg " + role;
    div.textContent = text;
    if (extra) { const s = document.createElement("small"); s.textContent = extra; div.appendChild(s); }
    $("#log").appendChild(div);
    $("#log").scrollTop = $("#log").scrollHeight;
    return div;
  }

  async function ask(q) {
    q = q.trim();
    if (!q) return;
    bubble("user", q);
    const pending = bubble("bot typing", "…");
    try {
      const res = await post({ message: q, reading, crop: $("#crop").value, lang, history });
      pending.remove();
      bubble("bot", res.reply, res.mode === "llm" ? "Claude · " + (res.model || "") : t("mode_rules"));
      history.push({ role: "user", content: q }, { role: "assistant", content: res.reply });
      history = history.slice(-8);
    } catch {
      pending.remove();
      bubble("bot error", t("error"));
    }
  }

  // events
  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => { lang = b.dataset.lang; applyLang(); }));
  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); const q = $("#q").value; $("#q").value = ""; ask(q); });
  $("#crop").addEventListener("change", refreshFindings);
  farmInput.addEventListener("change", () => { manual = false; reading = null; connect(); });
  $("#pumpBtn").addEventListener("click", () => {
    if (!client || !reading) return;
    client.publish(topic("cmd/pump"), JSON.stringify({ state: reading.pump === "on" ? "off" : "on" }));
  });
  $("#manualForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    manual = true;
    reading = { farm_id: "manual", ts: new Date().toISOString(), source: "manual", pump: "off" };
    for (const [k, v] of f.entries()) reading[k] = parseFloat(v);
    setConn("manual");
    show(reading);
    refreshFindings();
  });

  // start
  fetch("api/chat").then((r) => r.json()).then((h) => { llm = !!h.llm; setMode(); }).catch(() => setMode());
  applyLang();
  bubble("bot", t("hello"));
  connect();
  setTimeout(() => { if (!reading) refreshFindings(); }, 6000);
})();
