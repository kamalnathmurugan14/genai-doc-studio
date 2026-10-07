# 5-step demo script
1. **Setup** – `ollama serve`, start backend + frontend; open Studio and pick `meeting_notes.txt`.
2. **Stream** – *Summarize → bullets → Run*: tokens stream live; press **Stop** mid-way, then run again to see token/time counters.
3. **Long documents** – upload a long PDF, run *Summarize*: expand the *Map-reduce steps* accordion to show each chunk summary.
4. **Structured output** – *Extract → entities*: show `valid JSON`, the ✔ verified evidence markers, and (with a weak model) a retry count > 1.
5. **Prompts & compare** – open *Edit prompt & params*, tweak the template (live preview), save a new version, then *A/B compare* temperature 0 vs 1.2 on the same file; finish in *History*.
