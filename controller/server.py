import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import Controller
from arg_parser import arg_parser

async def main(args):
    controller = Controller(
        ident="ServerController",
        internal_host="localhost",
        admin_port=8021
    )

    try:
        if args.interactive:
            async for command in controller.command_prompt_loop():
                await controller.execute(command)
        else:
            command = args.command
            if not command:
                print("No command specified.")
            else:
                await controller.execute(command)
    finally:
        terminated = await controller.terminate()

    await asyncio.sleep(1.0)

    if not terminated:
        os._exit(1)

if __name__ == "__main__":
    parser = arg_parser()
    args = parser.parse_args()

    try:
        asyncio.get_event_loop().run_until_complete(main(args))
    except KeyboardInterrupt:
        os._exit(1)