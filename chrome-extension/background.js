// One click: hand the current tab to the receiver inside Papir.app.
// Every outcome is announced in words — a badge on its own explains nothing.
const DEFAULT_ENDPOINT = "http://127.0.0.1:47821";
const INK = "#1F1B16";
const RED = "#8b2f2f";

function badge(text, colour) {
  chrome.action.setBadgeBackgroundColor({ color: colour });
  chrome.action.setBadgeText({ text });
  setTimeout(() => chrome.action.setBadgeText({ text: "" }), 6000);
}

function tell(title, message) {
  chrome.action.setTitle({ title: title + " — " + message });
  chrome.notifications.create("papir-" + Date.now(), {
    type: "basic",
    iconUrl: "icons/128.png",
    title: title,
    message: message,
    priority: 2
  });
}

function succeed() {
  badge("\u2713", INK);
  tell("Sent to Papir", "It's in Papir's review window. Press Send there to reach your Kindle.");
}

function fail(message) {
  badge("!", RED);
  tell("Papir", message);
}

chrome.action.onClicked.addListener(async (tab) => {
  const { token, endpoint } = await chrome.storage.local.get(["token", "endpoint"]);
  if (!token) {
    fail("No token yet. Right-click this button \u2192 Options and paste the token from Papir \u2192 Settings \u2192 Browser.");
    chrome.runtime.openOptionsPage();
    return;
  }

  const url = tab && tab.url ? tab.url : "";
  if (!/^https?:\/\//i.test(url)) {
    fail("This tab has no web address to send. Open the document itself, not a Chrome settings page.");
    return;
  }

  const base = (endpoint || DEFAULT_ENDPOINT).replace(/\/+$/, "");
  let response;
  try {
    response = await fetch(base + "/send", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
      body: JSON.stringify({ url })
    });
  } catch (error) {
    fail("Papir isn't answering on " + base + ". Open Papir, and check Settings \u2192 Browser \u2192 Accept papir:// links is on. If it is, this is an older Papir build without the receiver.");
    return;
  }

  let body = {};
  try { body = await response.json(); } catch (ignored) {}

  if (response.ok) return succeed();
  if (response.status === 401) {
    return fail("Papir rejected the token. Open Papir \u2192 Settings \u2192 Browser, press Copy Token, and paste it into this extension's options.");
  }
  if (response.status === 409) {
    return fail("Sharing is switched off. Turn on Settings \u2192 Browser \u2192 Accept papir:// links.");
  }
  fail(body.error || ("Papir answered " + response.status + "."));
});

chrome.runtime.onInstalled.addListener(async () => {
  const { token } = await chrome.storage.local.get(["token"]);
  if (!token) chrome.runtime.openOptionsPage();
});
