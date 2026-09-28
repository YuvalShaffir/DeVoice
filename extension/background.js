/* Service worker
*
* Orchestration ONLY
*
* Tasks:
* 1. fire only when the extension's primary toolbar icon was clicked
* 2. ask Chrome for a stream capture handle
* 3. Hand that handle to whoever actually needs it
* */

chrome.action.onClicked.addListener(async (tab) =>{
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

    await chrome.runtime.sendMessage({type: "stream-id", streamId});
});
