# Student Timetable for AI Research Agent Usage

This timetable outlines daily duties for using the AI Research Agent as a student researcher, from **Tuesday to Saturday**. Focus on setup, research sessions for study topics, report review, and weekly maintenance. Assume ~4-6 hours/day, adjustable. Always start with `./start.sh` (or manual), open http://localhost:3000, select model (e.g., llama3.2), use depth slider (2-3 for quick, 4-5 for deep).

## Weekly Timetable

| Time Slot | Tuesday (Study Planning) | Wednesday (Deep Dive) | Thursday (Review & Apply) | Friday (Current Events) | Saturday (Synthesis & Maintenance) |
|-----------|---------------------------|-----------------------|---------------------------|-------------------------|------------------------------------|
| **8:00-9:00 AM** | ✅ Setup: Run `./start.sh`, check Ollama/models, test interface | ✅ Setup: Run `./start.sh`, load recent history | ✅ Setup: Run `./start.sh`, review Friday report | ✅ Setup: Run `./start.sh`, clear old history if needed | ✅ Full Setup & Backup: Run `./start.sh`, backup reports |
| **9:00-10:00 AM** | 📖 Research: \"Weekly study plan using AI tools\" (depth 2) | 🔬 Research: Subject deep dive e.g. \"Quantum computing basics\" (depth 4) | 📚 Review Thursday report, copy to notes | 🌐 Research: Current news e.g. \"Latest AI breakthroughs\" (depth 3) | 📊 Research: \"Weekly learning summary from reports\" (depth 3) |
| **10:00-11:00 AM** | ✏️ Review plan report, note 3-5 topics for week | 🔍 Research 2nd question from log (e.g. applications) | ✅ Apply findings: Outline essay/homework using report | 📖 Wikipedia integration review | 🔧 Maintenance: Check `pip list` in backend/venv, update if needed |
| **11:00-12:00 PM** | 🛑 Break / Lunch | 🛑 Break / Lunch | 🛑 Break / Lunch | 🛑 Break / Lunch | 🛑 Break / Lunch |
| **2:00-3:00 PM** | 📚 Research: Topic 1 e.g. \"History of [subject]\" | 🔬 Research: Follow-up gaps from reflection log | 📝 Edit/copy sources [1-5], cite in doc | 🌐 Research 2nd: \"Implications of [news topic]\" | 📈 Analyze patterns across week&#39;s reports |
| **3:00-4:00 PM** | 📋 Log review: Check sources, reflection | ✅ Copy report to study notes/Google Doc | 🎯 Research related homework question | 📋 Stop & save, review sources | 🧹 Clear history if full, test new model pull |
| **4:00-5:00 PM** | 🛑 Wrap-up: Copy report, shutdown servers | 🛑 Wrap-up: Synthesize day&#39;s findings | 🛑 Wrap-up: Plan weekend synthesis | 🛑 Wrap-up: Note key stats/insights | ✅ Weekly Review: Export all reports, shutdown |

## Key Duties Explained
- **Setup (Daily)**: Ensure Ollama running, `./start.sh` launches backend/frontend. Watch agent log for phases: 🗺️Plan → 🔍Search → 🤔Reflect → ✍️Report.
- **Research Sessions**: Input topic, hit Research ▶, monitor real-time stream. Adjust depth for speed/depth trade-off.
- **Review**: Use 📋Copy button, check sources panel. Integrate into studies (notes, essays).
- **Maintenance (Sat)**: `cd backend && venv\\Scripts\\activate && pip install -r requirements.txt --upgrade`, `ollama pull llama3.2`.
- **Tips**: Keep tabs open for multi-session. Use for homework, exam prep, curiosity topics.

**Total Weekly Research Time: ~20 hours**. Track progress in a journal. Enjoy autonomous learning! 🚀
