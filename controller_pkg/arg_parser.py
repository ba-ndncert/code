import argparse

def controller_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run controller in interactive mode"
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available commands"
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Run a command by its name or index"
    )
    parser.add_argument(
        "--endpoint",
        default = "http://localhost:8121",
        help="URL of Aries cloud agent admin panel"
    )
    parser.add_argument(
        "--env_path",
        # assume that .env file is one folder up
        default="./../.env",
        help="Path to environment file"
    )
    return parser

def setup_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--env_path",
        # assume that .env file is one folder up
        default="./../.env",
        help="Path to environment file"
    )
    parser.add_argument(
        "--schema_name",
        default="my_schema",
        help="Schema name"
    )
    parser.add_argument(
        "--schema_attrs",
        default="name,age",
        type=str,
        help="Comma-separated schema attributes"
    )
    return parser