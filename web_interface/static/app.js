let selectedTempType = 'fridge'; // Default value, will be updated from config

function showAlert(message, type = 'success') {
    const alertContainer = document.getElementById('alert-container');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    alertContainer.appendChild(alertDiv);
    
    // Remove alert after 5 seconds
    setTimeout(() => {
        if (alertContainer.contains(alertDiv)) {
            alertContainer.removeChild(alertDiv);
        }
    }, 5000);
}

function connectGmail() {
    const btn = document.getElementById('gmail-connect-btn');
    btn.innerHTML = 'Connecting...';
    btn.disabled = true;
    
    fetch('/api/gmail/connect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Gmail connected successfully!');
            document.getElementById('email-filter-section').style.display = 'block';
            // Reload page to update UI
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error connecting Gmail: ' + (data.details || data.error), 'error');
            btn.innerHTML = 'Connect Gmail Account';
            btn.disabled = false;
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
        btn.innerHTML = 'Connect Gmail Account';
        btn.disabled = false;
    });
}

function disconnectGmail() {
    if (!confirm('Are you sure you want to disconnect Gmail? You will need to re-authenticate next time.')) {
        return;
    }

    fetch('/api/gmail/disconnect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Gmail disconnected successfully');
            // Reload page to update UI
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('Error disconnecting Gmail: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
    });
}

function testGmail() {
    const testContainer = document.getElementById('test-results-container');
    testContainer.innerHTML = '<div class="alert alert-info">Testing Gmail connection and searching for temperature emails...</div>';

    fetch('/api/gmail/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const summary = data.summary;
            let resultsHtml = '<div class="test-results">';
            resultsHtml += '<h4>Gmail Test Results:</h4>';
            resultsHtml += '<ul>';
            resultsHtml += `<li><strong>Emails found:</strong> ${summary.total_emails}</li>`;
            resultsHtml += `<li><strong>Temperature readings:</strong> ${summary.total_readings}</li>`;
            resultsHtml += `<li><strong>Locations:</strong> ${summary.locations.join(', ') || 'None'}</li>`;
            
            if (summary.latest_reading) {
                resultsHtml += `<li><strong>Latest reading:</strong> ${summary.latest_reading.value}°C at ${summary.latest_reading.location}</li>`;
            }
            
            if (summary.alerts.length > 0) {
                resultsHtml += `<li><strong>Alerts found:</strong> ${summary.alerts.join(', ')}</li>`;
            }
            
            resultsHtml += '</ul></div>';
            
            testContainer.innerHTML = resultsHtml;
            showAlert('Gmail test completed successfully!');
        } else {
            testContainer.innerHTML = `<div class="alert alert-error">Test failed: ${data.error}</div>`;
            showAlert('Gmail test failed: ' + data.error, 'error');
        }
    })
    .catch(error => {
        testContainer.innerHTML = `<div class="alert alert-error">Network error: ${error}</div>`;
        showAlert('Network error: ' + error, 'error');
    });
}

function selectOption(type) {
    // Remove previous selections
    document.querySelectorAll('.temp-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    // Hide all custom inputs
    document.querySelectorAll('.custom-inputs').forEach(inputs => {
        inputs.classList.remove('active');
    });
    
    // Select current option
    selectedTempType = type;
    document.getElementById(type + '-option').checked = true;
    document.querySelector(`[onclick="selectOption('${type}')"]`).classList.add('selected');
    
    // Show custom inputs if custom option selected
    if (type === 'custom') {
        document.getElementById('custom-inputs').classList.add('active');
    }
}

function testAlert() {
    fetch('/api/test-alert', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Test alert sent!');
        } else {
            showAlert('Error testing alert: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
    });
}

function saveSettings() {
    if (!selectedTempType) {
        showAlert('Please select a temperature monitoring option.', 'error');
        return;
    }
    
    let temperatureSettings = {
        type: selectedTempType
    };
    
    if (selectedTempType === 'custom') {
        const minTemp = document.getElementById('min-temp').value;
        const maxTemp = document.getElementById('max-temp').value;
        const customName = document.getElementById('custom-name').value;
        
        if (!minTemp || !maxTemp || !customName) {
            showAlert('Please fill in all custom temperature settings.', 'error');
            return;
        }
        
        temperatureSettings.min_temp = parseFloat(minTemp);
        temperatureSettings.max_temp = parseFloat(maxTemp);
        temperatureSettings.name = customName;
    } else if (selectedTempType === 'fridge') {
        temperatureSettings.min_temp = 2;
        temperatureSettings.max_temp = 8;
        temperatureSettings.name = 'Fridge Monitor';
    } else if (selectedTempType === 'room') {
        temperatureSettings.min_temp = 0;
        temperatureSettings.max_temp = 25;
        temperatureSettings.name = 'Room Monitor';
    }
    
    const ttsSettings = {
        daily_time: document.getElementById('daily-time').value,
        volume: document.getElementById('voice-volume').value,
        announcement_content: document.getElementById('announcement-content').value,
        require_confirmation: document.getElementById('require-confirmation').value
    };
    
    const settings = {
        temperature: temperatureSettings,
        tts: ttsSettings
    };
    
    // Show saving state
    const saveBtn = document.querySelector('.save-section .btn-success');
    const originalText = saveBtn.innerHTML;
    saveBtn.innerHTML = 'Saving...';
    saveBtn.disabled = true;
    
    fetch('/api/settings/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            saveBtn.innerHTML = 'Settings Saved!';
            showAlert('Settings saved successfully! Monitoring configuration updated.');
            
            // Reset button after 2 seconds
            setTimeout(() => {
                saveBtn.innerHTML = originalText;
                saveBtn.disabled = false;
            }, 2000);
        } else {
            showAlert('Error saving settings: ' + data.error, 'error');
            saveBtn.innerHTML = originalText;
            saveBtn.disabled = false;
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
        saveBtn.innerHTML = originalText;
        saveBtn.disabled = false;
    });
}

