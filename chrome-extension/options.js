const DEFAULT_ENDPOINT = "http://127.0.0.1:47821";
const tokenInput = document.getElementById("token");
const endpointInput = document.getElementById("endpoint");
const status = document.getElementById("status");

function say(message, bad) {
  status.textContent = message;
  status.className = bad ? "bad" : "";
}

async function load() {
  const { token, endpoint } = await chrome.storage.local.get(["token", "endpoint"]);
  tokenInput.value = token || "";
  endpointInput.value = endpoint || DEFAULT_ENDPOINT;
}

async function save() {
  const token = tokenInput.value.trim();
  const endpoint = (endpointInput.value.trim() || DEFAULT_ENDPOINT).replace(/\/+$/, "");
  if (token && !/^[0-9a-f]{64}$/i.test(token)) {
    say("That token doesn't look right — it should be 64 hex characters.", true);
    return;
  }
  await chrome.storage.local.set({ token, endpoint });
  say(token ? "Saved." : "Saved. No token yet, so the button will open this page.", !token);
}

async function test() {
  const token = tokenInput.value.trim();
  const endpoint = (endpointInput.value.trim() || DEFAULT_ENDPOINT).replace(/\/+$/, "");
  if (!token) { say("Add a token first.", true); return; }
  try {
    const response = await fetch(endpoint + "/health", { headers: { Authorization: "Bearer " + token } });
    if (response.ok) {
      const body = await response.json();
      say(body.intake_enabled === false
        ? "Papir is listening, but papir:// links are off in Settings ▸ Browser."
        : "Papir is listening.", body.intake_enabled === false);
    } else if (response.status === 401) {
      say("Papir is running, but that token doesn't match. Press Copy Token in Settings \u25b8 Browser and paste it again.", true);
    } else {
      say("Papir answered " + response.status + ".", true);
    }
  } catch (error) {
    say("Nothing is listening on " + endpoint + ". Open Papir, turn on Settings \u25b8 Browser \u25b8 Accept papir:// links, then test again. If Papir is already open with that on, you are running an older build without the receiver.", true);
  }
}

document.getElementById("save").addEventListener("click", save);
document.getElementById("test").addEventListener("click", test);
document.getElementById("version").textContent =
  "Send to Papir v" + chrome.runtime.getManifest().version;
load().then(() => {
  if (tokenInput.value.trim()) test();
});
