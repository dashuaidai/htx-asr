"""
Evaluate ASR quality: compute Word Error Rate (WER) of generated_text against
the ground-truth text column in cv-valid-dev.csv (after running cv-decode.py).

    python compute-wer.py --csv /path/to/cv-valid-dev.csv

Outputs corpus-level WER plus breakdowns by accent, gender and duration —
useful for spotting subgroup degradation (see essay.pdf: concept drift should
be measured stratified, not only on the average).

WER = (substitutions + deletions + insertions) / reference_word_count,
computed corpus-level (total edits / total reference words). Text is
normalised before scoring: lower-cased, punctuation stripped (apostrophes
kept), whitespace collapsed — the ground truth is lower-case while the model
emits upper-case, so scoring raw strings would be meaningless.

Pure-Python implementation (word-level Levenshtein distance); no external
WER library needed.
"""

import argparse
import re
import sys

import pandas as pd

_norm_re = re.compile(r"[^a-z0-9' ]+")


def normalize(text) -> list[str]:
    """Lower-case, strip punctuation (keep apostrophes), split into words."""
    if text is None or (isinstance(text, float) and text != text):
        return []
    text = str(text).lower()
    text = _norm_re.sub(" ", text)
    return text.split()


def edit_distance(ref: list[str], hyp: list[str]) -> int:
    """Word-level Levenshtein distance (= S + D + I for the best alignment)."""
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    # Two-row dynamic programming to keep memory small.
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i] + [0] * len(hyp)
        for j, hyp_word in enumerate(hyp, start=1):
            current[j] = min(
                previous[j] + 1,                                   # deletion
                current[j - 1] + 1,                                # insertion
                previous[j - 1] + (ref_word != hyp_word),          # substitution/match
            )
        previous = current
    return previous[-1]


def corpus_wer(frame: pd.DataFrame) -> tuple[float, int, int]:
    """Return (wer, total_edits, total_ref_words) for a dataframe slice."""
    total_edits, total_words = 0, 0
    for _, row in frame.iterrows():
        ref = normalize(row["text"])
        hyp = normalize(row["generated_text"])
        total_edits += edit_distance(ref, hyp)
        total_words += len(ref)
    return (total_edits / total_words if total_words else 0.0), total_edits, total_words


def duration_bucket(value) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if seconds != seconds:  # NaN
        return "unknown"
    if seconds < 3:
        return "0-3 s"
    if seconds < 5:
        return "3-5 s"
    if seconds < 8:
        return "5-8 s"
    return "8 s +"


def print_breakdown(df: pd.DataFrame, column: str, title: str) -> None:
    print(f"\nWER by {title}:")
    groups = df.groupby(column, dropna=False)
    rows = []
    for key, frame in groups:
        wer, _, words = corpus_wer(frame)
        label = "(missing)" if (key is None or (isinstance(key, float) and key != key)) else str(key)
        rows.append((wer, label, len(frame), words))
    for wer, label, count, _ in sorted(rows):
        print(f"  {label:<15} {wer:7.2%}   ({count} clips)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute WER for cv-valid-dev.csv")
    parser.add_argument("--csv", default="cv-valid-dev.csv",
                        help="CSV with text and generated_text columns")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    for column in ("text", "generated_text"):
        if column not in df.columns:
            sys.exit(f"ERROR: column '{column}' not found in {args.csv}")

    empty = int((df["generated_text"].astype(str).str.strip() == "").sum()
                + df["generated_text"].isna().sum())

    wer, edits, words = corpus_wer(df)
    print(f"Clips scored:        {len(df)} ({empty} with empty generated_text)")
    print(f"Reference words:     {words}")
    print(f"Total word errors:   {edits}")
    print(f"Corpus WER:          {wer:.2%}")

    if "accent" in df.columns:
        print_breakdown(df, "accent", "accent")
    if "gender" in df.columns:
        print_breakdown(df, "gender", "gender")
    if "duration" in df.columns:
        df = df.assign(_bucket=df["duration"].map(duration_bucket))
        print_breakdown(df, "_bucket", "duration")


if __name__ == "__main__":
    main()
