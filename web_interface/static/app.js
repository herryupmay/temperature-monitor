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

// Add these functions to your existing static/app.js file

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
            showSuccess('Scheduler started: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showError('Failed to start scheduler: ' + result.error);
        }
    } catch (error) {
        showError('Error starting scheduler: ' + error.message);
    }
}

async function stopScheduler() {
    try {
        const response = await fetch('/api/scheduler/stop', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('Scheduler stopped: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showError('Failed to stop scheduler: ' + result.error);
        }
    } catch (error) {
        showError('Error stopping scheduler: ' + error.message);
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
            showSuccess(`Test Announcement Complete: ${announcement.message}`);
            
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
            }
        } else {
            showError('Test failed: ' + result.error);
        }
    } catch (error) {
        showError('Error running test: ' + error.message);
    } finally {
        const button = document.getElementById('test-announcement-btn');
        if (button) {
            button.disabled = false;
            button.innerHTML = 'Test Announcement';
        }
    }
}

async function addStaffConfirmation() {
    try {
        const staffName = document.getElementById('staff-name').value.trim();
        const location = document.getElementById('confirmation-location').value;
        
        if (!staffName) {
            showError('Please enter a staff name');
            return;
        }
        
        if (!location) {
            showError('Please select a location');
            return;
        }
        
        const response = await fetch('/api/sheets/confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                staff_name: staffName,
                location: location
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('Staff confirmation added: ' + result.message);
            document.getElementById('staff-name').value = ''; // Clear input
        } else {
            showError('Failed to add confirmation: ' + result.error);
        }
    } catch (error) {
        showError('Error adding staff confirmation: ' + error.message);
    }
}

async function openGoogleSheets() {
    try {
        const response = await fetch('/api/sheets/url');
        const result = await response.json();
        
        if (result.success && result.url) {
            window.open(result.url, '_blank');
        } else {
            showError(result.message || 'No Google Sheets URL available');
        }
    } catch (error) {
        showError('Error getting sheets URL: ' + error.message);
    }
}

