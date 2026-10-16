"""Transparent lexical near-duplicate screening, not a semantic leakage guarantee."""

from collections import Counter, defaultdict
import re

from .data import load_split
from .io import write_json


def screen(root, threshold=0.9):
    rows = [
        r
        for s in ("train", "model_selection", "calibration", "policy", "test")
        for r in load_split(root, s)
    ]
    grams = []
    for row in rows:
        words = re.findall(r"\w+", row["context"].casefold())
        grams.append({tuple(words[i : i + 3]) for i in range(len(words) - 2)})
    inverse = defaultdict(list)
    matches = []
    for i, current in enumerate(grams):
        if len(current) < 8:
            continue
        candidates = Counter(
            j
            for gram in current
            for j in inverse[gram]
            if rows[j]["split"] != rows[i]["split"]
        )
        for j, intersection in candidates.items():
            score = intersection / (len(current) + len(grams[j]) - intersection)
            if score >= threshold:
                matches.append(
                    {
                        "left": rows[j]["id"],
                        "left_split": rows[j]["split"],
                        "right": rows[i]["id"],
                        "right_split": rows[i]["split"],
                        "jaccard": score,
                    }
                )
        for gram in current:
            inverse[gram].append(i)
    result = {
        "method": "lowercase word-trigram Jaccard",
        "threshold": threshold,
        "minimum_distinct_trigrams": 8,
        "cross_split_candidates": matches,
        "candidate_count": len(matches),
        "limitations": "Lexical screen; short passages and semantic paraphrases are not covered. Candidates require manual adjudication.",
    }
    write_json(root / "reports/data/near_duplicate_screen.json", result)
    return result
