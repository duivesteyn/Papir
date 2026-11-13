// Runs only on the loopback page Papir opens. The token is in the URL fragment,
// which browsers never send to the server, so this is a local handshake.
const token = location.hash.slice(1);
const heading = document.getElementById("t");
const message = document.getElementById("m");

if (/^[0-9a-f]{64}$/i.test(token)) {
  chrome.storage.local.set({ token: token, endpoint: location.origin }).then(() => {
    heading.textContent = "Connected to Papir";
    message.textContent = "You can close this tab. Click the Papir button on any page.";
    if (history.replaceState) history.replaceState(null, "", location.pathname);
  });
} else {
  heading.textContent = "Nothing to pair";
  message.textContent = "Open Papir, then press Connect Browser in Settings.";
}
