# Quick Optimization Recipes

These are ready-to-implement optimizations for the research-agent backend.

---

## 1. URL Deduplication with Set (5 min)

### Current Code Issue
```python
# Lines 62-65 in agent.py - O(n) lookup
if result['url'] not in [src['url'] for src in self.sources]:
    self.sources.append(result)
    source_nums.append(len(self.sources))
```

### Optimized Code
```python
# In __init__
def __init__(self, model: str, max_searches: int = 3):
    self.model = model
    self.max_searches = max_searches
    self.sources = []
    self.source_urls = set()  # ADD THIS
    self.findings = []

# In run() method, replace the URL check with:
if result['url'] not in self.source_urls:  # O(1) instead of O(n)
    self.sources.append(result)
    self.source_urls.add(result['url'])
    source_nums.append(len(self.sources))
else:
    source_nums.append([src['url'] for src in self.sources].index(result['url']) + 1)
```

### Speedup
- Negligible for typical size (15-25 sources)
- No risk, just cleaner code

---

## 2. Connection Pooling for Page Scraping (15 min)

### Current Code Issue
```python
# Lines 96-98 in tools.py - Creates new client for every scrape
async def scrape_page(url: str, max_chars: int = 2000) -> str:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        # ... scrape ...
```

### Problem
- Each asyncio.gather() call in agent.py line 68 creates 4 new clients
- No connection reuse, TCP handshake for each page
- ~5-10% overhead from connection setup

### Optimized Code

#### Option A: Pass Client to Function
```python
# In tools.py - modify signature
async def scrape_page(client: httpx.AsyncClient, url: str, max_chars: int = 2000) -> str:
    try:
        response = await client.get(url, timeout=15.0)
        # ... rest of function ...
    except httpx.HTTPStatusError as e:
        return f"Error: Page not found (Status {e.response.status_code})"
    except httpx.RequestError as e:
        return f"Error: Could not reach the page"
    except Exception as e:
        return f"Error: Failed to process page"

# In agent.py __init__:
self.client = None

# In agent.py, before search loop (line ~50):
self.client = httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15.0)

# In agent.py, update scrape call (line 68):
scrape_tasks = [scrape_page(self.client, result['url']) for result in search_results]

# At end of run() method (before return or in finally):
if self.client:
    await self.client.aclose()
```

#### Option B: Use Client Context Manager (Cleaner)
```python
# In agent.py run() method, wrap whole logic:

async def run(self, topic: str) -> AsyncGenerator[Dict[str, Any], None]:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15.0) as client:
        # Pass client to all functions that need it
        # ... rest of run() ...
```

### Speedup
- ~5-10% faster page scraping through connection reuse
- **WARNING**: Must properly close client to avoid resource leaks

---

## 3. Timeout Reduction with Smart Retry (20 min)

### Current Code Issue
```python
# tools.py line 99 - All pages get 15s timeout
response = await client.get(url, timeout=15.0)
```

### Optimized Code
```python
async def scrape_page(client: httpx.AsyncClient, url: str, max_chars: int = 2000) -> str:
    """
    Scrapes and cleanses the text content of a webpage for research quality.
    Tries fast timeout first (8s), then longer timeout (10s) once if needed.
    """
    try:
        # Fast attempt first
        response = await client.get(url, timeout=8.0)
        response.raise_for_status()
    except httpx.TimeoutException:
        # One retry with longer timeout
        try:
            response = await client.get(url, timeout=12.0)
            response.raise_for_status()
        except Exception as e:
            return f"Error: Page request timed out"
    except httpx.HTTPStatusError as e:
        return f"Error: Page not found (Status {e.response.status_code})"
    except Exception as e:
        return f"Error: Could not reach the page"

    # ... rest of existing code ...
```

### Timing Impact
- **Fast pages** (2-4s): Save 4-7s per page → ~16-28s for 4 pages
- **Slow pages** (8-15s): First timeout, then succeed → lose 8-12s
- **Broken pages**: Fail after 8s instead of 15s → save 7s
- **Net result**: ~2-5 seconds faster per question (40-100ms per page in best case)

### Considerations
- Some legitimate pages take 10-15s to respond
- Only do 1 retry to avoid excessive delay
- Could add timeout per-url in future (tracking slow hosts)

---

## 4. Simple Findings Cache (30 min)

