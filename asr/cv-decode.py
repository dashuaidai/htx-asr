"""
Task 2d — batch-transcribe the Common Voice cv-valid-dev set (4,076 mp3 files)
by calling the ASR API from Task 2b/2c, and write the results into a new
`generated_text` column of cv-valid-dev.csv.

Usage (defaults match the assignment's layout):
    python cv-decode.py \
        --csv       /path/to/common_voice/cv-valid-dev.csv \
        --audio-dir /path/to/common_voice \
        --api-url   http://localhost:8001/asr \
        --workers   4

Notes / assumptions:
  * The dataset CSV has a `filename` column with relative paths such as
    "cv-valid-dev/sample-000000.mp3"; `--audio-dir` is the directory those
    paths are relative to (the folder that *contains* cv-valid-dev/).
  * The updated CSV is saved back to the same file (in the same folder), as
    required by the assignment. Use --output to write elsewhere.
  * The script is resumable: rows that already have a non-empty
    generated_text are skipped, and progress is checkpointed every
    --checkpoint-every completed files. Safe to Ctrl-C and re-run.
  * Failed files (unreadable audio / repeated API errors) are left with an
    empty generated_text and reported at the end.
"""

import argparse
import concurrent.futures
import os
import sys
import threading
import time

import pandas as pd
import requests
from tqdm import tqdm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch transcription client for the ASR API")
    parser.add_argument("--csv", default="common_voice/cv-valid-dev.csv",
                        help="Path to cv-valid-dev.csv")
    parser.add_argument("--audio-dir", default="common_voice",
                        help="Directory the CSV's `filename` column is relative to")
    parser.add_argument("--api-url", default="http://localhost:8001/asr",
                        help="ASR API endpoint")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of concurrent requests")
    parser.add_argument("--retries", type=int, default=3,
                        help="Retries per file on API/network errors")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Per-request timeout in seconds")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="Save the CSV after this many new transcriptions")
    parser.add_argument("--output", default=None,
                        help="Optional output CSV path (default: overwrite --csv)")
    return parser.parse_args()


def transcribe_one(session: requests.Session, api_url: str, path: str,
                   retries: int, timeout: int) -> dict:
    """Send one audio file to the ASR API; return the JSON response
    ({"transcription": ..., "duration": ...})."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with open(path, "rb") as fh:
                response = session.post(
                    api_url,
                    files={"file": (os.path.basename(path), fh, "audio/mpeg")},
                    timeout=timeout,
                )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # network error, HTTP error, bad JSON …
            last_error = exc
            time.sleep(min(2 ** attempt, 10))  # exponential backoff
    raise RuntimeError(f"{path}: failed after {retries} attempts: {last_error}")


def main() -> None:
    args = parse_args()
    output_path = args.output or args.csv

    df = pd.read_csv(args.csv)
    if "filename" not in df.columns:
        sys.exit(f"ERROR: no `filename` column in {args.csv}")

    # Resume support: keep any transcriptions from a previous (partial) run.
    if "generated_text" not in df.columns:
        df["generated_text"] = ""
    df["generated_text"] = df["generated_text"].fillna("")

    # Assumption: the dataset's `duration` column is empty; since the API also
    # returns the duration, we backfill it (used as a search field in Task 5).
    if "duration" not in df.columns:
        df["duration"] = pd.NA

    pending = [
        (idx, os.path.join(args.audio_dir, str(row.filename)))
        for idx, row in df.iterrows()
        if not str(row.generated_text).strip()
    ]
    print(f"{len(df)} rows total, {len(df) - len(pending)} already done, "
          f"{len(pending)} to transcribe with {args.workers} workers.")

    session = requests.Session()
    lock = threading.Lock()          # guards df writes + checkpointing
    completed_since_save = 0
    failures: list[str] = []

    def worker(item: tuple[int, str]) -> None:
        nonlocal completed_since_save
        idx, path = item
        try:
            result = transcribe_one(session, args.api_url, path, args.retries, args.timeout)
        except Exception as exc:
            with lock:
                failures.append(str(exc))
            return
        with lock:
            df.at[idx, "generated_text"] = result["transcription"]
            # Backfill duration only if the dataset didn't provide one.
            current = df.at[idx, "duration"]
            if result.get("duration") is not None and (
                pd.isna(current) or str(current).strip() == ""
            ):
                df.at[idx, "duration"] = float(result["duration"])
            completed_since_save += 1
            if completed_since_save >= args.checkpoint_every:
                df.to_csv(output_path, index=False)
                completed_since_save = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(tqdm(pool.map(worker, pending), total=len(pending), unit="file"))

    df.to_csv(output_path, index=False)  # final save
    done = int((df["generated_text"].astype(str).str.strip() != "").sum())
    print(f"Done: {done}/{len(df)} rows have generated_text. Saved to {output_path}")

    if failures:
        print(f"\n{len(failures)} file(s) failed:", file=sys.stderr)
        for line in failures[:20]:
            print("  -", line, file=sys.stderr)
        if len(failures) > 20:
            print(f"  ... and {len(failures) - 20} more", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
