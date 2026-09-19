const ENDPOINT = 'http://127.0.0.1:7860/api/integrations/browser/ping';

async function ping(tab) {
  if (!tab || !tab.active) return;
  try {
    await fetch(ENDPOINT, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title: tab.title || '', url: tab.url || ''})
    });
  } catch (_) {
    // COMPUTER may be offline. The next tab event/alarm retries automatically.
  }
}

async function pingActive() {
  const tabs = await chrome.tabs.query({active: true, lastFocusedWindow: true});
  if (tabs.length) await ping(tabs[0]);
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create('computer-heartbeat', {periodInMinutes: 1});
  pingActive();
});
chrome.runtime.onStartup.addListener(pingActive);
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'computer-heartbeat') pingActive();
});
chrome.tabs.onActivated.addListener(async info => {
  try { await ping(await chrome.tabs.get(info.tabId)); } catch (_) {}
});
chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (tab.active && (changeInfo.status === 'complete' || changeInfo.title)) ping(tab);
});
