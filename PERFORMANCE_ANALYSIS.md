# Research-Agent Performance Analysis

## 1. REPORT GENERATION FLOW

### Complete Request Flow: `/research` → Report Output

```
1. Client POST /research with (topic, model, depth)
   ↓
2. ResearchAgent initialized (model, max_searches=depth)
   ↓
3. PHASE 1: Planning (LLM Call #1)
   - LLM generates 4-5 research sub-questions from topic
   - Output: Array of questions
   - LLM Model: Selected model, Temp: 0.7, Max tokens: 2048
   ↓
4. PHASE 2: Searching & Finding (LLM Calls #2-N)
   FOR EACH question (up to max_searches):
     a) DuckDuckGo search(question)
        - Cache checked first (30-entry LRU cache)
        - Returns up to 4 results with title/snippet/url
     b) Parallel page scraping
        - asyncio.gather() fetches ALL 4 pages concurrently (GOOD!)
        - Each scrape: 15s timeout per page, extracts 2000 chars max
     c) LLM extraction (LLM Call)
        - Analyzes scraped content + original question
        - Extracts key findings as text
        - Output streamed to client
   ↓
5. PHASE 3: Wikipedia Fetch (HTTP Call)
   - GET Wikipedia API for topic summary
   - Inserted at beginning of findings list
   ↓
6. PHASE 4: Reflection (LLM Call)
   - LLM evaluates if research is sufficient
   - Returns: {sufficient: bool, missing: [gaps]}
   - **BUG**: Additional search logic for missing gaps is incomplete
   ↓
7. PHASE 5: Report Generation (Streaming LLM Call)
   - Assembles all findings + sources into report prompt
   - Uses chat_stream() to send tokens incrementally to client
   - Client receives tokens in real-time (Server-Sent Events)
   ↓
8. Done event with sources list
```

### Timing Breakdown (Estimated per Phase)

| Phase | Operation | Bottleneck | Time |
|-------|-----------|-----------|------|
| Planning | 1 LLM call | LLM inference | ~3-10s |
| Search-Scrape (per Q) | 4 parallel page fetches | Network I/O (4-6s) | 4-6s |
| Search-Extract (per Q) | 1 LLM call on scraped content | LLM inference | ~2-5s |
| Reflection | 1 LLM call on all findings | LLM inference | ~3-8s |
| Report | 1 streaming LLM call | LLM inference + network | ~10-30s |
| **TOTAL** (depth=3) | 5 searches × (2-5s LLM + 4-6s scrape) + 3-10s plan + 3-8s reflect + 10-30s report | **LLM + Network I/O** | **60-150s** |

---

## 2. PERFORMANCE BOTTLENECKS

### 🔴 CRITICAL BOTTLENECKS

#### 1. **Sequential LLM Calls Across Phases** (Highest Impact)
- **Issue**: plan → findings extraction (x5) → reflection → report are **strictly sequential**
- **Current**: Each phase waits for previous to complete
- **Impact**: Adding 3-8s per LLM call, 5+ calls = 15-40s minimum overhead
- **Code Location**: [agent.py](agent.py) lines 34-39, 62-70, 85-93, 101-130

#### 2. **Search Loop Processes Questions Sequentially** (High Impact)
- **Issue**: Even though page scraping is parallelized within a question, each question waits for:
  - Search results
  - Page scraping (parallel ✓)
  - LLM extraction
- Before moving to next question
- **Current Flow**:
  ```
  Q1: search → [scrape1,2,3,4 in parallel] → LLM extract (5-9s)
  Q2: search → [scrape1,2,3,4 in parallel] → LLM extract (5-9s)
  Q3: search → [scrape1,2,3,4 in parallel] → LLM extract (5-9s)
  ```
- **Potential**: Could do 2-3 searches in parallel
- **Code Location**: [agent.py](agent.py) lines 51-71

#### 3. **Page Scraping Timeout Inefficiency** (Medium Impact)
- **Issue**: Each `scrape_page()` call has 15s timeout, but most pages respond in 2-4s
- **Wasted**: 11-13s per slow/blocked page × 4 pages/question × 3-5 questions = ~1-2 min worst case
- **No Connection Pooling**: Each scrape creates new httpx.AsyncClient (lines 96-98 in tools.py)
- **Code Location**: [tools.py](tools.py) lines 75-120

#### 4. **No LLM Response Caching** (High Impact)
- **Issue**: Same findings can be extracted multiple times for similar queries
- **Example**: If two plan questions are similar, extractions of same content happens twice
- **No Caching**: Zero memoization of LLM calls
- **Code Location**: [ollama_client.py](ollama_client.py) - chat_complete() and chat_stream()