function saveEmailFilters() {
    const senderAddresses = document.getElementById('sender-addresses').value
        .split('\n')
        .map(s => s.trim())
        .filter(s => s.length > 0);
    
    const subjectKeywords = document.getElementById('subject-keywords').value
        .split('\n')
        .map(s => s.trim())
        .filter(s => s.length > 0);
    
    const excludeKeywords = document.getElementById('exclude-keywords').value
        .split('\n')
        .map(s => s.trim())
        .filter(s => s.length > 0);
    
    const requirePdf = document.getElementById('require-pdf').checked;
    
    const emailFilters = {
        sender_addresses: senderAddresses,
        subject_keywords: subjectKeywords,
        exclude_keywords: excludeKeywords,
        require_pdf: requirePdf
    };
    
    fetch('/api/gmail/save-filters', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email_filters: emailFilters })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('Email filters saved successfully!');
        } else {
            showAlert('Error saving email filters: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
    });
}

function testEmailFilters() {
    showAlert('Testing email filters...', 'info');
    
    fetch('/api/gmail/test-filters', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            let message = `Found ${data.emails_found} emails matching your filters`;
            if (data.sample_subjects && data.sample_subjects.length > 0) {
                message += `\n\nSample subjects:\n• ${data.sample_subjects.join('\n• ')}`;
            }
            showAlert(message);
        } else {
            showAlert('Error testing filters: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showAlert('Network error: ' + error, 'error');
    });
}

// Scheduler Management Functions
async function loadSchedulerStatus() {
    try {
        const response = await fetch('/api/scheduler/status');
        const result = await response.json();
        
        if (result.success) {
            updateSchedulerDisplay(result.status);
        } else {
            showError('Failed to load scheduler status: ' + result.error);
        }
    } catch (error) {
        showError('Error loading scheduler status: ' + error.message);
    }
}

function updateSchedulerDisplay(status) {
    const statusDiv = document.getElementById('scheduler-status');
    if (!statusDiv) return;
    
    const runningText = status.running ? '🟢 Running' : '🔴 Stopped';
    const enabledText = status.enabled ? 'Enabled' : 'Disabled';
    const nextRun = status.next_run_message || 'Not scheduled';
    
    statusDiv.innerHTML = `
        <div class="status-item">
            <strong>Status:</strong> ${runningText} (${enabledText})
        </div>
        <div class="status-item">
            <strong>Announce Time:</strong> ${status.announce_time || 'Not set'}
        </div>
        <div class="status-item">
            <strong>Next Run:</strong> ${nextRun}
        </div>
        <div class="status-item">
            <strong>Search Hours:</strong> ${status.search_hours_back || 24} hours back
        </div>
        <div class="status-item">
            <strong>Auto Log:</strong> ${status.auto_log_to_sheets ? 'Yes' : 'No'}
        </div>
    `;
}

