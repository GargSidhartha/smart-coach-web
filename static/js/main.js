document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('upload-form');
    const fileDropArea = document.getElementById('file-drop-area');
    const fileInput = document.getElementById('video-file');
    const fileName = document.getElementById('file-name');
    const statusMessage = document.getElementById('status-message');
    const progressBar = document.getElementById('progress-bar');
    const resultsArea = document.getElementById('results-area');
    const videoResultDiv = document.getElementById('video-result');
    const statsResultDiv = document.getElementById('stats-result');
    const resultVideoPlayer = document.getElementById('result-video-player');
    const resultVideoLink = document.getElementById('result-video-link');
    const resultStatsData = document.getElementById('result-stats-data');
    const resultStatsLink = document.getElementById('result-stats-link');

    let currentTaskId = null;
    let pollInterval = null;

    // Drag and drop functionality
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        fileDropArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        fileDropArea.classList.add('drag-over');
    }

    function unhighlight() {
        fileDropArea.classList.remove('drag-over');
    }

    fileDropArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        updateFileName(files[0]);
    }

    fileInput.addEventListener('change', function() {
        if (fileInput.files.length > 0) {
            updateFileName(fileInput.files[0]);
        }
    });

    function updateFileName(file) {
        if (file) {
            fileName.textContent = file.name;
            fileName.style.display = 'block';
        } else {
            fileName.style.display = 'none';
        }
    }

    form.addEventListener('submit', async function(event) {
        event.preventDefault();
        resetUI();

        const formData = new FormData(form);
        const videoFile = fileInput.files[0];

        if (!videoFile) {
            document.getElementById('status-stage').textContent = 'Error';
            document.getElementById('status-message').textContent = 'Please select a video file first.';
            return;
        }

        // Show loading spinner
        document.getElementById('status-icon').style.display = 'inline-block';
        document.getElementById('status-stage').textContent = 'Uploading';
        document.getElementById('status-message').textContent = 'Preparing video file...';
        progressBar.style.display = 'block';
        progressBar.value = 0;
        
        // Update processing steps
        updateProcessingStep('upload');
        
        // Add loading animation to upload button
        const uploadBtn = document.querySelector('.upload-btn');
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
        uploadBtn.disabled = true;

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
            }

            const data = await response.json();
            currentTaskId = data.task_id;
            
            document.getElementById('status-stage').textContent = 'Preparing';
            document.getElementById('status-message').textContent = 'Video uploaded. Processing started...';
            progressBar.value = 10;
            
            // Update processing steps
            updateProcessingStep('prepare');
            
            // Update button state
            uploadBtn.innerHTML = '<i class="fas fa-check"></i> Uploaded';
            
            pollStatus(currentTaskId);

        } catch (error) {
            console.error('Upload error:', error);
            document.getElementById('status-icon').style.display = 'none';
            document.getElementById('status-stage').textContent = 'Failed';
            document.getElementById('status-message').textContent = `Upload failed: ${error.message}`;
            document.getElementById('status-message').style.color = 'var(--accent-red)';
            progressBar.style.display = 'none';
            
            // Reset steps
            resetProcessingSteps();
            
            // Reset button state
            uploadBtn.innerHTML = 'Upload & Process';
            uploadBtn.disabled = false;
        }
    });

    function updateProcessingStep(currentStep) {
        const steps = document.querySelectorAll('.processing-steps .step');
        const stepOrder = ['upload', 'prepare', 'analyze', 'process', 'complete'];
        
        let currentStepFound = false;
        
        steps.forEach(step => {
            const stepType = step.getAttribute('data-step');
            const stepIndex = stepOrder.indexOf(stepType);
            const currentStepIndex = stepOrder.indexOf(currentStep);
            
            // Remove all classes first
            step.classList.remove('active', 'completed');
            
            // Mark steps that should be completed
            if (stepIndex < currentStepIndex) {
                step.classList.add('completed');
            } 
            // Mark current step as active
            else if (stepType === currentStep) {
                step.classList.add('active');
                currentStepFound = true;
            }
        });
    }
    
    function resetProcessingSteps() {
        const steps = document.querySelectorAll('.processing-steps .step');
        steps.forEach(step => {
            step.classList.remove('active', 'completed');
        });
    }

    function pollStatus(taskId) {
        if (pollInterval) {
            clearInterval(pollInterval);
        }

        let lastProgressUpdate = null;
        let progressHistory = [];
        const maxHistoryPoints = 5; // Use last 5 progress points to calculate ETA

        pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/status/${taskId}`);
                if (!response.ok) {
                    clearInterval(pollInterval);
                    document.getElementById('status-icon').style.display = 'none';
                    document.getElementById('status-stage').textContent = 'Error';
                    document.getElementById('status-message').textContent = 'Error checking status. Please try again later.';
                    document.getElementById('eta-display').style.display = 'none';
                    console.error('Status check failed:', response.status);
                    progressBar.style.display = 'none';
                    
                    // Reset steps
                    resetProcessingSteps();
                    
                    // Reset button
                    document.querySelector('.upload-btn').innerHTML = 'Upload & Process';
                    document.querySelector('.upload-btn').disabled = false;
                    return;
                }

                const data = await response.json();
                
                // Ensure progress bar is visible during processing stages
                if (data.state === 'PENDING' || data.state === 'STARTED' || data.state === 'PROGRESS') {
                    progressBar.style.display = 'block';
                    document.getElementById('status-icon').style.display = 'inline-block';
                } else {
                    progressBar.style.display = 'none';
                    document.getElementById('status-icon').style.display = 'none';
                    document.getElementById('eta-display').style.display = 'none';
                }

                // Update status with friendly names and icons
                let stateIcon = '';
                let friendlyState = '';
                let currentStep = 'prepare'; // Default step
                
                switch(data.state) {
                    case 'PENDING':
                        stateIcon = '<i class="fas fa-hourglass-start fa-spin"></i>';
                        friendlyState = 'Queued';
                        currentStep = 'prepare';
                        break;
                    case 'STARTED':
                        stateIcon = '<i class="fas fa-cogs fa-spin"></i>';
                        friendlyState = 'Started';
                        currentStep = 'analyze';
                        break;
                    case 'PROGRESS':
                        // Check the status message to determine what step we're in
                        if (data.info && data.info.status) {
                            if (data.info.status.includes('Converting')) {
                                stateIcon = '<i class="fas fa-film fa-spin"></i>';
                                friendlyState = 'Finalizing';
                                currentStep = 'process';
                            } else {
                                stateIcon = '<i class="fas fa-code-branch fa-spin"></i>';
                                friendlyState = 'Analyzing';
                                currentStep = 'analyze';
                            }
                        } else {
                            stateIcon = '<i class="fas fa-code-branch fa-spin"></i>';
                            friendlyState = 'Processing';
                            currentStep = 'analyze';
                        }
                        break;
                    case 'SUCCESS':
                        stateIcon = '<i class="fas fa-check-circle"></i>';
                        friendlyState = 'Complete';
                        currentStep = 'complete';
                        break;
                    case 'FAILURE':
                        stateIcon = '<i class="fas fa-exclamation-triangle" style="color: var(--accent-red);"></i>';
                        friendlyState = 'Failed';
                        resetProcessingSteps();
                        break;
                    default:
                        stateIcon = '<i class="fas fa-info-circle"></i>';
                        friendlyState = data.state;
                }
                
                // Update the processing step visualization
                if (data.state !== 'FAILURE') {
                    updateProcessingStep(currentStep);
                }
                
                // Format the status text
                let statusText = '';
                if (data.state === 'PROGRESS' && data.info && data.info.status) {
                    statusText = data.info.status;
                } else {
                    statusText = data.status || 'Processing video...';
                }
                
                document.getElementById('status-icon').innerHTML = stateIcon;
                document.getElementById('status-stage').textContent = friendlyState;
                document.getElementById('status-message').textContent = statusText;

                // Update progress bar and calculate ETA if we have progress data
                const etaDisplay = document.getElementById('eta-display');
                
                if (data.state === 'PROGRESS' && data.info && data.info.current && data.info.total) {
                    // Calculate percent complete
                    let percent = (data.info.current / data.info.total) * 100;
                    progressBar.value = percent;
                    
                    // Check if we have direct ETA from the server
                    if (data.info.eta) {
                        // Use the direct ETA from Celery/tqdm instead of calculating ourselves
                        etaDisplay.textContent = `ETA: ${data.info.eta}`;
                        etaDisplay.style.display = 'inline-block';
                        
                        // Add the rate data if available
                        const statusText = data.info.rate ? 
                            `${data.info.status} (${Math.round(percent)}%) [${data.info.rate}]` : 
                            `${data.info.status} (${Math.round(percent)}%)`;
                        document.getElementById('status-message').textContent = statusText;
                    } else {
                        // If no direct ETA is available, fallback to calculating it
                        document.getElementById('status-message').textContent = `${data.info.status || 'Processing...'} (${Math.round(percent)}%)`;
                        
                        // ETA calculation (existing code as fallback)
                        const now = new Date().getTime();
                        const current = data.info.current;
                        const total = data.info.total;
                        
                        // Add progress point to history
                        if (lastProgressUpdate) {
                            const timeDiff = (now - lastProgressUpdate) / 1000; // seconds
                            const progressDiff = current - progressHistory[progressHistory.length - 1].progress;
                            
                            if (progressDiff > 0) { // Only track if progress was made
                                // ...existing code...
                            }
                        } else {
                            // First progress update
                            progressHistory.push({
                                time: now,
                                progress: current,
                                rate: null // No rate yet
                            });
                        }
                        
                        lastProgressUpdate = now;
                    }
                } else if (data.state === 'STARTED') {
                    progressBar.value = 15;
                    etaDisplay.style.display = 'none';
                } else if (data.state === 'PENDING') {
                    progressBar.value = 5;
                    etaDisplay.style.display = 'none';
                } else if (data.state === 'SUCCESS') {
                    progressBar.value = 100;
                    etaDisplay.style.display = 'none';
                } else {
                    etaDisplay.style.display = 'none';
                }

                if (data.state === 'SUCCESS') {
                    clearInterval(pollInterval);
                    document.getElementById('status-stage').textContent = 'Complete';
                    document.getElementById('status-message').textContent = 'Processing complete!';
                    document.getElementById('status-message').classList.add('success-animation');
                    document.getElementById('eta-display').style.display = 'none';
                    
                    // Reset upload button
                    document.querySelector('.upload-btn').innerHTML = 'Upload & Process';
                    document.querySelector('.upload-btn').disabled = false;
                    
                    displayResults(data);
                } else if (data.state === 'FAILURE') {
                    clearInterval(pollInterval);
                    document.getElementById('status-stage').textContent = 'Failed';
                    document.getElementById('status-message').textContent = `Processing failed: ${data.status}`;
                    document.getElementById('status-message').style.color = 'var(--accent-red)';
                    document.getElementById('eta-display').style.display = 'none';
                    resultsArea.style.display = 'block';
                    
                    // Reset upload button
                    document.querySelector('.upload-btn').innerHTML = 'Upload & Process';
                    document.querySelector('.upload-btn').disabled = false;
                } else if (data.state === 'REVOKED' || data.state === 'RETRY') {
                     clearInterval(pollInterval);
                     document.getElementById('status-stage').textContent = data.state;
                     document.getElementById('status-message').textContent = 'Task interrupted';
                     document.getElementById('eta-display').style.display = 'none';
                     
                     // Reset upload button
                     document.querySelector('.upload-btn').innerHTML = 'Upload & Process';
                     document.querySelector('.upload-btn').disabled = false;
                }

            } catch (error) {
                clearInterval(pollInterval);
                document.getElementById('status-icon').style.display = 'none';
                document.getElementById('status-stage').textContent = 'Error';
                document.getElementById('status-message').textContent = 'Error checking status. See console.';
                document.getElementById('eta-display').style.display = 'none';
                console.error('Polling error:', error);
                progressBar.style.display = 'none';
                
                // Reset upload button
                document.querySelector('.upload-btn').innerHTML = 'Upload & Process';
                document.querySelector('.upload-btn').disabled = false;
            }
        }, 2000);
    }

   async function displayResults(data) {
        resultsArea.style.display = 'block';

        // Smooth reveal animation
        resultsArea.style.opacity = '0';
        resultsArea.style.transform = 'translateY(20px)';
        
        // Trigger reflow for animation
        void resultsArea.offsetWidth;
        
        // Animate in
        resultsArea.style.opacity = '1';
        resultsArea.style.transform = 'translateY(0)';

        if (data.result_video) {
            resultVideoPlayer.src = data.result_video;
            resultVideoLink.href = data.result_video;
            
            // Set the download attribute with the filename
            const videoFilename = data.result_video.split('/').pop();
            resultVideoLink.setAttribute('download', videoFilename);
            
            resultVideoPlayer.style.display = 'block';
            resultVideoLink.style.display = 'block';
            videoResultDiv.style.display = 'block';
            
            // Add event listener to video player to handle successful loading
            resultVideoPlayer.addEventListener('loadeddata', function() {
                // Add a subtle zoom animation when video is ready
                resultVideoPlayer.style.transform = 'scale(0.98)';
                setTimeout(() => {
                    resultVideoPlayer.style.transform = 'scale(1)';
                }, 200);
            });
            
            // Add event listener for video error
            resultVideoPlayer.addEventListener('error', function() {
                console.error('Video playback error');
                const warningElem = document.querySelector('.playback-warning');
                if (warningElem) {
                    warningElem.style.backgroundColor = '#f8d7da';
                    warningElem.style.borderColor = '#f5c6cb';
                    warningElem.style.color = '#721c24';
                    warningElem.innerHTML = '<p><strong>⚠️ Playback Error:</strong> Unable to play this video in your browser. Please use the download button below and open with Windows Media Player or VLC.</p>';
                }
            });
        } else {
             videoResultDiv.style.display = 'none';
        }

        if (data.result_stats) {
            resultStatsLink.href = data.result_stats;
            
            // Set download attribute for stats file
            const statsFilename = data.result_stats.split('/').pop();
            resultStatsLink.setAttribute('download', statsFilename);
            
            resultStatsLink.style.display = 'block';
            statsResultDiv.style.display = 'block';
            
            // Fetch and display JSON stats with loading indicator
            resultStatsData.innerHTML = '<div style="text-align: center;"><i class="fas fa-circle-notch fa-spin"></i> Loading statistics...</div>';
            
            try {
                const statsResponse = await fetch(data.result_stats);
                if (!statsResponse.ok) throw new Error('Failed to fetch stats JSON');
                const statsJson = await statsResponse.json();
                
                // Format JSON with syntax highlighting
                const formattedJson = JSON.stringify(statsJson, null, 2)
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
                        let cls = 'number';
                        if (/^"/.test(match)) {
                            if (/:$/.test(match)) {
                                cls = 'key';
                                match = '<span style="color: var(--accent-blue);">' + match + '</span>';
                            } else {
                                cls = 'string';
                                match = '<span style="color: var(--accent-green);">' + match + '</span>';
                            }
                        } else if (/true|false/.test(match)) {
                            cls = 'boolean';
                            match = '<span style="color: var(--accent-purple);">' + match + '</span>';
                        } else if (/null/.test(match)) {
                            cls = 'null';
                            match = '<span style="color: var(--accent-red);">' + match + '</span>';
                        } else {
                            match = '<span style="color: #e6db74;">' + match + '</span>';
                        }
                        return match;
                    });
                
                resultStatsData.innerHTML = formattedJson;
                
                // Animate stats appearance
                resultStatsData.style.opacity = '0';
                setTimeout(() => {
                    resultStatsData.style.opacity = '1';
                }, 100);
                
            } catch (error) {
                console.error('Error fetching/parsing stats:', error);
                resultStatsData.textContent = 'Could not load statistics data.';
            }
        } else {
            statsResultDiv.style.display = 'none';
        }
    }

    function resetUI() {
        statusMessage.textContent = 'Upload a video to start.';
        statusMessage.style.color = 'var(--text-primary)';
        statusMessage.classList.remove('success-animation');
        progressBar.style.display = 'none';
        progressBar.value = 0;
        resultsArea.style.display = 'none';
        videoResultDiv.style.display = 'none';
        statsResultDiv.style.display = 'none';
        resultVideoPlayer.style.display = 'none';
        resultVideoLink.style.display = 'none';
        resultStatsLink.style.display = 'none';
        resultVideoPlayer.src = '';
        resultStatsData.textContent = '';
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
        currentTaskId = null;
    }
});