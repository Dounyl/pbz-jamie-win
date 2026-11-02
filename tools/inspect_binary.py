"""Read relevant reflected symbol strings; never modify the game executable."""
import argparse
import mmap
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".local/research/binary-symbols.txt"))
    args = parser.parse_args()
    interesting = re.compile(
        r"drunk|tipsy|inebri|intoxic|runtimeaudio|importaudio|"
        r"(?:^|[_.])(?:PBZ)?Execution|GetExecution|CurrentExecution|"
        r"^E.*Execution|^On.*Execution|^.*Execution.*(?:State|Info|Component|Notify|End|Finish)$",
        re.I,
    )
    found = set()
    with args.binary.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for pattern, encoding in [(rb"(?:[\x20-\x7e]\x00){5,}", "utf-16-le"), (rb"[\x20-\x7e]{5,}", "ascii")]:
            for match in re.finditer(pattern, data):
                text = match.group().decode(encoding)
                if len(text) <= 160 and interesting.search(text):
                    found.add(text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sorted(found)) + "\n", encoding="utf-8")
    print(f"Saved {len(found)} candidates to {args.output}; names alone do not prove behavior.")


if __name__ == "__main__":
    main()
