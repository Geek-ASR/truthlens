"""Failure taxonomy entry #13 (research_paper/main.tex Appendix):
"Baseline architecture silently inheriting a rescue mechanism under
evaluation." The first working draft of Baselines 2-3 called
app.services.ai.factory.get_llm_provider(), which silently returns a
Gemini-fallback-wrapped provider whenever GEMINI_API_KEY is set -- giving
both "simple" baselines the exact failure-rescue mechanism TruthLens's
own architecture was being evaluated for having. Caught during smoke
testing before any number was reported; fixed by importing
OllamaProvider directly in every baseline script instead.

This is a static, structural regression test (not a runtime one): it
greps every research/baselines/*.py script's actual source for the
banned import pattern, so a future baseline script reintroducing this
exact bug fails CI immediately rather than silently inflating that
baseline's measured accuracy the way this bug did the first time,
undetected until manual smoke testing caught it."""
from pathlib import Path

_BASELINES_DIR = Path(__file__).resolve().parents[3] / "research" / "baselines"


def _baseline_scripts() -> list[Path]:
    scripts = [
        p for p in _BASELINES_DIR.glob("*.py") if p.name not in {"common.py", "__init__.py"}
    ]
    assert scripts, f"expected to find baseline scripts under {_BASELINES_DIR}, found none"
    return scripts


def test_no_baseline_script_imports_the_gemini_fallback_factory():
    offenders = []
    for script in _baseline_scripts():
        text = script.read_text()
        if "from app.services.ai.factory import get_llm_provider" in text or "factory.get_llm_provider" in text:
            offenders.append(script.name)
    assert offenders == [], (
        f"{offenders} import the Gemini-fallback-wrapping factory directly -- "
        "baselines must import OllamaProvider (or the Gemini-quota-aware "
        "provider explicitly, for a baseline that intentionally tests "
        "Gemini) directly, never through get_llm_provider(), which "
        "silently wraps Ollama in a Gemini fallback whenever "
        "GEMINI_API_KEY is set (see this file's own docstring)."
    )


def test_every_baseline_script_imports_ollama_provider_directly():
    missing = [s.name for s in _baseline_scripts() if "from app.services.ai.ollama_provider import" not in s.read_text()]
    assert missing == [], f"{missing} do not import OllamaProvider directly -- verify they aren't using the factory instead."
