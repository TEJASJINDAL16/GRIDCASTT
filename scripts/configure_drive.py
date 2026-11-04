"""Import Desktop OAuth credentials into local DVC settings; never print secrets."""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.config import configure_gdrive_oauth


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_file", type=pathlib.Path)
    args = parser.parse_args()
    try:
        configure_gdrive_oauth(args.client_file)
    except Exception:
        # Parser and library exceptions may include credential values; do not echo them.
        print(
            "OAuth import failed. Check that the input is a valid Desktop client JSON.",
            file=sys.stderr,
        )
        return 1
    print("Local DVC OAuth settings updated. A fresh browser authorization is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
