"""
One-off repair script: an earlier version of cv-decode.py wrote the whole API
response dict (as a string) into the generated_text column. This script parses
those strings and splits them into proper generated_text + duration values.
No re-transcription needed. Safe to run multiple times.

Usage:
    python fix-csv.py /path/to/cv-valid-dev.csv
"""

import ast
import sys

import pandas as pd


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python fix-csv.py /path/to/cv-valid-dev.csv")
    path = sys.argv[1]

    df = pd.read_csv(path)
    if "duration" not in df.columns:
        df["duration"] = pd.NA

    fixed = 0
    for idx, value in df["generated_text"].items():
        if isinstance(value, str) and value.strip().startswith("{"):
            try:
                data = ast.literal_eval(value.strip())
            except (ValueError, SyntaxError):
                continue  # not a dict string — leave untouched
            df.at[idx, "generated_text"] = data.get("transcription", "")
            current = df.at[idx, "duration"]
            if data.get("duration") is not None and (
                pd.isna(current) or str(current).strip() == ""
            ):
                df.at[idx, "duration"] = float(data["duration"])
            fixed += 1

    df.to_csv(path, index=False)
    done = int((df["generated_text"].astype(str).str.strip() != "").sum())
    print(f"Repaired {fixed} rows. {done}/{len(df)} rows have generated_text.")
    print(df[["filename", "generated_text", "duration"]].head(3).to_string(index=False))


if __name__ == "__main__":
    main()
