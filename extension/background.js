/* Service worker
*
* Orchestration ONLY
*
* Tasks:
* 1. fire only when the extension's primary toolbar icon was clicked
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
}

chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type !== "backend-error") return;
    showError(msg.reason);
    if (msg.reason === "auth") chrome.runtime.openOptionsPage();
});

chrome.action.onClicked.addListener(async (tab) =>{
    const {authToken} = await chrome.storage.local.get("authToken");
    if (!authToken) {
        showError("setup");
        chrome.runtime.openOptionsPage();
        return;
    }
    await chrome.action.setBadgeText({text: ""});

    const current = await chrome.tabs.get(tab.id);
    if (!current.audible) {
        console.log("[background] tab not audible, skipping capture");
        return;
    }

    const existing = await chrome.runtime.getContexts({
       contextTypes: ["OFFSCREEN_DOCUMENT"],
   });

    if (existing.length === 0) {
        await chrome.offscreen.createDocument({
            url: "offscreen.html",
            reasons: ["USER_MEDIA"],
            justification: "Hold the capture stream",
        });
    }

    const streamId = await chrome.tabCapture.getMediaStreamId({
        targetTabId: tab.id,
    });

    await chrome.runtime.sendMessage({type: "stream-id", streamId, token: authToken});
});
