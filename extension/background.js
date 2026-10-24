/* Service worker
*
* Orchestration ONLY
*
* Tasks:
* 1. start capture when the popup asks (toggle on), report status to the popup
* 2. ask Chrome for a stream capture handle
* 3. Hand that handle to whoever actually needs it
* */

const ERRORS = {
    setup: ["!", "DeVoice: paste the backend token on the options page"],
    auth: ["AUTH", "DeVoice: backend rejected the token - re-copy it from backend/.auth_token"],
    unreachable: ["DOWN", "DeVoice: backend not reachable at 127.0.0.1:8000"],
};

function showError(reason) {
    const [text, title] = ERRORS[reason];
    chrome.action.setBadgeText({ text });
    chrome.action.setTitle({ title });
    chrome.storage.session.set({ lastError: title });
}

async function offscreenContexts() {
    return chrome.runtime.getContexts({ contextTypes: ["OFFSCREEN_DOCUMENT"] });
}

async function startCapture(tabId) {
    const {authToken} = await chrome.storage.local.get("authToken");
    if (!authToken) {
        showError("setup");
        chrome.runtime.openOptionsPage();
        return {ok: false, reason: "setup"};
    }

    const current = await chrome.tabs.get(tabId);
    if (!current.audible) {
        console.log("[background] tab not audible, skipping capture");
        return {ok: false, reason: "silent"};
    }

    await chrome.action.setBadgeText({text: ""});
    await chrome.storage.session.remove("lastError");

    if ((await offscreenContexts()).length === 0) {
        await chrome.offscreen.createDocument({
            url: "offscreen.html",
            reasons: ["USER_MEDIA"],
            justification: "Hold the capture stream",
        });
    }

    const streamId = await chrome.tabCapture.getMediaStreamId({
        targetTabId: tabId,
    });

    await chrome.runtime.sendMessage({type: "stream-id", streamId, token: authToken, tabId});
    return {ok: true};
}

async function getStatus() {
    const {lastError} = await chrome.storage.session.get("lastError");
    const capturing = (await offscreenContexts()).length > 0
        ? await chrome.runtime.sendMessage({type: "capture-status"})
        : null;
    const tabId = capturing?.tabId ?? null;
    return {tabId, error: lastError ?? null, vocals: tabId === null ? null : capturing.vocals};
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "backend-error") {
        showError(msg.reason);
        if (msg.reason === "auth") chrome.runtime.openOptionsPage();
    } else if (msg.type === "start-capture") {
        void startCapture(msg.tabId).then(sendResponse);
        return true;
    } else if (msg.type === "get-status") {
        void getStatus().then(sendResponse);
        return true;
    }
});