// Load scheduler settings into form
async function loadSchedulerSettings() {
    try {
        const response = await fetch('/api/scheduler/settings');
        const result = await response.json();
        
        if (result.success) {
            const settings = result.settings;
            document.getElementById('announce-time').value = settings.announce_time || '09:00';
            document.getElementById('scheduler-enabled').checked = settings.enabled || false;
            document.getElementById('search-hours').value = settings.search_hours_back || 24;
            document.getElementById('auto-log-sheets').checked = settings.auto_log_to_sheets !== false;
            document.getElementById('require-confirmation').checked = settings.require_staff_confirmation !== false;
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

// Helper functions for displaying messages
function showSuccess(message) {
    console.log('SUCCESS:', message);
    // You can enhance this with a proper notification system
    alert('✅ ' + message);
}

function showError(message) {
    console.error('ERROR:', message);
    // You can enhance this with a proper notification system
    alert('❌ ' + message);
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

// Updated Staff Confirmation Functions for app.js

// Show staff confirmation popup
function showStaffConfirmationPopup() {
    // Get available locations first
    loadAvailableLocations();
    
    // Show the modal
    document.getElementById('staff-confirmation-modal').style.display = 'block';
    
    // Focus on the name input
    document.getElementById('modal-staff-name').focus();
}

// Close staff confirmation popup
function closeStaffConfirmationPopup() {
    document.getElementById('staff-confirmation-modal').style.display = 'none';
    
    // Clear the form
    document.getElementById('modal-staff-name').value = '';
    document.getElementById('confirmation-result').style.display = 'none';
}

// Load available locations from recent sheets data
async function loadAvailableLocations() {
    try {
        // Try to get locations from recent scheduler status or sheets
        const response = await fetch('/api/scheduler/status');
        const result = await response.json();
        
        let locations = ['Dispensary', 'Fridge']; // Default locations
        
        // Could also try to get from recent test results or sheets
        // For now, use common locations
        
        const locationNamesDiv = document.getElementById('location-names');
        locationNamesDiv.innerHTML = locations.map(loc => `• ${loc}`).join('<br>');
        
    } catch (error) {
        console.error('Error loading locations:', error);
        document.getElementById('location-names').innerHTML = '• Dispensary<br>• Fridge';
    }
}

// Confirm for all locations at once
async function confirmAllLocations() {
    try {
        const staffName = document.getElementById('modal-staff-name').value.trim();
        
        if (!staffName) {
            showConfirmationResult('Please enter your name', 'error');
            return;
        }
        
        // Get list of locations to confirm
        const locations = ['Dispensary', 'Fridge']; // Could make this dynamic
        
        showConfirmationResult('Adding confirmations...', 'info');
        
        let successCount = 0;
        let errors = [];
        
        // Confirm for each location
        for (const location of locations) {
            try {
                const response = await fetch('/api/sheets/confirm', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        staff_name: staffName,
                        location: location
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    successCount++;
                } else {
                    errors.push(`${location}: ${result.error}`);
                }
            } catch (error) {
                errors.push(`${location}: Network error`);
            }
        }
        
        // Show results
        if (successCount === locations.length) {
            showConfirmationResult(`✅ Successfully confirmed for all ${successCount} locations!`, 'success');
            
            // Auto-close after 2 seconds
            setTimeout(() => {
                closeStaffConfirmationPopup();
                showAlert(`Staff confirmation complete: ${staffName} confirmed for all locations`);
            }, 2000);
            
        } else if (successCount > 0) {
            showConfirmationResult(`⚠️ Partially successful: ${successCount}/${locations.length} locations confirmed`, 'warning');
            if (errors.length > 0) {
                showConfirmationResult(errors.join('<br>'), 'error');
            }
        } else {
            showConfirmationResult(`❌ Failed to confirm any locations:<br>${errors.join('<br>')}`, 'error');
        }
        
    } catch (error) {
        showConfirmationResult(`❌ Error: ${error.message}`, 'error');
    }
}

// Show result in the confirmation popup
function showConfirmationResult(message, type) {
    const resultDiv = document.getElementById('confirmation-result');
    
    let bgColor = '#f8f9fa';
    let textColor = '#333';
    
    switch (type) {
        case 'success':
            bgColor = '#d4edda';
            textColor = '#155724';
            break;
        case 'error':
            bgColor = '#f8d7da';
            textColor = '#721c24';
            break;
        case 'warning':
            bgColor = '#fff3cd';
            textColor = '#856404';
            break;
        case 'info':
            bgColor = '#d1ecf1';
            textColor = '#0c5460';
            break;
    }
    
    resultDiv.style.backgroundColor = bgColor;
    resultDiv.style.color = textColor;
    resultDiv.innerHTML = message;
    resultDiv.style.display = 'block';
}

// Updated saveSchedulerSettings function to include staff confirmation setting
async function saveSchedulerSettings() {
    try {
        const settings = {
            announce_time: document.getElementById('announce-time').value,
            enabled: document.getElementById('scheduler-enabled').checked,
            search_hours_back: parseInt(document.getElementById('search-hours').value) || 24,
            auto_log_to_sheets: document.getElementById('auto-log-sheets').checked,
            require_staff_confirmation: document.getElementById('require-staff-confirmation').checked
        };
        
        // Validate time format
        if (settings.announce_time && !/^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/.test(settings.announce_time)) {
            showError('Please enter a valid time in HH:MM format (24-hour)');
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
            showSuccess('Scheduler settings saved: ' + result.message);
            loadSchedulerStatus(); // Refresh status
        } else {
            showError('Failed to save settings: ' + result.error);
        }
    } catch (error) {
        showError('Error saving scheduler settings: ' + error.message);
    }
}

// Close modal when clicking outside of it
document.addEventListener('click', function(event) {
    const modal = document.getElementById('staff-confirmation-modal');
    if (event.target === modal) {
        closeStaffConfirmationPopup();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        const modal = document.getElementById('staff-confirmation-modal');
        if (modal.style.display === 'block') {
            closeStaffConfirmationPopup();
        }
    }
});