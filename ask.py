"""Ask the assistant about its findings. Run `python run.py` first.

    python ask.py "why did Chennai-Bangalore get pricier in March 2025?"
    python ask.py --llm none "anything odd on Delhi-Jaipur in November?"
"""

import argparse

from costwatch.llm import load_llm
from costwatch.notes import load_notes
from costwatch.qa import answer, load_results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--llm", choices=["local", "none"], default="local")
    args = parser.parse_args()
    print(answer(args.question, load_results(), load_notes(), load_llm(args.llm)))


if __name__ == "__main__":
    main()
