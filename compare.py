"""QAD comparison between two JSON exports."""

import json
import sys


def _normalize(val: str) -> list[str]:
    """Normalize possibly delimited values, accounting for None."""
    return sorted((val or "").split("|~|"))


def main() -> None:
    """Main method."""
    file1 = sys.argv[1]
    file2 = sys.argv[2]
    with open(file1) as f:
        file1_data = json.load(f)
    with open(file2) as f:
        file2_data = json.load(f)

    print(f"Keys in {file1}: {len(file1_data.keys())}")
    print(f"Keys in {file2}: {len(file2_data.keys())}")

    common_keys = file1_data.keys() & file2_data.keys()
    print(f"Comparing common keys: {len(common_keys)}")
    for ark in common_keys:
        file1_record = file1_data.get(ark)
        file2_record = file2_data.get(ark)
        # These should have the same keys...
        assert list(file1_record.keys()) == list(file2_record.keys())
        # Since they do, compare the values
        for key, val1 in file1_record.items():
            # Split and sort delimited values, accounting for None
            val1 = _normalize(val1)
            val2 = _normalize(file2_record[key])
            if val1 != val2:
                print(f"Mismatch in {ark} on {key}: {val1} != {val2}")


if __name__ == "__main__":
    main()
