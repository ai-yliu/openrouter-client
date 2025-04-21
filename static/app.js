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
    const compareButton = document.getElementById('compare-button'); // Added
    const comparisonOutputDiv = document.getElementById('comparison-output'); // Added
    const comparisonTableBody = document.querySelector('#comparison-table tbody'); // Added
    const reviewButton = document.getElementById('review-button'); // Added for Review
    const reviewOutputDiv = document.getElementById('review-output'); // Added for Review
    const reviewTableBody = document.querySelector('#review-table tbody'); // Added for Review

    // --- State ---
    let currentJobId = null;
    let currentUploadedFilename = null;
    let pollingInterval = null;
    let taskIds = {}; // {vlm: ..., ner1: ..., ner2: ..., comparison: ..., review: ...} // Added review
    let taskStatus = {}; // {vlm: '', ner1: '', ner2: '', comparison: '', review: ''} // Added review
    let rawTextLoaded = false;
    let ner1Loaded = false;
    let ner2Loaded = false;
    let ner1Data = null;
    let ner2Data = null;
    let comparisonData = null; // Added
    let comparisonLoaded = false; // Added
    let reviewData = null; // Added for Review
    let reviewLoaded = false; // Added for Review
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
        comparisonTableBody.innerHTML = ''; // Added
        reviewTableBody.innerHTML = ''; // Added for Review
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.add('hidden');
        comparisonOutputDiv.classList.add('hidden'); // Added
        reviewOutputDiv.classList.add('hidden'); // Added for Review
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
        comparisonLoaded = false; // Added
        reviewLoaded = false; // Added for Review
        ner1Data = null;
        ner2Data = null;
        comparisonData = null; // Added
        reviewData = null; // Added for Review
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
        [rawButton, ner1Button, ner2Button, compareButton, reviewButton].forEach(button => {
            button.classList.remove('active');
        });
        if (activeButton) {
            activeButton.classList.add('active');
        }
    }

    // Helper function to manage visibility of output sections
    function showOutputSection(sectionToShow) {
        // Hide all sections first
        rawTextOutput.classList.add('hidden');
        ner1OutputDiv.classList.add('hidden');
        ner2OutputDiv.classList.add('hidden');
        comparisonOutputDiv.classList.add('hidden');
        reviewOutputDiv.classList.add('hidden');

        // Show the requested section
        if (sectionToShow) {
            sectionToShow.classList.remove('hidden');
        }
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
                // Create a wrapper div for zooming
                const wrapper = document.createElement('div');
                wrapper.classList.add('image-zoom-wrapper'); // Add a class for targeting

                const img = document.createElement('img');
                img.alt = 'Uploaded Image';
                img.classList.add('fit-container'); // Image fits wrapper width
                img.onerror = () => {
                    console.error(`Error rendering base64 image for task ${vlmTaskId}`);
                    wrapper.innerHTML = '<p>Error rendering image preview.</p>'; // Put error in wrapper
                };
                // Construct Data URL
                img.src = `data:${data.mime_type || 'image/jpeg'};base64,${data.base64_data}`;

                // Append image to wrapper, then wrapper to display area
                wrapper.appendChild(img);
                fileDisplayArea.appendChild(wrapper);

            } else if (data.content_type === 'pdf_base64') {
                 // PDF preview from base64 is complex, show message or use embed if served differently
                 // If implementing PDF preview, apply similar wrapper strategy
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
                    } else if (task.task_type === 'vlm_review') { // Added check for review task
                        taskIds.review = task.task_id;
                        taskStatus.review = task.status;
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
        // nerApiResponse is the full API response object stored in the DB
        tableBody.innerHTML = ''; // Clear previous rows
        let entities = null;

        // --- Safely extract the entities array from the API response structure ---
        try {
            let content = nerApiResponse?.choices?.[0]?.message?.content; // Safely access nested properties

            if (content) {
                // Check if content is a string needing parsing (as expected from API)
                if (typeof content === 'string') {
                    try {
                        content = JSON.parse(content);
                    } catch (e) {
                        console.error("Failed to parse NER content string:", e);
                        tableBody.innerHTML = `<tr><td colspan="3">Error: Could not parse NER content string.</td></tr>`;
                        return;
                    }
                }
                // Now check for the 'entities' array within the parsed content object
                if (content && content.entities && Array.isArray(content.entities)) {
                    entities = content.entities;
                } else {
                     console.warn("Parsed NER content does not contain an 'entities' array:", content);
                }
            } else {
                 console.warn("Could not find 'content' in NER API response structure:", nerApiResponse);
            }
        } catch (e) {
            console.error("Error processing NER API response structure:", e);
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

    async function fetchComparisonResults(jobId) {
        if (!jobId) return;
        updateStatus('Fetching comparison results...');
        try {
            // Assuming Option B (pre-computed result stored in DB)
            // Need the comparison task ID first
            const comparisonTaskId = taskIds.comparison; // Get from polling
            if (!comparisonTaskId) {
                 // Maybe the comparison task hasn't been created yet or polling missed it
                 // We could try fetching based on job_id directly if API supports it
                 // Or just wait for next poll cycle. For now, show message.
                 updateStatus('Waiting for comparison task to complete...');
                 // Alternatively, call the API endpoint that computes on demand if using Option A
                 // const response = await fetch(`/api/v1/jobs/${jobId}/comparison`);
                 return; // Exit for now, rely on polling to eventually fetch
            }

            const response = await fetch(`/api/v1/tasks/${comparisonTaskId}/output`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || `HTTP error! status: ${response.status}`);
            }

            if (data.output_comparison_json) {
                comparisonData = data.output_comparison_json; // Store the result
                renderComparisonTable(comparisonTableBody, comparisonData);
                comparisonLoaded = true;
                updateStatus('Comparison results loaded.');
            } else {
                comparisonTableBody.innerHTML = '<tr><td colspan="4">No comparison data available.</td></tr>';
                updateStatus('No comparison data found.');
            }
        } catch (error) {
            console.error("Error fetching comparison results:", error);
            comparisonTableBody.innerHTML = `<tr><td colspan="4">Error: ${error.message}</td></tr>`;
            updateStatus(`Error fetching comparison: ${error.message}`, true);
        }
    }

    function renderComparisonTable(tableBody, comparisonResult) {
        tableBody.innerHTML = ''; // Clear previous rows
        let entities = null;
        try {
             // Comparison result structure is expected to be {"entities": [...]}
             if (comparisonResult && comparisonResult.entities && Array.isArray(comparisonResult.entities)) {
                 entities = comparisonResult.entities;
             }
        } catch(e) {
             console.error("Error accessing entities in comparison result:", e);
             tableBody.innerHTML = `<tr><td colspan="4">Error processing comparison result structure.</td></tr>`;
             return;
        }

        if (entities && entities.length > 0) {
            entities.forEach(entity => {
                const name = entity.entity_name || '[N/A]';
                const value = entity.entity_value || '[N/A]';
                const comparison = entity.comparison || '[N/A]';
                const confidence = entity.confidence !== undefined ? entity.confidence : '[N/A]';

                tableBody.innerHTML += `<tr>
                    <td>${escapeHtml(name)}</td>
                    <td>${escapeHtml(value)}</td>
                    <td>${escapeHtml(comparison)}</td>
                    <td>${escapeHtml(String(confidence))}</td>
                </tr>`;
            });
        } else {
            tableBody.innerHTML = '<tr><td colspan="4">No comparison results found.</td></tr>';
        }
    }

    // --- Review Functions (New) ---

    async function fetchAndRenderReviewData(jobId) {
        if (!jobId || !taskIds.comparison || !taskIds.review) {
            updateStatus('Cannot fetch review data: Missing comparison or review task ID.', true);
            return;
        }
        updateStatus('Fetching comparison and review results...');
        reviewTableBody.innerHTML = '<tr><td colspan="5">Loading review data...</td></tr>'; // Update colspan

        try {
            // Fetch both comparison and review outputs concurrently
            const [compResponse, reviewResponse] = await Promise.all([
                fetch(`/api/v1/tasks/${taskIds.comparison}/output`),
                fetch(`/api/v1/tasks/${taskIds.review}/output`)
            ]);

            // Check both responses
            if (!compResponse.ok) {
                const compError = await compResponse.json();
                throw new Error(`Comparison fetch failed: ${compError.error || compResponse.statusText}`);
            }
            if (!reviewResponse.ok) {
                const reviewError = await reviewResponse.json();
                throw new Error(`Review fetch failed: ${reviewError.error || reviewResponse.statusText}`);
            }

            const compData = await compResponse.json();
            const revData = await reviewResponse.json();

            // Store the fetched data
            comparisonData = compData.output_comparison_json; // Store comparison if needed elsewhere too
            reviewData = revData.output_review_json; // Store review data

            if (!comparisonData || !reviewData) {
                 throw new Error('Missing comparison or review data in API response.');
            }

            renderReviewTable(comparisonData, reviewData); // Pass the actual data objects
            reviewLoaded = true; // Mark as loaded
            updateStatus('Review results loaded.');

        } catch (error) {
            console.error("Error fetching or rendering review data:", error);
            reviewTableBody.innerHTML = `<tr><td colspan="5">Error loading review data: ${error.message}</td></tr>`; // Update colspan
            updateStatus(`Error loading review data: ${error.message}`, true);
            reviewLoaded = false; // Ensure it's marked as not loaded on error
        }
    }

    function renderReviewTable(compResult, reviewResult) {
        reviewTableBody.innerHTML = ''; // Clear previous rows

        let compEntities = null;
        // Map to store reviewed status: key = "name::value" (normalized), value = "yes"/"no"
        let reviewedStatusMap = new Map();

        // Safely extract comparison entities
        try {
            if (compResult && compResult.entities && Array.isArray(compResult.entities)) {
                compEntities = compResult.entities;
            }
        } catch (e) {
            console.error("Error accessing entities in comparison result:", e);
            reviewTableBody.innerHTML = `<tr><td colspan="5">Error processing comparison result structure.</td></tr>`;
            return;
        }

        // Safely extract and map reviewed status from the review task result
        // Assumes structure like {"entities": [{"name": "...", "value": "...", "reviewed": "yes/no"}, ...]}
        // Handles potential nesting within choices/message/content
        try {
            let reviewEntities = null;
            if (reviewResult && reviewResult.entities && Array.isArray(reviewResult.entities)) {
                reviewEntities = reviewResult.entities;
            } else if (reviewResult?.choices?.[0]?.message?.content) {
                 let content = reviewResult.choices[0].message.content;
                 if (typeof content === 'string') {
                     try { content = JSON.parse(content); } catch (e) { /* ignore parse error */ }
                 }
                 if (content && content.entities && Array.isArray(content.entities)) {
                    reviewEntities = content.entities;
                 }
            }

            if (reviewEntities) {
                reviewEntities.forEach(entity => {
                    const name = entity.entity_name;
                    const value = entity.entity_value;
                    const reviewed = entity.reviewed; // Get the actual status ("yes" or "no")

                    if (name && value && reviewed !== undefined) {
                        // Normalize key: lowercase and trim whitespace
                        const key = `${String(name).trim().toLowerCase()}::${String(value).trim().toLowerCase()}`;
                        // Store the actual status, defaulting to "no" if value is unexpected
                        reviewedStatusMap.set(key, String(reviewed).toLowerCase() === 'yes' ? 'Yes' : 'No');
                    }
                });
            } else {
                 console.warn("Could not find 'entities' array in review VLM output:", reviewResult);
            }
        } catch (e) {
            console.error("Error processing review result structure:", e);
            // Proceed without reviewed status if parsing fails
        }


        if (compEntities && compEntities.length > 0) {
            compEntities.forEach(entity => {
                const name = entity.entity_name || '[N/A]';
                const value = entity.entity_value || '[N/A]';
                const comparison = entity.comparison || entity.match || '[N/A]'; // Handle both keys
                const confidence = entity.confidence !== undefined ? entity.confidence : '[N/A]';

                let reviewedStatus = 'No'; // Default status

                // Check if the comparison status is 'match'
                if (String(comparison).toLowerCase() === 'match') {
                    reviewedStatus = 'N/A'; // Set to N/A for matched items
                } else {
                    // Only look up in the map if it's not a match
                    const reviewKey = `${String(name).trim().toLowerCase()}::${String(value).trim().toLowerCase()}`;
                    reviewedStatus = reviewedStatusMap.get(reviewKey) || 'No'; // Get status from map, default to 'No'
                }


                reviewTableBody.innerHTML += `<tr>
                    <td>${escapeHtml(name)}</td>
                    <td>${escapeHtml(value)}</td>
                    <td>${escapeHtml(comparison)}</td>
                    <td>${escapeHtml(String(confidence))}</td>
                    <td>${escapeHtml(reviewedStatus)}</td>
                </tr>`;
            });
        } else {
            reviewTableBody.innerHTML = '<tr><td colspan="5">No comparison results found to review.</td></tr>';
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
        showOutputSection(rawTextOutput); // Use helper
        updateStatus('Displaying Raw Text');
        if (taskIds.vlm && !rawTextLoaded) fetchRawText(taskIds.vlm);
    });

    ner1Button.addEventListener('click', () => {
        setActiveOutputButton(ner1Button);
        showOutputSection(ner1OutputDiv); // Use helper
        updateStatus('Displaying NER 1 Results');
        if (taskIds.ner1 && !ner1Loaded) fetchNER1(taskIds.ner1);
    });

     ner2Button.addEventListener('click', () => {
        setActiveOutputButton(ner2Button);
        showOutputSection(ner2OutputDiv); // Use helper
        updateStatus('Displaying NER 2 Results');
        if (taskIds.ner2 && !ner2Loaded) fetchNER2(taskIds.ner2);
    });

    compareButton.addEventListener('click', () => {
        setActiveOutputButton(compareButton);
        showOutputSection(comparisonOutputDiv); // Use helper
        updateStatus('Displaying Comparison Results');
        // Fetch comparison results if not already loaded and job is done/comparison task exists
        if (currentJobId && !comparisonLoaded && taskIds.comparison) {
             fetchComparisonResults(currentJobId); // Pass job ID, fetch function will get task ID
        } else if (!taskIds.comparison) {
            updateStatus('Comparison task not yet available or completed.');
        }
        // Removed redundant fetchNER2 call from here
    });

    // Removed duplicated compareButton listener

    reviewButton.addEventListener('click', () => {
        setActiveOutputButton(reviewButton);
        showOutputSection(reviewOutputDiv); // Use helper
        updateStatus('Displaying Review Results');

        // Fetch comparison AND review results if not already loaded and tasks are completed
        if (currentJobId && !reviewLoaded && taskIds.comparison && taskIds.review && taskStatus.comparison === 'completed' && taskStatus.review === 'completed') {
             fetchAndRenderReviewData(currentJobId); // Call new function
        } else if (!taskIds.comparison || !taskIds.review || taskStatus.comparison !== 'completed' || taskStatus.review !== 'completed') { // Check statuses here too
            updateStatus('Comparison or Review task not yet available or completed.');
            reviewTableBody.innerHTML = '<tr><td colspan="5">Comparison and Review tasks must complete first.</td></tr>'; // Update colspan
        } else if (reviewLoaded) {
             // Data is loaded, just ensure the section is visible (already handled by showOutputSection)
             updateStatus('Displaying previously loaded Review Results');
        }
    });


    function applyZoom() {
        // Target the wrapper div for scaling
        const zoomWrapper = fileDisplayArea.querySelector('.image-zoom-wrapper');
        if (zoomWrapper) {
            zoomWrapper.style.transformOrigin = 'top left'; // Zoom from top-left
            zoomWrapper.style.transform = `scale(${currentZoomLevel})`;
            // Note: The image inside the wrapper retains its .fit-container style (width: 100%)
        }
        // Also handle potential PDF embeds if implemented similarly
        const pdfEmbed = fileDisplayArea.querySelector('embed'); // Example
         if (pdfEmbed) {
             // Apply zoom directly or via wrapper depending on implementation
             pdfEmbed.style.transformOrigin = 'top left';
             pdfEmbed.style.transform = `scale(${currentZoomLevel})`;
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

    // Removed duplicated tab button listeners (raw, ner1, ner2)

    // Zoom button listeners
    zoomInButton.addEventListener('click', zoomIn);
    zoomOutButton.addEventListener('click', zoomOut);


    // --- Initial Setup ---
    clearDisplay(); // Initialize the view

}); // End DOMContentLoaded