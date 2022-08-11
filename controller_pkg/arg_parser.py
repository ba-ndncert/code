import argparse

def controller_parser():
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
    parser.add_argument(
        "--endpoint",
        default = "http://localhost:8121"
    )
    return parser

def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--register_did",
        type=bool,
        default=False 
    )
    parser.add_argument(
        "--env_path",
        # assume that .env file is one folder up
        default="./../.env"
    )
    parser.add_argument(
        "--schema_name",
        default="my_schema"
    )
    parser.add_argument(
        "--schema_attrs",
        default="name,age",
        type=str
    )
    return parser