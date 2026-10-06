"""Build (or rebuild) the retrieval index from the club data.

Usage:  python build_index.py [--retriever dense|bm25|hybrid]
The API also builds the index automatically on startup if it is missing or
out of date, so this is mainly for rebuilding ahead of a demo.
"""
import argparse
import logging

from rag import service
from rag.config import RETRIEVERS, settings

logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retriever", choices=RETRIEVERS, default=settings.retriever)
    args = parser.parse_args()

    retriever = service.init(rebuild=True, retriever_name=args.retriever)
    clubs = len({c["club_id"] for c in retriever.chunks})
    print(f"Built {retriever.name} index: {clubs} clubs, {len(retriever.chunks)} chunks")


if __name__ == "__main__":
    main()
