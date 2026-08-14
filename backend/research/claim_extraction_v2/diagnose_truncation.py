"""EXP-009 follow-up: confirm whether claim extraction's output
truncation on item-0001 (EOF while parsing JSON at column 12461,
research/results/claim_extraction_recall_comparison_20260815.json) is
actually caused by num_predict=4096 running out mid-response, and
whether raising it fixes it -- rather than assuming from the error
message alone.

Calls Ollama directly (not through OllamaProvider, to capture the raw,
unparsed response text and Ollama's own `done_reason` field, which
`structured_call()` discards) at several num_predict values.

Run: ./.venv/bin/python research/claim_extraction_v2/diagnose_truncation.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import ollama  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.claim_extraction import _build_user_content  # noqa: E402
from app.schemas.claim import ClaimExtractionResult  # noqa: E402
from app.services.ai.prompts import CLAIM_EXTRACTION_SYSTEM_PROMPT  # noqa: E402

_TARGET_URL = "https://www.instagram.com/reel/DYCLkKoBpof/"  # item-0001, the item that truncated


async def _raw_call(client, *, user_content: str, num_predict: int) -> dict:
    response = await client.chat(
        model="llama3.2",
        messages=[
            {"role": "system", "content": CLAIM_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        format=ClaimExtractionResult.model_json_schema(),
        options={"temperature": 0.2, "num_predict": num_predict, "repeat_penalty": 1.3},
    )
    text = response.message.content or ""
    return {
        "num_predict": num_predict,
        "done_reason": getattr(response, "done_reason", None),
        "eval_count": getattr(response, "eval_count", None),
        "output_chars": len(text),
        "ends_with_valid_json_close": text.rstrip().endswith("}"),
        "last_120_chars": text[-120:],
    }


async def main() -> None:
    settings = get_settings()
    client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reel).where(Reel.source_url == _TARGET_URL).limit(1))
        reel = result.scalars().first()
        user_content = _build_user_content(reel)

    print(f"user_content length: {len(user_content)} chars\n")

    for num_predict in (4096, 8192, 16384):
        outcome = await _raw_call(client, user_content=user_content, num_predict=num_predict)
        print(f"num_predict={num_predict}:")
        for k, v in outcome.items():
            if k != "num_predict":
                print(f"  {k}: {v!r}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
