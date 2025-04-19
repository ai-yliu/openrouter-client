document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const fileInput = document.getElementById('file-input');
    const uploadButton = document.getElementById('upload-button');
    const prevButton = document.getElementById('prev-button');
    const nextButton = document.getElementById('next-button');
    const clearButton = document.getElementById('clear-button');
    const rawButton = document.getElementById('raw-button');
    const ner1Button = document.getElementById('ner1-button');
    const ner2Button = document.getElementById('ner2-button');

    const fileDisplayArea = document.getElementById('file-display-area');
    const outputDisplayArea = document.getElementById('output-display-area');
    const rawTextOutput = document.getElementById('raw-text-output');
    const ner1OutputDiv = document.getElementById('ner1-output');
    const ner2OutputDiv = document.getElementById('ner2-output');
    const ner1TableBody = document.querySelector('#ner1-table tbody');
    const ner2TableBody = document.querySelector('#ner2-table tbody');
    const statusArea = document.getElementById('status-area');
    const zoomInButton = document.getElementById('zoom-in-button');
    const zoomOutButton = document.getElementById('zoom-out-button');
    const zoomLevelDisplay = document.getElementById('zoom-level-display');

    // --- State ---
    let currentJobId = null;
    let currentUploadedFilename = null;
    let pollingInterval = null;
    let taskIds = {}; // {vlm: ..., ner1: ..., ner2: ..., comparison: ...}
    let taskStatus = {}; // {vlm: '', ner1: '', ner2: '', comparison: ''}
    let rawTextLoaded = false;
    let ner1Loaded = false;
    let ner2Loaded = false;
    let ner1Data = null;
    let ner2Data = null;
    let currentZoomLevel = 1.0; // Start at 100%

    // --- Functions ---

    function updateStatus(message, isError = false) {
        statusArea.innerHTML = `<p>${message}</p>`;
        statusArea.style.color = isError ? 'red' : '#555';
    }

    function clearDisplay() {
        fileDisplayArea.innerHTML = '<p>Upload an image or PDF file.</p>';
        rawTextOutput.textContent = '';
        ner1TableBody.innerHTML = '';
        ner2TableBody.innerHTML = '';
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.add('hidden');
        rawTextOutput.classList.remove('hidden'); // Show raw by default
        setActiveOutputButton(rawButton);
        updateStatus('Idle');
        currentJobId = null;
        currentUploadedFilename = null;
        taskIds = {};
        taskStatus = {};
        rawTextLoaded = false;
        ner1Loaded = false;
        ner2Loaded = false;
        ner1Data = null;
        ner2Data = null;
        fileInput.value = ''; // Clear file input
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
        // Reset zoom on clear
        currentZoomLevel = 1.0;
        applyZoom();
    }

    function setActiveOutputButton(activeButton) {
        [rawButton, ner1Button, ner2Button].forEach(button => {
            button.classList.remove('active');
        });
        activeButton.classList.add('active');
    }

    async function displayFile(vlmTaskId) {
        fileDisplayArea.innerHTML = '<p>Loading preview...</p>'; // Show loading state
        if (!vlmTaskId) {
            fileDisplayArea.innerHTML = '<p>Error: No VLM Task ID available for preview.</p>';
            return;
        }

        try {
            const response = await fetch(`/api/v1/tasks/${vlmTaskId}/input_content`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            fileDisplayArea.innerHTML = ''; // Clear loading state

            if (data.content_type === 'image_base64' && data.base64_data) {
                const img = document.createElement('img');
                img.alt = 'Uploaded Image';
                img.onerror = () => {
                    console.error(`Error rendering base64 image for task ${vlmTaskId}`);
                    fileDisplayArea.innerHTML = '<p>Error rendering image preview.</p>';
                };
                // Construct Data URL
                img.src = `data:${data.mime_type || 'image/jpeg'};base64,${data.base64_data}`;
                fileDisplayArea.appendChild(img);
            } else if (data.content_type === 'pdf_base64') {
                 // PDF preview from base64 is complex, show message or use embed if served differently
                 fileDisplayArea.innerHTML = '<p>PDF uploaded. Preview via base64 not implemented.</p>';
                 // If you were serving PDFs via /uploads/ route still:
                 // const embed = document.createElement('embed');
                 // embed.src = `/uploads/${currentUploadedFilename}`; // Requires filename state
                 // embed.type = 'application/pdf';
                 // embed.style.width = '100%';
                 // embed.style.height = '100%';
                 // fileDisplayArea.appendChild(embed);
            } else if (data.content_type === 'url') {
                 fileDisplayArea.innerHTML = `<p>Input was a URL: <a href="${data.url}" target="_blank">${data.url}</a></p>`;
            } else if (data.content_type === 'text') {
                 fileDisplayArea.innerHTML = `<p>Text file uploaded.</p><pre>${data.content ? data.content.substring(0, 500) + '...' : ''}</pre>`; // Show snippet
            }
             else {
                fileDisplayArea.innerHTML = `<p>Cannot display input type: ${data.content_type || 'unknown'}.</p>`;
            }

        } catch (error) {
            console.error('Error fetching/displaying input content:', error);
            fileDisplayArea.innerHTML = `<p>Error loading preview: ${error.message}</p>`;
        }
        // Apply current zoom level when displaying a new file
        applyZoom();
    }

    async function handleUpload() {
        const file = fileInput.files[0];
        if (!file) {
            updateStatus('Please select a file first.', true);
            return;
        }

        clearDisplay(); // Clear previous results before new upload
        updateStatus('Uploading file...');
        uploadButton.disabled = true; // Disable button during upload

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/v1/jobs', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP error! status: ${response.status}`);
            }

            currentJobId = result.job_id;
            currentUploadedFilename = result.uploaded_filename;
            updateStatus(`Processing started (Job ID: ${currentJobId}). Please wait...`);
            // We need the VLM task ID to display the file now.
            // Let's trigger the first status poll immediately to get it.
            // Display will happen once VLM task ID is known via polling.
            // displayFile(currentUploadedFilename); // Remove direct call

            // Start polling for status
            pollingInterval = setInterval(() => pollJobStatus(currentJobId), 2000);

        } catch (error) {
            console.error('Upload error:', error);
            updateStatus(`Upload failed: ${error.message}`, true);
            currentJobId = null;
            currentUploadedFilename = null;
        } finally {
             uploadButton.disabled = false; // Re-enable button
        }
    }

    async function pollJobStatus(jobId) {
        try {
            const response = await fetch(`/api/v1/jobs/${jobId}/status`);
            const data = await response.json();

            if (data.error) {
                updateStatus(`Error: ${data.error}`, true);
                clearInterval(pollingInterval);
                pollingInterval = null;
                return;
            }

            // Update task IDs and statuses
            if (data.tasks && Array.isArray(data.tasks)) {
                data.tasks.forEach(task => {
                    if (task.task_type === 'vlm_extraction') {
                        taskIds.vlm = task.task_id;
                        taskStatus.vlm = task.status;
                    } else if (task.task_type === 'ner_processing' && task.task_order === 2) {
                        taskIds.ner1 = task.task_id;
                        taskStatus.ner1 = task.status;
                    } else if (task.task_type === 'ner_processing' && task.task_order === 3) {
                        taskIds.ner2 = task.task_id;
                        taskStatus.ner2 = task.status;
                    } else if (task.task_type === 'json_comparison') {
                        taskIds.comparison = task.task_id;
                        taskStatus.comparison = task.status;
                    }
                });
            }

            // Update status area
            updateStatus(`Job Status: ${data.job_status || 'unknown'}`);

            // If VLM task ID is known and file not yet displayed, display it
            if (taskIds.vlm && !fileDisplayArea.querySelector('img, embed, pre, a')) {
                 displayFile(taskIds.vlm);
            }
            // If VLM is completed and raw text not loaded, fetch it
            if (taskStatus.vlm === 'completed' && !rawTextLoaded && taskIds.vlm) {
                await fetchRawText(taskIds.vlm);
                rawTextLoaded = true; // Mark as loaded after fetch attempt
            }
            // If NER1 is completed and not loaded, fetch it
            if (taskStatus.ner1 === 'completed' && !ner1Loaded && taskIds.ner1) {
                await fetchNER1(taskIds.ner1);
                ner1Loaded = true;
            }
            // If NER2 is completed and not loaded, fetch it
            if (taskStatus.ner2 === 'completed' && !ner2Loaded && taskIds.ner2) {
                await fetchNER2(taskIds.ner2);
                ner2Loaded = true;
            }

            // Stop polling if job is completed or failed
            if (data.job_status === 'completed' || data.job_status === 'failed') {
                clearInterval(pollingInterval);
                pollingInterval = null;
                updateStatus(`Job ${data.job_status}.`);
            }

        } catch (error) {
            updateStatus(`Polling error: ${error.message}`, true);
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }

    async function fetchRawText(taskId) {
        try {
            const response = await fetch(`/api/v1/tasks/${taskId}/output`);
            const data = await response.json();
            if (data.output_text) {
                rawTextOutput.textContent = data.output_text;
            } else {
                rawTextOutput.textContent = '[No raw text available]';
            }
        } catch (error) {
            rawTextOutput.textContent = `[Error fetching raw text: ${error.message}]`;
        }
    }

    async function fetchNER1(taskId) {
        try {
            const response = await fetch(`/api/v1/tasks/${taskId}/output`);
            const data = await response.json();
            if (data.output_json) {
                ner1Data = data.output_json;
                renderNERTable(ner1TableBody, ner1Data);
            } else {
                ner1TableBody.innerHTML = '<tr><td colspan="3">No NER 1 data available</td></tr>';
            }
        } catch (error) {
            ner1TableBody.innerHTML = `<tr><td colspan="3">Error: ${error.message}</td></tr>`;
        }
    }

    async function fetchNER2(taskId) {
        try {
            const response = await fetch(`/api/v1/tasks/${taskId}/output`);
            const data = await response.json();
            if (data.output_json) {
                ner2Data = data.output_json;
                renderNERTable(ner2TableBody, ner2Data);
            } else {
                ner2TableBody.innerHTML = '<tr><td colspan="3">No NER 2 data available</td></tr>';
            }
        } catch (error) {
            ner2TableBody.innerHTML = `<tr><td colspan="3">Error: ${error.message}</td></tr>`;
        }
    }

    function renderNERTable(tableBody, nerApiResponse) {
        tableBody.innerHTML = ''; // Clear previous rows
        let entities = null;

        // --- Safely extract the entities array ---
        try {
            // Check if the API response itself is the content (less likely now)
            if (nerApiResponse && nerApiResponse.entities && Array.isArray(nerApiResponse.entities)) {
                 entities = nerApiResponse.entities;
            }
            // Check standard structure: choices -> message -> content -> entities
            else if (nerApiResponse && nerApiResponse.choices && nerApiResponse.choices[0] &&
                     nerApiResponse.choices[0].message && nerApiResponse.choices[0].message.content) {

                let content = nerApiResponse.choices[0].message.content;
                // Check if content is a string needing parsing
                if (typeof content === 'string') {
                    try {
                        content = JSON.parse(content);
                    } catch (e) {
                        console.error("Failed to parse NER content string:", e);
                        tableBody.innerHTML = `<tr><td colspan="3">Error: Could not parse NER content.</td></tr>`;
                        return;
                    }
                }
                // Now check for entities within the parsed content
                if (content && content.entities && Array.isArray(content.entities)) {
                    entities = content.entities;
                }
            }
        } catch (e) {
            console.error("Error accessing entities in NER response:", e);
            tableBody.innerHTML = `<tr><td colspan="3">Error processing NER response structure.</td></tr>`;
            return;
        }
        // --- Render the table rows ---
        if (entities && entities.length > 0) {
            entities.forEach(entity => {
                // Use .get() or check property existence for safety if schema might vary
                const name = entity.entity_name || '[N/A]';
                const value = entity.entity_value || '[N/A]';
                const confidence = entity.confidence !== undefined ? entity.confidence : '[N/A]'; // Handle potential 0 confidence

                tableBody.innerHTML += `<tr>
                    <td>${escapeHtml(name)}</td>
                    <td>${escapeHtml(value)}</td>
                    <td>${escapeHtml(String(confidence))}</td>
                </tr>`;
            });
        } else if (entities) { // It's an empty array
             tableBody.innerHTML = '<tr><td colspan="3">No entities found.</td></tr>';
        }
         else { // Entities array not found in response structure
            tableBody.innerHTML = '<tr><td colspan="3">Could not find entities in the response.</td></tr>';
        }
    }

    // Helper to prevent basic HTML injection
    function escapeHtml(unsafe) {
        if (unsafe === null || unsafe === undefined) return '';
        return String(unsafe)
             .replace(/&/g, "&")
             .replace(/</g, "<")
             .replace(/>/g, ">")
             .replace(/"/g, '"') // Correctly quote the replacement string
             .replace(/'/g, '&#039;'); // Correctly quote the replacement string
    }

    // --- Event Listeners ---
    uploadButton.addEventListener('click', handleUpload);
    clearButton.addEventListener('click', clearDisplay);

    rawButton.addEventListener('click', () => {
        setActiveOutputButton(rawButton);
        rawTextOutput.classList.remove('hidden');
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.add('hidden');
        updateStatus('Displaying Raw Text');
        if (taskIds.vlm && !rawTextLoaded) fetchRawText(taskIds.vlm);
    });

    ner1Button.addEventListener('click', () => {
        setActiveOutputButton(ner1Button);
        rawTextOutput.classList.add('hidden');
        ner1OutputDiv.classList.remove('hidden');
        ner2OutputDiv.classList.add('hidden');
        updateStatus('Displaying NER 1 Results');
        if (taskIds.ner1 && !ner1Loaded) fetchNER1(taskIds.ner1);
    });

     ner2Button.addEventListener('click', () => {
        setActiveOutputButton(ner2Button);
        rawTextOutput.classList.add('hidden');
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.remove('hidden');
        updateStatus('Displaying NER 2 Results');
        if (taskIds.ner2 && !ner2Loaded) fetchNER2(taskIds.ner2);
    });

    function applyZoom() {
        const displayElement = fileDisplayArea.querySelector('img, embed'); // Target image or embed
        if (displayElement) {
            displayElement.style.transformOrigin = 'top left'; // Zoom from top-left
            displayElement.style.transform = `scale(${currentZoomLevel})`;
        }
        if (zoomLevelDisplay) {
            zoomLevelDisplay.textContent = `${Math.round(currentZoomLevel * 100)}%`;
        }
    }

    function zoomIn() {
        currentZoomLevel += 0.1;
        // Optional: Add max zoom limit
        // if (currentZoomLevel > 3.0) currentZoomLevel = 3.0;
        applyZoom();
    }

    function zoomOut() {
        currentZoomLevel -= 0.1;
        // Optional: Add min zoom limit
        if (currentZoomLevel < 0.1) currentZoomLevel = 0.1;
        applyZoom();
    }

    // --- Event Listeners ---
    uploadButton.addEventListener('click', handleUpload);
    clearButton.addEventListener('click', clearDisplay);

    rawButton.addEventListener('click', () => {
        setActiveOutputButton(rawButton);
        rawTextOutput.classList.remove('hidden');
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.add('hidden');
        updateStatus('Displaying Raw Text');
        if (taskIds.vlm && !rawTextLoaded) fetchRawText(taskIds.vlm);
    });

    ner1Button.addEventListener('click', () => {
        setActiveOutputButton(ner1Button);
        rawTextOutput.classList.add('hidden');
        ner1OutputDiv.classList.remove('hidden');
        ner2OutputDiv.classList.add('hidden');
        updateStatus('Displaying NER 1 Results');
        if (taskIds.ner1 && !ner1Loaded) fetchNER1(taskIds.ner1);
    });

     ner2Button.addEventListener('click', () => {
        setActiveOutputButton(ner2Button);
        rawTextOutput.classList.add('hidden');
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.remove('hidden');
        updateStatus('Displaying NER 2 Results');
        if (taskIds.ner2 && !ner2Loaded) fetchNER2(taskIds.ner2);
    });

    // Zoom button listeners
    zoomInButton.addEventListener('click', zoomIn);
    zoomOutButton.addEventListener('click', zoomOut);


    // --- Initial Setup ---
    clearDisplay(); // Initialize the view

}); // End DOMContentLoaded