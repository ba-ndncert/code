import json
from attr import has

import prompt_toolkit
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.eventloop.defaults import use_asyncio_event_loop
from prompt_toolkit.formatted_text import FormattedText, PygmentsTokens
from prompt_toolkit.patch_stdout import patch_stdout

import pygments
from pygments.filter import Filter
from pygments.lexer import Lexer
from pygments.lexers.data import JsonLdLexer

class PrefixFilter(Filter):
    def __init__(self, **options):
        Filter.__init__(self, **options)
        self.prefix = options.get("prefix")

    def lines(self, stream):
        line = []
        for ttype, value in stream:
            if "\n" in value:
                parts = value.split("\n")
                value = parts.pop()
                for part in parts:
                    line.append((ttype, part))
                    line.append((ttype, "\n"))
                    yield line
                    line = []
            line.append((ttype, value))
        if line:
            yield line

    def filter(self, lexer, stream):
        if isinstance(self.prefix, str):
            prefix = ((pygments.token.Generic, self.prefix),)
        elif self.prefix:
            prefix = self.prefix
        else:
            prefix = ()
        for line in self.lines(stream):
            yield from prefix
            yield from line

def print_lexer(
    body: str, lexer: Lexer, label: str = None, prefix: str = None, indent: int = None
):
    prefix_str = prefix + " " if prefix else ""
    if prefix_str or indent:
        prefix_body = prefix_str + " " * (indent or 0)
        lexer.add_filter(PrefixFilter(prefix=prefix_body))
    tokens = list(pygments.lex(body, lexer=lexer))
    if label:
        fmt_label = [("fg:ansimagenta", label)]
        if prefix_str:
            fmt_label.insert(0, ("", prefix_str))
        print_formatted(FormattedText(fmt_label))
    print_formatted(PygmentsTokens(tokens))

def print_json(data, label: str = None, prefix: str = None, indent: int = 2):
    if isinstance(data, str):
        data = json.loads(data)
    data = json.dumps(data, indent=2)
    prefix_str = prefix or ""
    print_lexer(data, JsonLdLexer(), label=label, prefix=prefix_str, indent=indent)

def print_formatted(*args, **kwargs):
    prompt_toolkit.print_formatted_text(*args, **kwargs)

def print_ext(
    *msg,
    color: str = None,
    label: str = None,
    prefix: str = None,
    indent: int = None,
    **kwargs,
):
    prefix_str = prefix or ""
    if indent:
        prefix_str += " " * indent
    if color:
        msg = [(color, " ".join(map(str, msg)))]
        if prefix_str:
            msg.insert(0, ("", prefix_str + " "))
        if label:
            msg.insert(0, ("fg:ansimagenta", label + "\n"))
        print_formatted(FormattedText(msg), **kwargs)
        return
    if label:
        print(label, **kwargs)
    if prefix_str:
        msg = (prefix_str, *msg)
    print(*msg, **kwargs)


def log_msg(*msg, color="fg:ansimagenta", **kwargs):
    run_in_terminal(lambda: print_ext(*msg, color=color, **kwargs))

def log_json(data, **kwargs):
    run_in_terminal(lambda: print_json(data, **kwargs))

def prompt_init():
    if hasattr(prompt_init, "_called"):
        return
    prompt_init._called = True
    use_asyncio_event_loop()

async def prompt(*args, **kwargs):
    prompt_init()
    with patch_stdout():
        try:
            while True:
                tmp = await prompt_toolkit.prompt(*args, async_=True, **kwargs)
                if tmp:
                    break
            return tmp
        except EOFError:
            return None

async def prompt_list(*args, **kwargs):
    x = await prompt(*args, **kwargs)
    return x.replace(" ", "").split(",")