async function startScheduler() {
    try {
        const response = await fetch('/api/scheduler/start', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('Scheduler started: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showAlert('Failed to start scheduler: ' + (result.error || result.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        showAlert('Error starting scheduler: ' + error.message, 'error');
    }
}

async function stopScheduler() {
    try {
        const response = await fetch('/api/scheduler/stop', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('Scheduler stopped: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showAlert('Failed to stop scheduler: ' + (result.error || result.message || 'Unknown error'), 'error');
        }
    } catch (error) {
        showAlert('Error stopping scheduler: ' + error.message, 'error');
    }
}

async function testAnnouncement() {
    try {
        const button = document.getElementById('test-announcement-btn');
        if (button) {
            button.disabled = true;
            button.innerHTML = 'Testing...';
        }
        
        const response = await fetch('/api/scheduler/test', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            const announcement = result.announcement;
            showAlert(`Test Announcement Complete: ${announcement.message}`);
            
            // Display detailed results
            const resultsDiv = document.getElementById('test-results');
            if (resultsDiv && result.raw_data.summary) {
                const summary = result.raw_data.summary;
                resultsDiv.innerHTML = `
                    <h4>Test Results:</h4>
                    <div class="test-result-item"><strong>Time:</strong> ${announcement.time}</div>
                    <div class="test-result-item"><strong>Emails Found:</strong> ${summary.total_emails}</div>
                    <div class="test-result-item"><strong>Temperature Readings:</strong> ${summary.total_readings}</div>
                    <div class="test-result-item"><strong>Locations:</strong> ${summary.locations.join(', ')}</div>
                    <div class="test-result-item"><strong>Sheets Logged:</strong> ${summary.sheets_logged ? 'Yes' : 'No'}</div>
                    ${summary.latest_reading ? `<div class="test-result-item"><strong>Latest:</strong> ${summary.latest_reading.value}°C at ${summary.latest_reading.location}</div>` : ''}
                `;
                resultsDiv.style.display = 'block';
            }
        } else {
            showAlert('Test failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showAlert('Error running test: ' + error.message, 'error');
    } finally {
        const button = document.getElementById('test-announcement-btn');
        if (button) {
            button.disabled = false;
            button.innerHTML = '🧪 Test Manual Announcement';
        }
    }
}

async function openGoogleSheets() {
    try {
        const response = await fetch('/api/sheets/url');
        const result = await response.json();
        
        if (result.success && result.url) {
            window.open(result.url, '_blank');
        } else {
            showAlert(result.message || 'No Google Sheets URL available', 'error');
        }
    } catch (error) {
        showAlert('Error getting sheets URL: ' + error.message, 'error');
    }
}

// Load scheduler settings into form
async function loadSchedulerSettings() {
    try {
        const response = await fetch('/api/scheduler/settings');
        const result = await response.json();
        
        if (result.success) {
            const settings = result.settings;
            
            // Safe element access with null checks
            const announceTimeEl = document.getElementById('announce-time');
            if (announceTimeEl) announceTimeEl.value = settings.announce_time || '09:00';
            
            const schedulerEnabledEl = document.getElementById('scheduler-enabled');
            if (schedulerEnabledEl) schedulerEnabledEl.checked = settings.enabled || false;
            
            const searchHoursEl = document.getElementById('search-hours');
            if (searchHoursEl) searchHoursEl.value = settings.search_hours_back || 24;
            
            const autoLogSheetsEl = document.getElementById('auto-log-sheets');
            if (autoLogSheetsEl) autoLogSheetsEl.checked = settings.auto_log_to_sheets !== false;
            
            const requireConfirmationEl = document.getElementById('require-staff-confirmation');
            if (requireConfirmationEl) requireConfirmationEl.checked = settings.require_staff_confirmation !== false;
        }
    } catch (error) {
        console.error('Error loading scheduler settings:', error);
    }
}

// Initialize scheduler interface when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load initial status and settings
    loadSchedulerStatus();
    loadSchedulerSettings();
    
    // Refresh status every 30 seconds
    setInterval(loadSchedulerStatus, 30000);
});

// Updated saveSchedulerSettings function
async function saveSchedulerSettings() {
    try {
        const announceTimeEl = document.getElementById('announce-time');
        const schedulerEnabledEl = document.getElementById('scheduler-enabled');
        const searchHoursEl = document.getElementById('search-hours');
        const autoLogSheetsEl = document.getElementById('auto-log-sheets');
        const requireConfirmationEl = document.getElementById('require-staff-confirmation');
        
        const settings = {
            announce_time: announceTimeEl ? announceTimeEl.value : '09:00',
            enabled: schedulerEnabledEl ? schedulerEnabledEl.checked : false,
            search_hours_back: searchHoursEl ? parseInt(searchHoursEl.value) || 24 : 24,
            auto_log_to_sheets: autoLogSheetsEl ? autoLogSheetsEl.checked : true,
            require_staff_confirmation: requireConfirmationEl ? requireConfirmationEl.checked : true
        };
        
        // Validate time format
        if (settings.announce_time && !/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/.test(settings.announce_time)) {
            showAlert('Please enter a valid time in HH:MM format (24-hour)', 'error');
            return;
        }
        
        const response = await fetch('/api/scheduler/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showAlert('Scheduler settings saved: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showAlert('Failed to save settings: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showAlert('Error saving scheduler settings: ' + error.message, 'error');
    }
}

// Helper functions for displaying messages
function showError(message) {
    console.error('ERROR:', message);
    showAlert(message, 'error');
}

// Initialize the interface
document.addEventListener('DOMContentLoaded', function() {
    // Get config from server to set initial selection
    fetch('/api/config')
        .then(response => response.json())
        .then(config => {
            selectedTempType = config.temperature?.type || 'fridge';
            if (selectedTempType) {
                selectOption(selectedTempType);
            }
        })
        .catch(error => {
            console.log('Could not load config, using default');
            selectedTempType = 'fridge';
        });
});