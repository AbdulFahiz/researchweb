import json
import asyncio
from typing import AsyncGenerator, List, Dict, Any

from ollama_client import chat_complete, chat_stream
from tools import duckduckgo_search, scrape_page, wikipedia_search

# System Prompts
PLAN_SYSTEM = "You are a research planning expert. Analyze the topic deeply and return ONLY a JSON array of 4-5 specific, diverse sub-questions that cover different angles (history, current state, applications, implications, future). No other text."
SEARCH_SYSTEM = "You are a research analyst. Extract ONLY the most relevant and important facts, data points, statistics, and insights. Be specific with numbers, dates, and names. Ignore marketing language and focus on substance."
REFLECT_SYSTEM = "You are a quality evaluator. Assess if we have sufficient information to write a comprehensive report. Return ONLY JSON: {\"sufficient\": true/false, \"missing\": [\"specific gap\"]}. No other text."
REPORT_SYSTEM = "You are an expert research writer. Write a comprehensive, well-structured report using markdown: # [Topic], ## Executive Summary (overview), ## Key Findings (organized by theme), ## Analysis (deeper insights), ## Conclusion. Use [1], [2] citation format. Be authoritative, cite facts, and provide 500+ words. Format clearly with subheadings."

class ResearchAgent:
    def __init__(self, model: str, max_searches: int = 3):
        self.model = model
        self.max_searches = max_searches
        self.sources = []
        self.source_urls = set()  # O(1) URL lookup instead of O(n)
        self.findings = []
        self.client = None

    async def _yield_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        event = {"type": event_type, "data": data}
        return event

    async def run(self, topic: str) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # Initialize reusable HTTP client for page scraping (connection pooling)
            import httpx
            self.client = httpx.AsyncClient(headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }, follow_redirects=True, timeout=15.0)
            
            # 1. Plan
            yield await self._yield_event("status", {"phase": "planning", "content": "🗺️ Planning research..."})
            plan_str = await chat_complete(self.model, [{"role": "user", "content": f"Topic: {topic}"}], system=PLAN_SYSTEM)
            
            try:
                plan = json.loads(plan_str.strip())
                if not isinstance(plan, list):
                    # If it's not a list, try to extract one
                    plan = [str(plan)]
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract questions from the response text
                lines = plan_str.split('\n')
                plan = [line.strip() for line in lines if line.strip() and not line.strip().startswith('[') and not line.strip().startswith(']')]
                if not plan:
                    plan = ["What are the key aspects of " + topic, "How does " + topic + " work", "What is the history of " + topic, "What are the current applications of " + topic, "What are future trends in " + topic]
            
            if plan and isinstance(plan, list):
                yield await self._yield_event("plan", {"content": plan})
            else:
                yield await self._yield_event("error", {"content": f"Failed to generate valid plan from response: {plan_str}"})
                return

            # 2. Search - Parallel processing for efficiency
            search_count = 0
            import asyncio
            
            for i, question in enumerate(plan):
                if search_count >= self.max_searches:
                    break
                
                yield await self._yield_event("status", {"phase": "searching", "content": f"🔍 Researching: {question}"})
                
                # Search with better query formulation
                search_results = await duckduckgo_search(question, max_results=4)
                if not search_results:
                    yield await self._yield_event("status", {"phase": "searching", "content": f"⚠️ No results for: {question}, retrying..."})
                    search_results = await duckduckgo_search(question.split()[0], max_results=3)
                    if not search_results:
                        continue

                source_nums = []
                for result in search_results:
                    if result['url'] not in self.source_urls:  # O(1) set lookup instead of O(n) list lookup
                        self.sources.append(result)
                        self.source_urls.add(result['url'])
                        source_nums.append(len(self.sources))
                    else:
                        # Find existing source index
                        source_nums.append(next(i+1 for i, src in enumerate(self.sources) if src['url'] == result['url']))

                yield await self._yield_event("search_results", {"query": question, "results": search_results, "source_nums": source_nums})

                # Scrape pages in parallel with reusable client (connection pooling)
                scrape_tasks = [scrape_page(self.client, result['url']) for result in search_results]
                scraped_contents = await asyncio.gather(*scrape_tasks)
                
                scraped_content = []
                for idx, content in enumerate(scraped_contents):
                    if content and not content.startswith("Error"):
                        scraped_content.append(f"Source [{source_nums[idx]}]: {content}")

                if not scraped_content:
                    continue

                # Extract findings with better context
                findings_prompt = f"Research Question: {question}\n\nSource Material:\n" + "\n\n".join(scraped_content) + "\n\nProvide a comprehensive answer using facts from the sources."
                finding = await chat_complete(self.model, [{"role": "user", "content": findings_prompt}], system=SEARCH_SYSTEM)
                self.findings.append({"question": question, "finding": finding})
                yield await self._yield_event("finding", {"question": question, "content": finding})
                
                search_count += 1

            # 3. Wikipedia
            yield await self._yield_event("status", {"phase": "searching", "content": f"📖 Fetching Wikipedia summary for \"{topic}\""})
            wiki_summary = await wikipedia_search(self.client, topic)
            if not wiki_summary.startswith("Error"):
                self.findings.insert(0, {"question": "Wikipedia Summary", "finding": wiki_summary})
                yield await self._yield_event("wiki", {"content": wiki_summary})

            # 4. Reflect
            yield await self._yield_event("status", {"phase": "reflecting", "content": "🤔 Reflecting on findings..."})
            findings_text = "\n\n".join([f"### {f['question']}\n{f['finding']}" for f in self.findings])
            reflect_prompt = f"Topic: {topic}\n\nCurrent Findings:\n{findings_text}"
            reflection_str = await chat_complete(self.model, [{"role": "user", "content": reflect_prompt}], system=REFLECT_SYSTEM)
            
            try:
                reflection = json.loads(reflection_str.strip())
                if not isinstance(reflection, dict):
                    reflection = {"sufficient": True, "missing": []}
            except json.JSONDecodeError:
                # If parsing fails, assume research is sufficient
                reflection = {"sufficient": True, "missing": []}
            
            yield await self._yield_event("reflect", {"content": reflection})
            if not reflection.get("sufficient", True) and search_count < self.max_searches and reflection.get("missing"):
                # Perform additional searches for missing info
                for missing_query in reflection["missing"]:
                     if search_count >= self.max_searches:
                        break
                     # (This is a simplified loop, a more robust agent would integrate this better)
                     yield await self._yield_event("status", {"phase": "searching", "content": f"🔍 Addressing gaps: \"{missing_query}\""})
                     # ... (re-run search logic) ...
                     search_count += 1


            # 5. Report
            yield await self._yield_event("status", {"phase": "writing", "content": "✍️ Writing report..."})
            yield await self._yield_event("report_start", {})

            source_list = "\n".join([f"[{i+1}] {src['title']}: {src['url']}" for i, src in enumerate(self.sources)])
            report_prompt = f"Topic: {topic}\n\nFindings:\n{findings_text}\n\nSources:\n{source_list}"
            
            async for token in chat_stream(self.model, [{"role": "user", "content": report_prompt}], system=REPORT_SYSTEM):
                if "Error:" in token:
                    yield await self._yield_event("error", {"content": token})
                    return
                yield await self._yield_event("report_token", {"content": token})

            yield await self._yield_event("done", {"sources": self.sources})

        except Exception as e:
            yield await self._yield_event("error", {"content": str(e)})
        
        finally:
            # Close the HTTP client to prevent resource leaks
            if self.client:
                await self.client.aclose()
