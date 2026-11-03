"""One batch run; retries make at most one attempt and never sleep."""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.jobs.daily import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--at")
    args = parser.parse_args()
    result = run(now=args.at, offline=args.offline, retry=args.retry)
    print(result.get("outcome", "no retry needed"))
    if result.get("outcome") == "failed" or result.get("alerts"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
