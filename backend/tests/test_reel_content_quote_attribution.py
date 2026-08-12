from app.db.models import Claim as ClaimModel
from app.db.models import ClaimType
from app.pipeline.reel_content import _find_quote_claim, _speaker_name


def _claim(text: str, source_quote: str | None, entities: list[dict], importance: float = 0.5) -> ClaimModel:
    return ClaimModel(
        text=text,
        claim_type=ClaimType.factual,
        verifiable=True,
        importance=importance,
        source_quote=source_quote,
        entities=entities,
    )


def test_third_person_on_screen_headline_is_not_attributed_to_its_subject():
    # Real bug found live against the mandatory test reel
    # (docs/CURRENT_ARCHITECTURE.md): source_quote was a genuine verbatim
    # on-screen caption written by the video's publisher — "Kejriwal
    # Attacks Centre Over New 3-Hour Social Media Takedown Rule" — which
    # passes the "is it verbatim" check, but attributing it to Kejriwal
    # himself is still wrong: he didn't say or write those words, the
    # publisher did, describing him in the third person.
    claim = _claim(
        text="Arvind Kejriwal criticized the Indian Central Government over a new 3-hour social media takedown rule.",
        source_quote="Kejriwal Attacks Centre Over New 3-Hour Social Media Takedown Rule",
        entities=[
            {"name": "Arvind Kejriwal", "type": "person"},
            {"name": "Government of India", "type": "organization"},
        ],
    )
    assert _speaker_name(claim, reel_creator_handle="InformIndia24") == "InformIndia24"


def test_genuine_first_person_quote_is_still_attributed_to_the_speaker():
    claim = _claim(
        text="Arvind Kejriwal said the takedown rule was rushed through without consultation.",
        source_quote="This rule was rushed through without any real consultation.",
        entities=[{"name": "Arvind Kejriwal", "type": "person"}],
    )
    assert _speaker_name(claim, reel_creator_handle="InformIndia24") == "Arvind Kejriwal"


def test_no_quote_claim_falls_back_to_reel_creator():
    assert _speaker_name(None, reel_creator_handle="InformIndia24") == "InformIndia24"


def test_find_quote_claim_prefers_attribution_verb_claims():
    plain = _claim("The rule takes effect in 30 days.", source_quote="within 30 days", entities=[], importance=0.9)
    attributed = _claim(
        "Kejriwal criticized the rule.", source_quote="This is unacceptable.", entities=[], importance=0.1
    )
    result = _find_quote_claim([plain, attributed])
    assert result is attributed
