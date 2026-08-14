"""experiments/README.md's schema, enforced: every entry is valid JSON,
every experiment_id is unique and follows the EXP-NNN convention (per
"No experiment may silently overwrite an old result" -- a duplicate ID
would be exactly that), and every entry has the fields the schema
requires."""
import json
import re
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "experiments" / "registry.jsonl"
_REQUIRED_FIELDS = {
    "experiment_id", "hypothesis", "dataset", "split", "n", "baseline", "variant",
    "model", "prompt_version", "retrieval_version", "validator_version", "metrics",
    "result", "confidence_interval", "failure_cases", "interpretation",
    "hypothesis_supported", "artifact", "date",
}
_ID_PATTERN = re.compile(r"^EXP-\d{3,}$")


def _load_registry() -> list[dict]:
    with open(_REGISTRY_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_registry_is_valid_jsonl():
    entries = _load_registry()
    assert len(entries) > 0


def test_every_experiment_id_is_unique():
    entries = _load_registry()
    ids = [e["experiment_id"] for e in entries]
    assert len(ids) == len(set(ids)), f"duplicate experiment_id(s) found: {[i for i in ids if ids.count(i) > 1]}"


def test_every_experiment_id_follows_the_exp_nnn_convention():
    entries = _load_registry()
    for e in entries:
        assert _ID_PATTERN.match(e["experiment_id"]), f"{e['experiment_id']!r} does not match EXP-NNN"


def test_every_entry_has_all_required_fields():
    entries = _load_registry()
    for e in entries:
        missing = _REQUIRED_FIELDS - set(e.keys())
        assert not missing, f"{e['experiment_id']} is missing fields: {missing}"


def test_hypothesis_supported_uses_only_allowed_values():
    entries = _load_registry()
    allowed = {True, False, "directional", "n/a"}
    for e in entries:
        assert e["hypothesis_supported"] in allowed, (
            f"{e['experiment_id']}.hypothesis_supported={e['hypothesis_supported']!r} not in {allowed}"
        )
