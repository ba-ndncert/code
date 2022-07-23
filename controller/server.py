import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller import Controller

async def main():
    try:
        controller = Controller(
            ident="ServerController",
            internal_host="localhost",
            admin_port=8021
        )
        await controller.register_did()
        await controller.register_schema_and_cred_def(
            schema_name="NDNSchema2",
            schema_attrs=["Attr1", "Attr2"],
            version="1.0"
        )
    finally:
        terminated = await controller.terminate()

    await asyncio.sleep(1.0)

    if not terminated:
        os._exit(1)

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        os.exit(1)