# Results directory — status

**Nothing in this directory as of Day 3 is a final result.** Everything
here so far is a functional smoke test confirming the baseline code
(`backend/research/baselines/`) actually runs end-to-end against the
real dataset without crashing — not a frozen, comparable evaluation.
The real, final run happens once at Day 8, against whatever the dataset
has grown to by then, with every configuration run at the same frozen
point, per `research/EXPERIMENT_PLAN.md`.

## Files present after Day 3

- `baseline_search_llm_20260812T210132Z.jsonl` — Baseline 2 smoke test.
  **Caveat**: this run used `app.services.ai.factory.get_llm_provider()`,
  which (since `GEMINI_API_KEY` was set at the time) silently wraps
  Ollama in `FallbackLLMProvider` — meaning this specific run could have
  used Gemini as a rescue path on a raw Ollama failure, which is exactly
  the confound `BASELINE_SPEC.md` says a baseline must not have. The bug
  was found and fixed (both baseline scripts now use `OllamaProvider()`
  directly) immediately after this run had already started; it was left
  to finish rather than killed, since it's real, honestly-labeled smoke
  -test data, not a result being relied on for any conclusion. **Do not
  cite numbers from this file in the paper.**
- `baseline_search_rag_llm_20260812T210417Z.jsonl` — Baseline 3 smoke
  test, run with the corrected code (`OllamaProvider()` directly, no
  Gemini fallback available). This one IS methodologically clean, but
  is still only a 7-item smoke test against a dataset not yet frozen at
  its final size — not a Day 8 result either.

## What Day 8 will do differently

- Re-run Baseline 2 with the corrected code (this file's caveat won't
  apply to that run).
- Run against the full, by-then-frozen dataset, not the 7 items that
  existed during Day 3.
- Run all five configurations (LLM-only, Search+LLM, Search+RAG+LLM,
  TruthLens-minus-validation, Full TruthLens) at the same frozen point,
  per `EXPERIMENT_PLAN.md` §"Day 8" discipline — no configuration's
  numbers get reused piecemeal from an earlier smoke test once the real
  run happens.
