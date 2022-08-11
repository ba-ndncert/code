import argparse
import asyncio
import os
import random
import sys

from aiohttp import ClientSession
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller_pkg.arg_parser import setup_parser
from controller_pkg.controller import Controller
from controller_pkg.utils import log

class Setup:
    def __init__(
        self,
        server_controller: Controller,
        client_controller: Controller
    ):
        self.server_controller = server_controller
        self.client_controller = client_controller
        
    def log(self, msg):
        log(f"Setup: {msg}", color="fg:ansigreen")
    
    async def register_did(self):
        await self.server_controller.register_did()
        await self.client_controller.register_did()
        
    async def exchange_connection(self):
        resp = await self.server_controller.create_invitation()
        invitation = resp["invitation"]
        resp = await self.client_controller.receive_invitation(invitation)
        client_connection_id = resp["connection_id"]
        resp = await self.client_controller.request_invitation(client_connection_id)
        client_connection_did = resp["my_did"]
        while not await self.server_controller.has_connection(params={"their_did": client_connection_did}):
            self.server_controller.log(f"Wait for connection with their_did: {client_connection_did}")
            await asyncio.sleep(1.0)
        resp = await self.server_controller.accept_invitation(client_connection_did)
        server_connection_id = resp["connection_id"]
        return server_connection_id, client_connection_id
          
    async def register_schema_and_cred_def(self, schema_name, schema_attrs, cred_def_tag):
        return await self.server_controller.register_schema_and_cred_def(
            schema_name=schema_name,
            schema_attrs=schema_attrs,
            tag=cred_def_tag
        )
        
    async def exchange_credential(
        self, connection_id, schema_id, cred_def_id, attributes_json
    ):
        # Offer credential
        _, thread_id = await self.server_controller.offer_credential(
            connection_id=connection_id,
            schema_id=schema_id,
            cred_def_id=cred_def_id,
            attributes_json=attributes_json
        )
        
        # Request credential
        while not await self.client_controller.has_credential_exchange_record(params={"thread_id": thread_id}):
            self.client_controller.log(f"Wait for credential offer with thread_id: {thread_id}")
            await asyncio.sleep(1.0)
        await self.client_controller.request_credential(thread_id)
        
        # Issue credential
        while not await self.server_controller.has_credential_exchange_record(
            params={"thread_id": thread_id, "state": "request-received"}
        ):
            self.server_controller.log(f"Wait for credential request with thread_id: {thread_id}")
            await asyncio.sleep(0.01)
        await self.server_controller.issue_credential(thread_id)

async def main(args):
    # load environment variables from .env file
    load_dotenv(args.env_path)
    
    server_controller = Controller(
        ident = "ServerController",
        endpoint = f"http://{os.getenv('SERVER_AGENT_IP')}:{os.getenv('SERVER_AGENT_ADMIN_PORT')}",
        ledger_url=os.getenv("LEDGER_URL") or "http://dev.greenlight.bcovrin.vonx.io"
    )
    server_controller.client_session = ClientSession()
            
    client_controller = Controller(
        ident = "ClientController",
        endpoint = f"http://{os.getenv('CLIENT_AGENT_IP')}:{os.getenv('CLIENT_AGENT_ADMIN_PORT')}",
        ledger_url=os.getenv("LEDGER_URL") or "http://dev.greenlight.bcovrin.vonx.io"
    )
    client_controller.client_session = ClientSession()
    
    setup = Setup(
        server_controller=server_controller,
        client_controller=client_controller
    )
    
    try:
        setup.log("Establish connection between client and server agent")
        server_connection_id, _ = await setup.exchange_connection()
        setup.log("Register schema and credential definition from server agent")
        schema_id, cred_def_id = await setup.register_schema_and_cred_def(
            schema_name=args.schema_name,
            schema_attrs=str(args.schema_attrs).replace(" ", "").split(","),
            # Credential definitions can't be reassigned to an agent. Therefore, a random tag is generated. See:
            # https://github.com/hyperledger/aries-cloudagent-python/issues/506
            cred_def_tag=str(random.randint(0,1e6))
        )
        setup.log("Issue credential from server agent to client agent")
        await setup.exchange_credential(
            connection_id=server_connection_id,
            schema_id=schema_id,
            cred_def_id=cred_def_id,
            attributes_json=await setup.server_controller.build_cred_preview_attributes_json(
                schema_id
            )
        )
    finally:
        await server_controller.client_session.close()
        await client_controller.client_session.close()
    
    

if __name__ == "__main__":  
    parser = setup_parser()
    args = parser.parse_args()
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        sys.exit()