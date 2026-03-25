# 🔬 AI Research Agent

This is a local AI-powered research agent that takes a topic, autonomously plans sub-questions, searches the web, scrapes pages, reflects on completeness, and streams a full markdown research report. The entire process runs locally using Ollama and a FastAPI backend, with a pure HTML/JS/CSS frontend.

## Architecture Diagram

```
+--------------------------------+      +--------------------------------+
|         Frontend (Browser)     |      |         Backend (Python)       |
|    (localhost:3000)            |      |    (localhost:8000)            |
|                                |      |                                |
|  +--------------------------+  |      |  +--------------------------+  |
|  |        index.html        |  |      |  |         main.py          |  |
|  |        styles.css        |  |      |  |       (FastAPI App)      |  |
|  |         app.js           |  |      |  +--------------------------+  |
|  +--------------------------+  |      |               |                |
|               |                |      |  +--------------------------+  |
| (EventSource /fetch API)       |      |  |         agent.py         |  |
|               |                |      |  |      (ReAct Loop)        |  |
|               v                |      |  +--------------------------+  |
|  SSE Stream of JSON Events     |      |      /      |      \         |
|                                |      |     /       |       \        |
+-----------------|--------------+      |    v        v        v       |
                  |                     | +-------+ +-------+ +-------+  |
                  |                     | |tools.py | |ollama_| |       |  |
                  |                     | |(Search/ | |client | |       |  |
                  |                     | | Scrape) | | .py   | |       |  |
                  |                     | +-------+ +-------+ +-------+  |
                  |                     +-----------------|--------------+
                  |                                       |
                  | (HTTP API Calls)                      |
                  |                                       v
                  |                     +--------------------------------+
                  |                     |         Ollama Service         |
                  |                     |      (localhost:11434)         |
                  |                     |                                |
                  |                     |  +--------------------------+  |
                  |                     |  |   LLM (e.g., Llama 3.2)  |  |
                  |                     |  +--------------------------+  |
                  +-------------------->|                                |
                                        +--------------------------------+
```

## Prerequisites

1.  **Python 3.10+**: Ensure you have a modern version of Python installed.
2.  **Ollama**: The agent relies on a locally running Ollama instance.
    *   Download and install from [https://ollama.com](https://ollama.com).
    *   Ensure the Ollama application is **running** before starting the agent.
3.  **An Ollama Model**: You need at least one model pulled.
    *   Run `ollama pull llama3.2` (or another model like `mistral`).

## 🚀 Quick Start

1.  **Make the start script executable:**
    ```bash
    chmod +x start.sh
    ```

2.  **Run the script:**
    ```bash
    ./start.sh
    ```

3.  **Open the application:**
    *   Navigate to **http://localhost:3000** in your web browser.

The script will automatically check for Ollama, install Python dependencies into a virtual environment, and start both the backend and frontend servers.

## Manual Setup

If `start.sh` fails, you can run the application manually:

1.  **Start the Backend:**
    ```bash
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
    ```

2.  **Start the Frontend (in a new terminal):**
    ```bash
    cd frontend
    python3 -m http.server 3000
    ```

3.  **Open the App:**
    *   Navigate to **http://localhost:3000**.

## Troubleshooting

*   **Ollama Not Running**: If you see an error message saying "Ollama is not running," please start the Ollama desktop application and try again.
*   **CORS Errors**: The FastAPI backend is configured to allow all origins (`*`), so CORS errors should not be an issue. If you encounter them, ensure no browser extension is blocking requests.
*   **No Models Found**: If the model dropdown is empty or shows the fallback list, it means the app could not connect to the Ollama API at `http://localhost:11434/api/tags`.
    *   Verify Ollama is running.
    *   Check if you have pulled any models (`ollama list`).
*   **`start.sh` permission denied**: Run `chmod +x start.sh` to make the script executable.
*   **Address already in use**: If you get an error that port 8000 or 3000 is already in use, another application is using that port. You can either stop the other application or modify the ports in `start.sh` and `backend/main.py`.

## 🎯 Recent Improvements (Latest Session)

### Research Quality Enhancements
- **Enhanced System Prompts**: Better guidance for planning, searching, reflecting, and report writing
- **Parallel Web Scraping**: All search results are scraped concurrently for faster research
- **Intelligent Query Fallback**: If a search fails, the system automatically retries with simplified queries
- **Better Content Extraction**: Smart detection of main content areas for cleaner page scraping
- **Expanded Coverage**: Increased from 3 to 4 search results per query for better information gathering
- **Richer Context**: Page scraping captures up to 2000 characters per source (from 1500)

### Performance Optimizations
- **Search Result Caching**: Recent search queries are cached to prevent duplicate API calls and improve speed
- **Batched Rendering**: Frontend renders report updates every 200ms instead of per-token, preventing UI lag
- **Error Recovery**: Research continues gracefully even if individual sources fail

### UI/UX Improvements
- **Better Status Feedback**: Phase-specific emoji indicators (🔍 searching, 🤔 reflecting, ✏️ writing)
- **Enhanced Log Styling**: Better visual hierarchy with gradient backgrounds and color-coded item types
- **Auto-Scrolling**: Agent log automatically scrolls to show the latest activity
- **Improved Buttons**: Modern gradient styling with hover effects and visual feedback
- **Better Placeholder**: Informative empty state in the report area
- **Input Enhancements**: Better focus states and visual feedback for the research topic input

### Technical Improvements
- **Async Optimization**: Multiple concurrent operations for faster research cycles
- **Better Error Messages**: User-friendly error feedback instead of technical details
- **Code Organization**: Improved modularity and separation of concerns
- **Responsive Design**: Better support for various screen sizes

## 🔍 How It Works

1. **Plan**: The agent generates 4-5 specific sub-questions about your research topic
2. **Search**: For each question, it searches the web and scrapes the top 4 results
3. **Reflect**: The agent evaluates whether it has enough information to answer your question
4. **Report**: Finally, it synthesizes all findings into a comprehensive, well-structured markdown report

The entire process streams in real-time to your browser, so you can watch the research happen step-by-step.

## 📋 Features

- **Real-time Streaming**: Watch the research process unfold in real-time via Server-Sent Events
- **Local & Private**: Everything runs on your local machine; no data sent to external services
- **Multiple Models**: Support for any Ollama-compatible model (Llama, Mistral, DeepSeek, etc.)
- **Adjustable Depth**: Control research depth with a simple slider (Quick → Deep)
- **Source Citations**: Full list of sources used in the research
- **Copy to Clipboard**: Easy export of reports for use in documents
- **Research History**: Keeps track of your recent searches
