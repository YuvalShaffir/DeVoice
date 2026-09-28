chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type !== "stream-id") return;
    console.log("[offscreen] received stream ID:", msg.streamId);
});
