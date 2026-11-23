"""Price table loading, prompt size, long-prompt tier and per-request cost.

The single copy of the price logic for the `usage` skill. Stdlib only, Python 3.9+.
"""
import json
import math
import os
import re

SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prices.json")
OVERRIDE_PATH = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"),
                             "usage", "prices.json")
FIELDS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
_DATE_SUFFIX = re.compile(r"-\d{8}$")


def _valid_entry(entry):
    if not isinstance(entry, dict):
        return False
    for f in FIELDS:
        v = entry.get(f)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0:
            return False
    lp = entry.get("long_prompt")
    if lp is not None:
        threshold = lp.get("threshold") if isinstance(lp, dict) else None
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not math.isfinite(threshold) \
                or threshold <= 0:
            return False
        if not _valid_entry({k: v for k, v in lp.items() if k != "threshold"}):
            return False
    return True


def _read_table(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, dict) or not models:
        raise ValueError("no 'models' object")
    bad = [m for m, e in models.items() if not _valid_entry(e)]
    if bad:
        raise ValueError("invalid entries: " + ", ".join(sorted(bad)))
    return data


class PriceTable:
    """Seed table with an optional per-model override merged over it."""

    def __init__(self, seed_path=SEED_PATH, override_path=OVERRIDE_PATH):
        seed = _read_table(seed_path)
        self.models = dict(seed["models"])
        self.seed_version = seed.get("version")
        self.override_version = None
        self.override_error = None
        self.override_notes = []
        if override_path and os.path.exists(override_path):
            try:
                over = _read_table(override_path)
            except (OSError, ValueError) as exc:
                self.override_error = f"{override_path}: {exc}"
            else:
                for model, entry in over["models"].items():
                    seed_entry = self.models.get(model)
                    if seed_entry is None:
                        self.override_notes.append(f"{model}: not in the seed table, added as a new model")
                    elif "long_prompt" in seed_entry and "long_prompt" not in entry:
                        entry = dict(entry, long_prompt=seed_entry["long_prompt"])
                        self.override_notes.append(f"{model}: no long_prompt in the override, kept the seed's tier")
                    self.models[model] = entry
                self.override_version = over.get("version") or "unversioned"

    def versions(self):
        out = {"seed": self.seed_version, "override": self.override_version}
        if self.override_error:
            out["override_error"] = self.override_error
        if self.override_notes:
            out["override_notes"] = self.override_notes
        return out

    def lookup(self, model):
        """Exact id first, then the id without a date suffix. None when unpriced."""
        if not model:
            return None
        if model in self.models:
            return self.models[model]
        return self.models.get(_DATE_SUFFIX.sub("", model))


def token_classes(usage):
    """The five token classes of one usage dict. A missing cache_creation dict counts as 5-minute writes."""
    usage = usage or {}
    cc = usage.get("cache_creation")
    if isinstance(cc, dict) and ("ephemeral_5m_input_tokens" in cc or "ephemeral_1h_input_tokens" in cc):
        c5 = cc.get("ephemeral_5m_input_tokens") or 0
        c1 = cc.get("ephemeral_1h_input_tokens") or 0
    else:
        c5, c1 = usage.get("cache_creation_input_tokens") or 0, 0
    return {
        "input": usage.get("input_tokens") or 0,
        "cache_write_5m": c5,
        "cache_write_1h": c1,
        "cache_read": usage.get("cache_read_input_tokens") or 0,
        "output": usage.get("output_tokens") or 0,
    }


def prompt_size(tokens):
    """Prompt = input + cache write + cache read."""
    return tokens["input"] + tokens["cache_write_5m"] + tokens["cache_write_1h"] + tokens["cache_read"]


def request_cost(table, model, tokens):
    """USD for one request, on the long-prompt tier when the prompt is above its threshold. None when unpriced."""
    entry = table.lookup(model)
    if entry is None:
        return None
    lp = entry.get("long_prompt")
    if lp and prompt_size(tokens) > lp["threshold"]:
        entry = lp
    return sum(tokens[f] * entry[f] for f in FIELDS) / 1e6
