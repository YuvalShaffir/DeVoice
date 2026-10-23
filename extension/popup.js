const toggle = document.getElementById("toggle");
const stateEl = document.getElementById("state");
const errorEl = document.getElementById("error");

const STATE_TEXT = {
    on: "On - vocals removed on this tab",
    off: "Off - play audio in this tab, then switch on",
    silent: "No audio playing in this tab yet",
};

function render({on, text, error}) {
    toggle.setAttribute("aria-checked", String(on));
    stateEl.textContent = text;
    errorEl.textContent = error ?? "";
    errorEl.hidden = !error;
    toggle.disabled = false;
}

async function activeTabId() {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    return tab.id;
}

async function refresh() {
    const [tabId, status] = await Promise.all([
        activeTabId(),
        chrome.runtime.sendMessage({type: "get-status"}),
    ]);
    const on = status.tabId === tabId;
    render({on, text: STATE_TEXT[on ? "on" : "off"], error: status.error});
}

toggle.addEventListener("click", async () => {
    const turningOn = toggle.getAttribute("aria-checked") !== "true";
    toggle.disabled = true;
    stateEl.textContent = turningOn ? "Starting…" : "Stopping…";
    if (!turningOn) {
        await chrome.runtime.sendMessage({type: "stop-capture"});
        await refresh();
        return;
    }
    const res = await chrome.runtime.sendMessage({type: "start-capture", tabId: await activeTabId()});
    if (res.ok) return refresh();
    const status = await chrome.runtime.sendMessage({type: "get-status"});
    render({on: false, text: res.reason === "silent" ? STATE_TEXT.silent : STATE_TEXT.off, error: status.error});
});

document.getElementById("settings").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
});

void refresh();
