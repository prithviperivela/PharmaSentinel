import argparse
import json
from pathlib import Path

from pharmasentinel.comparison import compare

parser = argparse.ArgumentParser()
parser.add_argument("--first", default="baseline")
parser.add_argument("--second", default="biomedbert")
parser.add_argument(
    "--split", choices=["model_selection", "policy", "test"], default="policy"
)
args = parser.parse_args()
print(
    json.dumps(
        compare(
            Path(__file__).resolve().parents[1], args.first, args.second, args.split
        ),
        indent=2,
    )
)
