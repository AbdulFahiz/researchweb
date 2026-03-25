document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'http://localhost:8000';

    // --- DOM Elements ---
    const modelDropdown = document.getElementById('model-dropdown');
    const topicInput = document.getElementById('topic-input');
    const researchButton = document.getElementById('research-button');
    const stopButton = document.getElementById('stop-button');
    const depthSlider = document.getElementById('depth-slider');
    const agentLog = document.getElementById('agent-log');
    const reportOutput = document.getElementById('report-output');
    const copyButton = document.getElementById('copy-button');
    const sourcesToggle = document.getElementById('sources-toggle');
    const sourcesContent = document.getElementById('sources-content');
    const errorBanner = document.getElementById('error-banner');
    const historyList = document.getElementById('history-list');
    const clearHistoryButton = document.getElementById('clear-history-button');

    let abortController = null;
    let currentReport = '';
    let currentSources = [];
    let reportRenderTimer = null;

    const updateReportDisplay = () => {
        // Batch render: only update DOM every 200ms max
        if (reportRenderTimer) clearTimeout(reportRenderTimer);
        reportRenderTimer = setTimeout(() => {
            if (currentReport) {
                reportOutput.innerHTML = marked.parse(currentReport) + '<span class="blinking-cursor"></span>';
            }
        }, 200);
    };

    // --- State Management ---
    const setBusyState = (isBusy) => {
        topicInput.disabled = isBusy;
        researchButton.disabled = isBusy;
        modelDropdown.disabled = isBusy;
        depthSlider.disabled = isBusy;
        if (isBusy) {
            researchButton.classList.add('hidden');
            stopButton.classList.remove('hidden');
        } else {
            researchButton.classList.remove('hidden');
            stopButton.classList.add('hidden');
            abortController = null;
        }
    };

    // --- API Calls ---
    const fetchModels = async () => {
        try {
            const response = await fetch(`${API_URL}/models`);
            if (!response.ok) throw new Error('Failed to fetch models');
            const data = await response.json();
            modelDropdown.innerHTML = data.models
                .map(model => `<option value="${model}">${model}</option>`)
                .join('');
        } catch (error) {
            showError('Could not load models from Ollama. Using fallback list.');
            console.error(error);
            modelDropdown.innerHTML = ['llama3.2', 'mistral', 'deepseek-r1']
                .map(model => `<option value="${model}">${model}</option>`)
                .join('');
        }
    };

    const startResearch = async () => {
        const topic = topicInput.value.trim();
        const model = modelDropdown.value;
        const depth = parseInt(depthSlider.value, 10);

        if (!topic) {
            showError('Please enter a research topic.');
            return;
        }

        setBusyState(true);
        clearUI();
        currentReport = '';
        currentSources = [];
        abortController = new AbortController();

        try {
            const response = await fetch(`${API_URL}/research`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, model, depth }),
                signal: abortController.signal,
            });

            if (!response.body) return;

            const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const lines = value.split('\n\n');
                for (const line of lines) {
                    if (line.startsWith('data:')) {
                        const data = line.substring(5);
                        try {
                            const event = JSON.parse(data);
                            handleEvent(event);
                        } catch (e) {
                            // Ignore empty or malformed JSON
                        }
                    }
                }
            }
        } catch (error) {
            if (error.name !== 'AbortError') {
                showError(`Research failed: ${error.message}`);
            }
        } finally {
            setBusyState(false);
        }
    };

    // --- Event Handling ---
    const handleEvent = (event) => {
        const { type, data } = event;
        switch (type) {
            case 'status':
                const phase = data.phase || 'working';
                let icon = '';
                switch(phase) {
                    case 'planning': icon = '🗺️'; break;
                    case 'searching': icon = '🔍'; break;
                    case 'reflecting': icon = '🤔'; break;
                    case 'writing': icon = '✍️'; break;
                    default: icon = '⏳';
                }
                addLogEntry('status', `<span>${icon} ${data.content}</span> <span class="thinking-dot"></span>`);
                break;
            case 'plan':
                addLogEntry('plan', `<h4>Research Plan:</h4><ul>${data.content.map(q => `<li>${q}</li>`).join('')}</ul>`);
                break;
            case 'search_results':
                const resultsHtml = data.results.map((res, i) => `
                    <div class="result-card">
                        <strong>[${data.source_nums[i]}] <a href="${res.url}" target="_blank">${res.title}</a></strong>
                        <p>${res.snippet}</p>
                    </div>`).join('');
                addLogEntry('search-result', `<details><summary>Results for "${data.query}"</summary>${resultsHtml}</details>`);
                break;
            case 'finding':
                addLogEntry('finding', `<h4>Finding for "${data.question}"</h4><p>${data.content}</p>`);
                break;
            case 'wiki':
                addLogEntry('wiki', `<h4>📖 Wikipedia Summary</h4><p>${data.content}</p>`);
                break;
            case 'reflect':
                const reflection = data.content;
                const sufficient = reflection.sufficient ? 'Sufficient' : 'Not Sufficient';
                const missing = reflection.missing && reflection.missing.length > 0 ? `Missing: ${reflection.missing.join(', ')}` : '';
                addLogEntry('reflect', `<h4>Reflection</h4><p><strong>Status:</strong> ${sufficient}<br/>${missing}</p>`);
                break;
            case 'report_start':
                reportOutput.innerHTML = '<span class="blinking-cursor"></span>';
                break;
            case 'report_token':
                currentReport += data.content;
                updateReportDisplay();
                break;
            case 'done':
                // Flush the final render
                if (reportRenderTimer) clearTimeout(reportRenderTimer);
                reportOutput.innerHTML = marked.parse(currentReport);
                reportOutput.querySelector('.blinking-cursor')?.remove();
                copyButton.classList.remove('hidden');
                currentSources = data.sources;
                renderSources();
                saveToHistory(topicInput.value.trim(), currentReport, currentSources);
                loadHistory();
                showToast('Research complete!');
                break;
            case 'error':
                showError(data.content);
                setBusyState(false);
                break;
        }
        scrollToBottom(agentLog);
    };

    // --- UI Updates ---
    const clearUI = () => {
        agentLog.innerHTML = '';
        reportOutput.innerHTML = '<div class="placeholder">Your report will appear here...</div>';
        sourcesContent.innerHTML = '';
        sourcesContent.classList.remove('visible');
        sourcesToggle.textContent = 'SOURCES ▼';
        copyButton.classList.add('hidden');
        hideError();
    };

    const addLogEntry = (type, content) => {
        const item = document.createElement('div');
        item.className = `log-item ${type}`;
        item.innerHTML = content;
        agentLog.appendChild(item);
        // Auto-scroll to newest entry
        setTimeout(() => agentLog.scrollTop = agentLog.scrollHeight, 0);
    };

    const renderSources = () => {
        if (currentSources.length === 0) return;
        const sourcesHtml = `<ol>${currentSources.map(src => `<li><a href="${src.url}" target="_blank">${src.title}</a></li>`).join('')}</ol>`;
        sourcesContent.innerHTML = sourcesHtml;
    };

    const showError = (message) => {
        errorBanner.textContent = message;
        errorBanner.classList.remove('hidden');
        setTimeout(hideError, 5000);
    };

    const hideError = () => errorBanner.classList.add('hidden');

    const showToast = (message) => {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.remove();
        }, 3000);
        // Simple toast style
        const style = document.createElement('style');
        style.innerHTML = `
        .toast {
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background-color: var(--accent-color); color: var(--bg-color);
            padding: 10px 20px; border-radius: 6px; z-index: 1001;
            animation: fadeInSlideUp 0.5s ease;
        }`;
        document.head.appendChild(style);
    };

    const scrollToBottom = (element) => {
        element.scrollTop = element.scrollHeight;
    };

    // --- Local Storage History ---
    const getHistory = () => JSON.parse(localStorage.getItem('researchHistory') || '[]');

    const saveToHistory = (topic, report, sources) => {
        let history = getHistory();
        const newEntry = {
            topic,
            report,
            sources,
            timestamp: new Date().toISOString(),
        };
        history.unshift(newEntry);
        history = history.slice(0, 5); // Keep last 5
        localStorage.setItem('researchHistory', JSON.stringify(history));
    };

    const loadHistory = () => {
        const history = getHistory();
        historyList.innerHTML = history.map((item, index) =>
            `<div class="history-item" data-index="${index}">
                ${item.topic} - <small>${new Date(item.timestamp).toLocaleDateString()}</small>
            </div>`
        ).join('');
    };

    const reloadFromHistory = (index) => {
        const history = getHistory();
        const item = history[index];
        if (item) {
            clearUI();
            topicInput.value = item.topic;
            currentReport = item.report;
            currentSources = item.sources;
            reportOutput.innerHTML = marked.parse(currentReport);

            renderSources();
            copyButton.classList.remove('hidden');
            addLogEntry('status', 'Loaded from history.');
        }
    };

    const clearHistory = () => {
        localStorage.removeItem('researchHistory');
        loadHistory();
    };

    // --- Event Listeners ---
    researchButton.addEventListener('click', startResearch);
    stopButton.addEventListener('click', () => {
        if (abortController) {
            abortController.abort();
            showToast('Research stopped.');
        }
    });

    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(currentReport).then(() => {
            copyButton.textContent = 'Copied ✓';
            setTimeout(() => { copyButton.textContent = 'Copy 📋'; }, 2000);
        });
    });

    sourcesToggle.addEventListener('click', () => {
        const isVisible = sourcesContent.classList.toggle('visible');
        sourcesToggle.textContent = isVisible ? 'SOURCES ▲' : 'SOURCES ▼';
        if (isVisible) {
            sourcesContent.style.maxHeight = sourcesContent.scrollHeight + "px";
        } else {
            sourcesContent.style.maxHeight = "0";
        }
    });
    
    historyList.addEventListener('click', (e) => {
        if (e.target.classList.contains('history-item')) {
            const index = e.target.dataset.index;
            reloadFromHistory(index);
        }
    });

    clearHistoryButton.addEventListener('click', clearHistory);

    // --- Initialization ---
    fetchModels();
    loadHistory();
});
