const input = document.getElementById("token");
const statusEl = document.getElementById("status");

chrome.storage.local.get("authToken").then(({authToken}) => {
   if (authToken) statusEl.textContent = "A token is saved. Paste a new one to replace it.";
});

document.getElementById("save").addEventListener("click", async () => {
   const val = input.value.trim();
   if (!val) {
       statusEl.textContent = "Paste the token from backend/.auth_token first.";
       return;
   }
   await chrome.storage.local.set({ authToken: val});
   await chrome.action.setBadgeText({ text: ""});
   input.value = "";
   statusEl.textContent = "Saved. Click the toolbar icon on a tab playing audio."
});