#### 5. **Double URL Lookup** (Low-Medium Impact)
- **Issue**: `if result['url'] not in [src['url'] for src in self.sources]` is O(n)
- **Scales**: With 4-5 results × 3-5 questions = 15-25 lookups, each checking 15-25 existing URLs
- **Code Location**: [agent.py](agent.py) lines 62-65

#### 6. **Partial Chat Streaming** (Medium Impact)
- **Issue**: Report uses chat_stream() for tokens (GOOD!), but findings are sent as complete chunks
- **Finding events**: `yield await self._yield_event("finding", ...)` - entire finding sent at once
- **Inconsistency**: User sees report flowing but waits for findings in bulk
- **Code Location**: [agent.py](agent.py) lines 69-70

---

## 3. OPTIMIZATIONS AVAILABLE

### 🟢 QUICK WINS (1-2 hour implementation)

1. **Parallel Question Processing**
   - **Idea**: Run 2-3 searches in parallel instead of sequential  
   - **Effort**: ~30 min
   - **Expected Gain**: ~30-40% faster search phase
   - **Risk**: Low
   - **Implementation**: 
     - Gather first `min(3, len(plan))` questions into parallel searchers
     - Limit to 3 to avoid overwhelming Ollama and network
   ```python
   # Instead of for loop, use:
   search_tasks = []
   for i, question in enumerate(plan[:min(3, self.max_searches)]):
       search_tasks.append(self._search_and_extract(question))
   results = await asyncio.gather(*search_tasks)
   ```

2. **Efficient URL Deduplication with Set**
   - **Idea**: Replace O(n) list search with O(1) set
   - **Effort**: ~5 min
   - **Expected Gain**: Negligible (milliseconds)
   - **Risk**: Very Low
   ```python
   self.source_urls = set()  # Add to __init__
   if result['url'] not in self.source_urls:
       self.sources.append(result)
       self.source_urls.add(result['url'])
   ```

3. **Connection Pool Reuse**
   - **Idea**: Create single httpx.AsyncClient at agent level, reuse for all scrapes
   - **Effort**: ~15 min
   - **Expected Gain**: ~5-10% faster page scraping (connection reuse)
   - **Risk**: Low (need proper cleanup)
   ```python
   self.client = httpx.AsyncClient(headers=HEADERS, timeout=15.0)
   # Use in scrape_page(), cleanup in done
   await self.client.aclose()
   ```

4. **Timeout Reduction with Fallback**
   - **Idea**: Reduce initial timeout to 8s, retry once with 10s if failed
   - **Effort**: ~20 min
   - **Expected Gain**: ~2-5s per slow page
   - **Risk**: Medium (might fail on legitimately slow pages)
   ```python
   try:
       response = await client.get(url, timeout=8.0)
   except httpx.TimeoutException:
       response = await client.get(url, timeout=10.0)  # One retry
   ```

5. **LLM Response Caching (Simple)**
   - **Idea**: Cache LLM findings by `hash(question + scraped_content_hash)`
   - **Effort**: ~30 min
   - **Expected Gain**: ~10-20% if questions/content repeat
   - **Risk**: Low
   ```python
   import hashlib
   cache_key = hashlib.md5(f"{question}{content}".encode()).hexdigest()
   if cache_key in findings_cache:
       return findings_cache[cache_key]
   ```

6. **Stream Individual Findings**
   - **Idea**: Stream finding extraction token-by-token like report
   - **Effort**: ~20 min
   - **Expected Gain**: Better perceived performance (progressive display)
   - **Risk**: Low
   - Change `finding` event to stream tokens instead of complete text

### 🟡 MEDIUM EFFORT (2-4 hours)

7. **Batch Finding Extraction**
   - **Idea**: Extract findings for 2-3 searches in parallel (with different contexts)
   - **Effort**: ~1 hour
   - **Expected Gain**: ~40-50% faster if findings extraction is bottleneck
   - **Risk**: Medium (need careful prompt design to avoid crosstalk)
   - **Note**: Requires refactoring search loop to collect all scraped content, then batch extract

8. **Smart Reflection with Targeted Re-search**
   - **Idea**: Complete the incomplete "address gaps" logic
   - **Effort**: ~1.5 hours
   - **Expected Gain**: More thorough reports, potentially fewer iterations
   - **Risk**: Medium (network/LLM overhead if many gaps)
   - **Code Location**: [agent.py](agent.py) lines 93-99 (incomplete)

9. **Reduce Ollama Inference Cost**
   - **Idea**: Lower `num_predict=2048` for planning (could use 512), increase for report (4096)
   - **Effort**: ~20 min (testing required)
   - **Expected Gain**: ~5-10% faster planning, better reports
   - **Risk**: Medium (quality/quantity trade-off)
   ```python
   # Different settings per phase
   PLAN_SETTINGS = {"num_predict": 512, "temperature": 0.5}
   REPORT_SETTINGS = {"num_predict": 4096, "temperature": 0.7}
   ```