### Current Code Issue
- Same LLM extraction happens if similar content from different sources
- Plan might have overlapping questions like "What's the history of X?" vs "Historical background of X?"

### Optimized Code

#### Add to agent.py:
```python
import hashlib

class ResearchAgent:
    def __init__(self, model: str, max_searches: int = 3):
        self.model = model
        self.max_searches = max_searches
        self.sources = []
        self.source_urls = set()
        self.findings = []
        self.findings_cache = {}  # ADD THIS: {content_hash → finding_text}

    @staticmethod
    def _hash_content(text: str) -> str:
        """Create a hash of content for duplicate detection."""
        return hashlib.md5(text.encode()).hexdigest()[:8]

    # In run() method, replace the finding extraction section (lines 62-70):
    # Old code:
    # findings_prompt = f"Research Question: {question}\n\n..."
    # finding = await chat_complete(...)
    
    # New code:
    findings_text = "\n\n".join(scraped_content)
    content_hash = self._hash_content(findings_text + question)
    
    # Check cache first
    if content_hash in self.findings_cache:
        finding = self.findings_cache[content_hash]
        yield await self._yield_event("status", {"phase": "searching", "content": f"📚 Using cached finding for: {question}"})
    else:
        # Call LLM only if not cached
        findings_prompt = f"Research Question: {question}\n\nSource Material:\n" + "\n\n".join(scraped_content) + "\n\nProvide a comprehensive answer using facts from the sources."
        finding = await chat_complete(self.model, [{"role": "user", "content": findings_prompt}], system=SEARCH_SYSTEM)
        
        # Cache it for future use
        self.findings_cache[content_hash] = finding
    
    self.findings.append({"question": question, "finding": finding})
    yield await self._yield_event("finding", {"question": question, "content": finding})
```

### Speedup
- **Hit rate**: ~10-20% for typical research topics (questions have overlapping keywords)
- **Per hit**: Save 2-5 seconds (one LLM inference)
- **Net**: 0.5-2 seconds faster per 5-10 questions on average

### Limitations
- Only helps if questions have similar scraped content
- Cache only lasts for current request (not persistent)
- Would need persistent storage/database for cross-session caching

---

## 5. Parallel Question Processing (30 min)

### Current Code Issue
```python
# Lines 51-71 in agent.py - Sequential loop
for i, question in enumerate(plan):
    if search_count >= self.max_searches:
        break
    # ... search and extract for each question ...
```

Makes full utilization of single core only.

### Optimized Code

```python
# In agent.py, replace the search loop with:

async def _search_and_extract(self, question: str, search_count_start: int) -> tuple:
    """Helper to search, scrape, and extract for a single question."""
    try:
        yield await self._yield_event("status", {"phase": "searching", "content": f"🔍 Researching: {question}"})
        
        search_results = await duckduckgo_search(question, max_results=4)
        if not search_results:
            yield await self._yield_event("status", {"phase": "searching", "content": f"⚠️ No results for: {question}, retrying..."})
            search_results = await duckduckgo_search(question.split()[0], max_results=3)
            if not search_results:
                return (None, None, None)

        source_nums = []
        for result in search_results:
            if result['url'] not in self.source_urls:
                self.sources.append(result)
                self.source_urls.add(result['url'])
                source_nums.append(len(self.sources))
            else:
                source_nums.append([src['url'] for src in self.sources].index(result['url']) + 1)

        yield await self._yield_event("search_results", {"query": question, "results": search_results, "source_nums": source_nums})

        # Scrape in parallel
        scrape_tasks = [scrape_page(result['url']) for result in search_results]
        scraped_contents = await asyncio.gather(*scrape_tasks)
        
        scraped_content = []
        for idx, content in enumerate(scraped_contents):
            if content and not content.startswith("Error"):
                scraped_content.append(f"Source [{source_nums[idx]}]: {content}")

        if not scraped_content:
            return (None, None, None)

        # Extract finding
        findings_prompt = f"Research Question: {question}\n\nSource Material:\n" + "\n\n".join(scraped_content) + "\n\nProvide a comprehensive answer using facts from the sources."
        finding = await chat_complete(self.model, [{"role": "user", "content": findings_prompt}], system=SEARCH_SYSTEM)
        
        return (question, finding, scraped_content)
    except Exception as e:
        yield await self._yield_event("error", {"content": f"Error processing {question}: {str(e)}"})
        return (None, None, None)

# Replace the for loop section with parallel processing:
# (Around line 51-71)

search_count = 0

# Process questions in parallel batches of 3
for batch_start in range(0, len(plan), 3):
    if search_count >= self.max_searches:
        break
    
    batch = plan[batch_start:batch_start + 3]
    batch = [q for q in batch if search_count < self.max_searches]
    
    if not batch:
        break
    
    # Run 2-3 questions in parallel
    search_tasks = [self._search_and_extract(q, search_count) for q in batch]
    results = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, tuple) and result[0]:
            question, finding, scraped_content = result
            self.findings.append({"question": question, "finding": finding})
            yield await self._yield_event("finding", {"question": question, "content": finding})
            search_count += 1
        elif isinstance(result, Exception):
            yield await self._yield_event("error", {"content": f"Batch processing error: {str(result)}"})
```

