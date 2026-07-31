"""
Task 4e — index the transcribed Common Voice metadata (cv-valid-dev.csv,
including the generated_text column produced in Task 2d) into the
2-node Elasticsearch cluster from docker-compose.yml.

Usage:
    python cv-index.py --csv /path/to/common_voice/cv-valid-dev.csv \
                       --es-url http://localhost:9200 \
                       --index cv-transcriptions

Notes / assumptions:
  * The assignment mentions "cs-valid-dev.csv"; this is assumed to be a typo
    for cv-valid-dev.csv (the file produced in Task 2d).
  * Document _id = the row's filename, so re-running the script is idempotent
    (documents are overwritten, never duplicated).
  * `duration` is indexed as float; empty/invalid values are indexed as null.
  * age / gender / accent are keyword fields (exact facet filtering) with a
    .text subfield is unnecessary — Search-UI facets work on keywords.
    generated_text and text are full-text fields with keyword subfields.
"""

import argparse
import sys

import pandas as pd
from elasticsearch import Elasticsearch, helpers

MAPPING = {
    "properties": {
        "filename":       {"type": "keyword"},
        "text":           {"type": "text"},                       # ground-truth transcript
        "generated_text": {"type": "text",                        # ASR output (Task 2)
                           "fields": {"keyword": {"type": "keyword", "ignore_above": 512}}},
        "up_votes":       {"type": "integer"},
        "down_votes":     {"type": "integer"},
        "age":            {"type": "keyword"},
        "gender":         {"type": "keyword"},
        "accent":         {"type": "keyword"},
        "duration":       {"type": "float"},
    }
}

SETTINGS = {"number_of_shards": 2, "number_of_replicas": 1}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index cv-valid-dev.csv into Elasticsearch")
    parser.add_argument("--csv", default="cv-valid-dev.csv", help="Path to the transcribed CSV")
    parser.add_argument("--es-url", default="http://localhost:9200", help="Elasticsearch URL")
    parser.add_argument("--index", default="cv-transcriptions", help="Index name")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete and recreate the index before indexing")
    return parser.parse_args()


def to_float(value):
    """float or None (ES rejects NaN); '' -> None."""
    try:
        result = float(value)
        return result if result == result else None  # NaN check
    except (TypeError, ValueError):
        return None


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def clean_str(value):
    """Return a stripped string, or None for NaN/empty (so ES stores null)."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    text = str(value).strip()
    return text or None


def generate_actions(df: pd.DataFrame, index: str):
    for _, row in df.iterrows():
        yield {
            "_index": index,
            "_id": str(row["filename"]),          # idempotent re-runs
            "_source": {
                "filename":       clean_str(row.get("filename")),
                "text":           clean_str(row.get("text")),
                "generated_text": clean_str(row.get("generated_text")),
                "up_votes":       to_int(row.get("up_votes")),
                "down_votes":     to_int(row.get("down_votes")),
                "age":            clean_str(row.get("age")),
                "gender":         clean_str(row.get("gender")),
                "accent":         clean_str(row.get("accent")),
                "duration":       to_float(row.get("duration")),
            },
        }


def main() -> None:
    args = parse_args()

    df = pd.read_csv(args.csv)
    if "generated_text" not in df.columns:
        print("WARNING: no generated_text column found — run asr/cv-decode.py first.",
              file=sys.stderr)

    es = Elasticsearch(args.es_url, request_timeout=60)
    if not es.ping():
        sys.exit(f"ERROR: cannot reach Elasticsearch at {args.es_url}")

    if args.recreate and es.indices.exists(index=args.index):
        es.indices.delete(index=args.index)
        print(f"Deleted existing index {args.index}")

    if not es.indices.exists(index=args.index):
        es.indices.create(index=args.index, mappings=MAPPING, settings=SETTINGS)
        print(f"Created index {args.index} (2 shards, 1 replica)")

    ok_count, err_count = 0, 0
    for ok, item in helpers.streaming_bulk(
        es, generate_actions(df, args.index), chunk_size=500,
        raise_on_error=False, max_retries=3,
    ):
        if ok:
            ok_count += 1
        else:
            err_count += 1
            if err_count <= 5:
                print("Bulk error:", item, file=sys.stderr)

    es.indices.refresh(index=args.index)
    total = es.count(index=args.index)["count"]
    print(f"Indexed {ok_count} docs ({err_count} errors). "
          f"Index {args.index} now holds {total} documents.")
    if err_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
