"""Command-line entry point for the IRIS-SIG-29 harvester."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .client import HttpClient
from .config import (
    DEFAULT_FIXTURES_DIR,
    DEFAULT_GAZETTEER_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PROJECTS,
    PROJECT_ROOT,
    Settings,
)
from .errors import DatabaseLoadError, HarvesterError
from .geocoding import Gazetteer, Geocoder
from .harvester import Harvester
from .parser import FiftyHertzParser
from .storage import load_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iris-harvester",
        description="Extract 50Hertz offshore grid-connection signals into iris_staging.signal_ingest.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--offline",
        action="store_true",
        help="parse the saved fixtures (default, no network)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="fetch the project pages live, honouring robots.txt and a request delay",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="directory containing the captured HTML fixtures",
    )
    parser.add_argument(
        "--gazetteer",
        type=Path,
        default=DEFAULT_GAZETTEER_PATH,
        help="CSV gazetteer (name,lat,lon,precision,source)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="JSONL artifact path",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="PostgreSQL DSN; defaults to IRIS_DATABASE_URL",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="write the JSONL artifact without touching PostgreSQL",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=None,
        help="minimum seconds between live HTTP requests",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    settings = Settings.from_env(args.dsn)
    if args.request_delay is not None:
        settings = Settings(
            database_url=settings.database_url,
            request_delay_seconds=args.request_delay,
            http_timeout_seconds=settings.http_timeout_seconds,
            http_retries=settings.http_retries,
            user_agent=settings.user_agent,
        )

    try:
        gazetteer = Gazetteer.from_csv(args.gazetteer)
        geocoder = Geocoder(gazetteer)
    except HarvesterError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 1

    client = HttpClient(settings) if args.live else None
    harvester = Harvester(FiftyHertzParser(), geocoder, client=client)

    if args.live:
        result = harvester.run_live(DEFAULT_PROJECTS)
        mode = "live"
    else:
        result = harvester.run_offline(args.fixtures_dir, DEFAULT_PROJECTS)
        mode = "offline"

    _write_artifact(args.output, result.records)

    print("IRIS-SIG-29 50Hertz harvester")
    print(f"mode={mode} sources={len(DEFAULT_PROJECTS)}")
    print(
        f"parsed={len(result.records)} errors={len(result.errors)} "
        f"capacity_present={sum(r.capacity_mw is not None for r in result.records)} "
        f"capacity_missing={sum(r.capacity_mw is None for r in result.records)}"
    )
    counts = result.geom_counts
    print(
        "geometry="
        f"resolved:{counts.get('resolved', 0)} "
        f"approximate:{counts.get('approximate', 0)} "
        f"unresolved:{counts.get('unresolved', 0)} "
        f"invalid:{counts.get('invalid', 0)}"
    )
    for error in result.errors:
        print(f"error source={error.source!r} type={error.error_type} message={error.message}")
    print(f"output={args.output} records={len(result.records)}")

    if args.no_db:
        print("database=skipped (--no-db)")
    elif not settings.database_url:
        print("database=skipped (IRIS_DATABASE_URL not set)")
    else:
        try:
            with psycopg.connect(settings.database_url, connect_timeout=5) as connection:
                loaded = load_records(connection, result.records)
        except (psycopg.Error, DatabaseLoadError) as exc:
            print(f"database error: {exc}", file=sys.stderr)
            return 1
        print(
            f"database=loaded inserted={loaded.inserted} "
            f"updated={loaded.updated} unchanged={loaded.unchanged}"
        )

    return 0 if not result.errors else 2


def _write_artifact(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    record.to_artifact(),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            handle.write("\n")
    tmp.replace(path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
