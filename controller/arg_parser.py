import argparse

def arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run controller in interactive mode"
    )
    parser.add_argument(
        "command",
        nargs="?"
    )
    return parser