### Speedup
- **Expected**: 30-40% faster search phase (process 3 questions in time of ~2)
- **Total impact**: 15-25 seconds saved on 60-150s job
- **Risk**: Medium
  - Ollama may struggle with 3 concurrent LLM inferences
  - Network congestion if all 3 scrape requests simultaneous
  - Mitigation: Start with 2 parallel, test with 3

### Important Considerations
1. This requires `_search_and_extract` to be an async generator
2. Concurrent LLM calls might bottleneck on Ollama
3. Could cause queue-induced UI flickering (findings appear out-of-order)

---

## 6. Configuration Optimization (20 min for testing)

### Current Issue
```python
# Same settings for all phases (ollama_client.py)
"options": {
    "temperature": 0.7,
    "num_predict": 2048,
}
```

### Optimized per-Phase Settings
```python
# ollama_client.py - Add phase-aware settings:

PHASE_SETTINGS = {
    "plan": {"temperature": 0.5, "num_predict": 512},      # Fast, creative
    "search": {"temperature": 0.8, "num_predict": 1024},   # Balanced
    "reflect": {"temperature": 0.3, "num_predict": 256},   # Precise yes/no
    "report": {"temperature": 0.7, "num_predict": 4096},   # Detailed
}

async def chat_complete(
    model: str,
    messages: List[Dict[str, str]],
    system: str = "",
    phase: str = "default"  # ADD parameter
) -> str:
    """Gets a complete response from the Ollama API."""
    settings = PHASE_SETTINGS.get(phase, {"temperature": 0.7, "num_predict": 2048})
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages if system else messages,
        "stream": False,
        "options": settings,  # Use phase-specific settings
    }
    # ... rest of function ...

async def chat_stream(
    model: str,
    messages: List[Dict[str, str]],
    system: str = "",
    phase: str = "default"  # ADD parameter
) -> AsyncGenerator[str, None]:
    """Streams responses from the Ollama API."""
    settings = PHASE_SETTINGS.get(phase, {"temperature": 0.7, "num_predict": 2048})
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages if system else messages,
        "stream": True,
        "options": settings,
    }
    # ... rest of function ...
```

### Update agent.py calls:
```python
# Line 39: Planning call
plan_str = await chat_complete(self.model, [...], system=PLAN_SYSTEM, phase="plan")

# Line 70: Finding extraction
finding = await chat_complete(self.model, [...], system=SEARCH_SYSTEM, phase="search")

# Line 89: Reflection call
reflection_str = await chat_complete(self.model, [...], system=REFLECT_SYSTEM, phase="reflect")

# Line 117: Report streaming
async for token in chat_stream(self.model, [...], system=REPORT_SYSTEM, phase="report"):
```

### Expected Impact
- **Planning**: 10-20% faster (lower num_predict)
- **Report**: Potentially higher quality (higher num_predict)
- **Overall**: 5-10% faster without quality loss

---

## Implementation Roadmap

### Batch 1 (Day 1 - 1 hour)
1. URL dedup with Set ✓
2. Timeout reduction with retry ✓
3. Simple findings cache ✓

### Batch 2 (Day 2 - 1 hour)
4. Connection pooling ✓
5. Configuration optimization ✓

### Batch 3 (Day 3 - 2 hours, if bottleneck remains)
6. Parallel question processing ✓

### Testing Checklist
- [ ] Report quality unchanged
- [ ] No resource leaks (client cleanup)
- [ ] Error handling still works
- [ ] Streaming still smooth
- [ ] Time measurements show improvement
