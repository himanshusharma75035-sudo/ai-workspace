#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from app.config import TEAMS
from app.knowledge import knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description="Build isolated semantic indexes for organization knowledge")
    parser.add_argument("--team", choices=TEAMS, action="append", dest="teams")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(json.dumps(knowledge.rebuild_embeddings(args.teams, force=args.force), indent=2))


if __name__ == "__main__":
    main()
