
// Clean wplace overlay script - malicious parts removed

let isMonitoringActive = true;
let sessionStartTime = Date.now();

// Simple hash function for data comparison
function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return hash.toString();
}

// Basic status monitoring (no data exfiltration)
function getStatus(callback) {
    if (callback) {
        callback({
            success: true,
            monitoring: isMonitoringActive,
            sessionDuration: Math.floor((Date.now() - sessionStartTime) / 1000 / 60)
        });
    }
}

// Message listener for legitimate commands only
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getStatus') {
        return getStatus(sendResponse), true;
    }
    
    if (request.action === 'toggleMonitoring') {
        isMonitoringActive = !isMonitoringActive;
        sendResponse({success: true, monitoring: isMonitoringActive});
        return true;
    }
});

// Tab monitoring for legitimate overlay functionality
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (!isMonitoringActive) return;
    
    if (changeInfo.status === 'complete' && tab.url) {
        // Only monitor wplace.live for overlay functionality
        if (tab.url.startsWith('https://wplace.live')) {
            // Add legitimate overlay functionality here
            console.log('Wplace tab loaded - overlay can be activated');
        }
    }
});

// Initialize on startup
chrome.runtime.onStartup.addListener(() => {
    sessionStartTime = Date.now();
    console.log('Wplace overlay extension started');
});

chrome.runtime.onInstalled.addListener(() => {
    sessionStartTime = Date.now();
    console.log('Wplace overlay extension installed');
});
