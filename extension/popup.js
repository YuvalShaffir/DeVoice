const toggle = document.getElementById("toggle");
const stateEl = document.getElementById("state");
const errorEl = document.getElementById("error");
const vocalsToggle = document.getElementById("vocals");
const vocalsStateEl = document.getElementById("vocals-state");

const STATE_TEXT = {
    on: "On - separating audio on this tab",
    off: "Off - play audio in this tab, then switch on",
    silent: "No audio playing in this tab yet",
};

const VOCALS_TEXT = {
    on: "Vocals audible",
    off: "Vocals removed",
    disabled: "Turn DeVoice on first",
};

function render({on, vocals, text, error}) {
    toggle.setAttribute("aria-checked", String(on));
    stateEl.textContent = text;
    errorEl.textContent = error ?? "";
    errorEl.hidden = !error;
    toggle.disabled = false;
    renderVocals(on, vocals);
}

function renderVocals(capturingHere, vocals) {
    const audible = capturingHere && vocals === true;
    vocalsToggle.setAttribute("aria-checked", String(audible));
    vocalsToggle.disabled = !capturingHere;
    vocalsStateEl.textContent = capturingHere ? VOCALS_TEXT[audible ? "on" : "off"] : VOCALS_TEXT.disabled;
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
    render({on, vocals: status.vocals, text: STATE_TEXT[on ? "on" : "off"], error: status.error});
}

toggle.addEventListener("click", async () => {
    const turningOn = toggle.getAttribute("aria-checked") !== "true";
    toggle.disabled = vocalsToggle.disabled = true;
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

vocalsToggle.addEventListener("click", async () => {
    const on = vocalsToggle.getAttribute("aria-checked") !== "true";
    vocalsToggle.disabled = true;
    await chrome.runtime.sendMessage({type: "set-vocals", on});
    await refresh();
});

document.getElementById("settings").addEventListener("click", (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
});

void refresh();