10. **Implement Request-Level Caching**
    - **Idea**: Cache entire report for duplicate topics (with TTL)
    - **Effort**: ~2 hours
    - **Expected Gain**: ~90% faster for repeat topics
    - **Risk**: Medium (cache invalidation, storage)
    - **Note**: Redis or in-memory with TTL

---

## 4. STREAMING IMPLEMENTATION STATUS

### ✅ WHAT'S ALREADY STREAMING:
- **Report Generation**: Uses `chat_stream()` to send tokens incrementally
  - [agent.py](agent.py) lines 116-120
  - [main.py](main.py) lines 60-62
  - Client receives SSE (Server-Sent Events) with report content token-by-token
  - **Good**: User sees report appearing in real-time

### ❌ NOT STREAMING:
- **Plan Phase**: Full array sent at once
- **Findings Extraction**: Each finding is complete text, not streamed
- **Reflection**: Complete JSON sent at once
- **Search Results**: Complete array sent at once

### 🟡 OPPORTUNITY:
- Streaming findings extraction would improve perceived performance significantly
- Current: Wait 3-5s for finding, then see it appear all at once
- Better: See finding tokens appearing as they're extracted

---

## 5. CURRENT CACHE STRATEGY

### ✅ EXISTING CACHING:
- **DuckDuckGo Search Cache**: 30-entry LRU cache ([tools.py](tools.py) lines 19-25)
  - Fast for repeated queries
  - Auto-evicts oldest when full

### ❌ MISSING CACHES:
- **LLM Response Cache**: No caching of findings, plans, reflections
- **Page Scrape Cache**: Each URL fetched on demand, no storage
- **Session Cache**: No cross-request caching

### 💡 RECOMMENDED CACHING ADDITIONS:
1. **Findings Cache**: `hash(question + scraped_content) → finding_text`
2. **Plan Cache** (optional): `topic → plan` with 6-hour TTL
3. **Content Cache**: Store scraped pages for 24-48 hours

---

## 6. RECOMMENDED IMPLEMENTATION PRIORITY

### Phase 1 - Quick Wins (Do First - 1-2 hours)
1. ✓ URL dedup with Set (5 min)
2. ✓ Connection pool reuse (15 min)
3. ✓ Timeout reduction with fallback (20 min)
4. ✓ Simple findings cache (30 min)

**Expected improvement: 10-20% faster**

### Phase 2 - Medium Effort (Do Next - 2-4 hours)  
1. ✓ Parallel question processing (30 min)
2. ✓ Streaming findings extraction (20 min)
3. ✓ Complete gap-filling logic (1.5 hours)

**Expected improvement: 30-50% faster**

### Phase 3 - Future Optimization (Database required)
1. Request-level caching with TTL
2. Persistent content cache
3. LLM response database with embedding-based retrieval

---

## 7. KEY FINDINGS SUMMARY

| Finding | Severity | Impact | Effort |
|---------|----------|--------|--------|
| Sequential LLM calls across phases | 🔴 | Adds 15-40s overhead | Hard |
| Sequential question processing | 🔴 | 30-40% speed gain available | Medium |
| No LLM response caching | 🔴 | 10-20% duplicate work | Easy |
| Page scrape timeout inefficiency | 🟡 | 1-2 min worst case | Medium |
| No connection pooling | 🟡 | 5-10% improvement available | Easy |
| Inefficient URL lookups | 🟢 | Milliseconds | Easy |
| Partial streaming architecture | 🟡 | Better UX, not faster | Easy |
| Incomplete gap-filling logic | 🟡 | Missing feature | Medium |

---

## BOTTLENECK DIAGRAM

```
Total Time: 60-150s (depth=3)
│
├─ PHASE 1: Planning (3-10s)
│  └─ LLM inference ⏱️
│
├─ PHASE 2: Search × max_searches (Sequential, Critical!)
│  │
│  ├─ Q1 (5-9s total)
│  │  ├─ DuckDuckGo search (0.5s) [cached if repeat]
│  │  ├─ Scrape 4 pages [parallel] (4-6s) ⏱️
│  │  └─ LLM extraction (2-5s) ⏱️
│  │
│  ├─ Q2 (5-9s) [WAITS FOR Q1]
│  │  └─ Same as Q1
│  │
│  └─ Q3 (5-9s) [WAITS FOR Q2]
│     └─ Same as Q1
│
├─ PHASE 3: Wikipedia (1-3s) [Could be parallel with Phase 2]
│  └─ HTTP API call ⏱️
│
├─ PHASE 4: Reflection (3-8s)
│  └─ LLM inference ⏱️
│
└─ PHASE 5: Report (10-30s)
   └─ LLM streaming ⏱️ [Efficiently streamed!]
```

**Key insight**: Phases 2-4 are strictly sequential with no parallelism between them.
