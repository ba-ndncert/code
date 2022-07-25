import asyncio
import json
import logging
import os
import random
from typing import Awaitable, Dict

from aiohttp import ClientSession, ClientResponse, ClientError

from utils import log_msg, log_json, prompt, prompt_list

LEDGER_URL = os.getenv("LEDGER_URL")

EVENT_LOGGER = logging.getLogger("event")

class repr_json:
    def __init__(self, val):
        self.val = val

    def __repr__(self) -> str:
        if isinstance(self.val, str):
            return self.val
        return json.dumps(self.val, indent=4)

class Controller:
    def __init__(
        self,
        ident: str,
        internal_host: str,
        admin_port: int,
        role: str=None
    ):
        self.ident = ident
        self.internal_host = internal_host
        self.role = role

        self.client_session: ClientSession = ClientSession()

        rand_name = str(random.randint(100_000, 999_999))
        self.seed = ("00000000000000000000000000000000" + rand_name)[-32:]

        self.ledger_url = LEDGER_URL or "http://dev.greenlight.bcovrin.vonx.io"
        self.admin_url = f"http://{self.internal_host}:{admin_port}"

        self.commands = {}
        self.register_command("register_did", self.register_did)
        self.register_command("register_schema", self.register_schema, {"schema_name": False, "schema_attrs": True})


    async def register_did(
        self
    ):
        self.log(f"Registering {self.ident} ...")

        data = {
            "alias": self.ident,
            "role": "ENDORSER" if self.role == "endorser" else "",
            "seed": self.seed
        }

        async with self.client_session.post(
            self.ledger_url + "/register",
            json = data
        ) as resp:
            if resp.status != 200:
                raise Exception(
                    f"Error registering DID {data}, response code {resp.status}"
                )
            nym_info = await resp.json()
            self.did = nym_info["did"]
            self.log(f"nym_info: {nym_info}")
        self.log(f"Registered DID: {self.did}")

    async def register_schema_and_cred_def(
        self,
        schema_name,
        version,
        schema_attrs,
        tag=None
    ):
        schema_id = await self.register_schema(
            schema_name,
            version,
            schema_attrs
        )
        await self.register_cred_def(
            schema_id,
            schema_name,
            tag
        )

    async def register_schema(
        self,
        schema_name,
        schema_attrs,
        version="1.0"
    ):
        self.log(f"Registering schema {schema_name} ...")
        schema_body = {
            "schema_name": schema_name,
            "schema_version": version,
            "attributes": schema_attrs
        }
        schema_response = await self.admin_POST("/schemas", schema_body)
        log_json(json.dumps(schema_response), label="Schema:")
        await asyncio.sleep(2.0)
        if "schema_id" in schema_response:
            # schema is created directly
            schema_id = schema_response["schema_id"]
        else:
            # need to wait for the endorser process
            schema_response = {"schema_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(schema_response["schema_ids"]):
                schema_response = await self.admin_GET("/schemas/created")
                if 0 == len(schema_response["schema_ids"]):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            schema_id = schema_response["schema_ids"][0]
        log_msg("Schema ID:", schema_id)
        return schema_id

    async def register_cred_def(
        self,
        schema_id,
        schema_name,
        tag=None
    ):
        cred_def_tag = tag if tag else (self.ident + "." + schema_name).replace(" ", "_")
        self.log(f"Registering credential defintion {cred_def_tag} ...")
        cred_def_body = {
            "schema_id": schema_id,
            "support_revocation": False,
            "tag": cred_def_tag
        }
        cred_def_response = await self.admin_POST(
            "/credential-definitions", cred_def_body
        )
        await asyncio.sleep(2.0)
        if "credential_definition_id" in cred_def_response:
            # cred def is created directly
            cred_def_id = cred_def_response["credential_definition_id"]
        else:
            # need to wait for the endorser process
            cred_def_response = {"credential_definition_ids": []}
            attempts = 3
            while 0 < attempts and 0 == len(
                cred_def_response["credential_definition_ids"]
            ):
                cred_def_response = await self.admin_GET(
                    "/credential-definitions/created"
                )
                if 0 == len(
                    cred_def_response["credential_definition_ids"]
                ):
                    await asyncio.sleep(1.0)
                    attempts = attempts - 1
            cred_def_id = cred_def_response["credential_definition_ids"][0]
        log_msg("Cred def ID:", cred_def_id)
        return schema_id, cred_def_id

    async def admin_request(
        self, method, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        params = {k: v for (k, v) in (params or {}).items() if v is not None}
        async with self.client_session.request(
            method, self.admin_url + path, json=data, params=params, headers=headers
        ) as resp:
            resp_text = await resp.text()
            try:
                resp.raise_for_status()
            except Exception as e:
                # try to retrieve and print text on error
                raise Exception(f"Error: {resp_text}") from e
            if not resp_text and not text:
                return None
            if not text:
                try:
                    return json.loads(resp_text)
                except json.JSONDecodeError as e:
                    raise Exception(f"Error decoding JSON: {resp_text}") from e
            return resp_text

    async def admin_GET(
        self, path, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            EVENT_LOGGER.debug("Controller GET %s request to Agent", path)
            response = await self.admin_request(
                "GET", path, None, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from GET %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_POST(
        self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        try:
            EVENT_LOGGER.debug(
                "Controller POST %s request to Agent%s", path,
                (" with data: \n{}".format(repr_json(data)) if data else ""),
            )
            response = await self.admin_request(
                "POST", path, data, text, params, headers=headers
            )
            EVENT_LOGGER.debug(
                "Response from POST %s received: \n%s",
                path,
                repr_json(response),
            )
            return response
        except ClientError as e:
            self.log(f"Error during POST {path}: {str(e)}")
            raise

    async def terminate(self):
        await self.client_session.close()

    def handle_output(self, *output, source: str = None, **kwargs):
        end = "" if source else "\n"
        if source == "stderr":
            color = "fg:ansired"
        elif not source:
            color = "fg:ansiblue"
        else:
            color = None
        log_msg(*output, color=color, prefix="", end=end, **kwargs)

    def log(self, *msg, **kwargs):
        self.handle_output(*msg, **kwargs)

    async def command_prompt_loop(self):
        while True:
            command = await prompt(self.command_prompt_loop_text())
            yield command
    
    def command_prompt_loop_text(self):
        print("Select a command by its index or name:")
        for i, cmd_name in enumerate(self.commands):
            print(f"{i}: {cmd_name}")

    async def execute(self, command: str):
        if command.isdigit():
            index = int(command)
            if index >= len(self.commands):
                print(f"{command} is not a valid index.")
                return
            command = list(self.commands)[index]
        if not command in self.commands:
            print(f"{command} is not a valid command.")
            return
        await self.commands[command]()

    def register_command(self, name: str, coro: Awaitable, arg_dict: Dict[str, bool]=None):
        if not arg_dict:
            self.commands[name] = coro
        else:
            async def _f():
                args = {}
                for arg_name, is_list in arg_dict.items():
                    if is_list:
                        args[arg_name] = await prompt_list(f"Enter comma-separated values for {arg_name}: ")
                    else:
                        args[arg_name] = await prompt(f"Enter {arg_name}: ")
                await coro(**args)
            self.commands[name] = _f

