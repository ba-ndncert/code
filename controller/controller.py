#!/usr/bin/env python3.9

import asyncio
import json
import logging
import os
import sys
from typing import Awaitable, Dict, List

from aiohttp import ClientSession, ClientResponse, ClientError

from utils import log_msg, log_json, prompt, prompt_list, prompt_opt, log

from arg_parser import arg_parser

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
        endpoint: str
    ):
        """ Initializes a controller for an Aries agent. The ledger url is read from the environment variable LEDGER_URL.

        Args:
            ident (str): The identity (name) of the controller
            endpoint (str): The endpoint under which the agent's admin page can be reached
        """
        self.ident = ident
        self.did = None

        self.client_session = None

        self.ledger_url = LEDGER_URL or "http://dev.greenlight.bcovrin.vonx.io"
        self.admin_url = endpoint

        self.commands = {}
        self.register_command("register_did", self.register_did)
        self.register_command("register_schema", self.register_schema, {"schema_name": "1", "schema_attrs": "+"})
        self.register_command("register_cred_def",  self.register_cred_def, {"schema_id": "1", "schema_name": "1", "tag": "?"})
        self.register_command(
            "offer_credential", 
            self.offer_credential, 
            {
                "connection_id": "1",
                "schema_id": "1",
                "cred_def_id": "1",
                "attributes_json": "1",
                "schema_issuer_did": "?"
            }
        )
        
    async def get_did(
        self
    ):
        """ Get the DID that the agent registered on the ledger. If no DID is registered yet, register_did() is called.

        Returns:
            did (str): The DID the agent registered on the ledger 
        """
        log("Getting public DID ...")
        
        if not self.did:
            self.register_did()
        
        log(f"Obtained DID: {self.did}")
        return self.did


    async def register_did(
        self
    ):  
        """ Register a DID for the agent on the ledger. Note that each time this method is invoked a new DID is assigned as public DID to the agent.

        Raises:
            Exception: DID could not be registered
        """
        log(f"Registering {self.ident} ...")
        
        data = {
            "alias": self.ident,
            "role": ""
        }
        
        resp = await self.admin_POST("/wallet/did/create")
        did = resp["result"]["did"]
        data["did"] = did
        verkey = resp["result"]["verkey"]
        data["verkey"] = verkey

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
            log(f"nym_info: {nym_info}")
            
        await self.admin_POST("/wallet/did/public", params = {"did": self.did})
        log(f"Registered DID: {self.did}")

    async def register_schema_and_cred_def(
        self,
        schema_name,
        schema_attrs,
        version="1.0",
        tag=None
    ):
        """ Register schema and associated credential definition on the ledger.

        Args:
            schema_name (str): Schema name
            schema_attrs (List[str]): Schema attributes
            version (str, optional): Schema version. Defaults to "1.0".
            tag (str, optional): Credential definition tag. Defaults to None.
            
        Returns:
            schema_id, credential_definition_id (str, str): Schema identifier and credential definition identifier
        """
        schema_id = await self.register_schema(
            schema_name,
            version,
            schema_attrs
        )
        return await self.register_cred_def(
            schema_id,
            schema_name,
            tag
        )

    async def register_schema(
        self,
        schema_name: str,
        schema_attrs: List[str],
        version="1.0"
    ):
        """ Register schema on the ledger.

        Args:
            schema_name (str): Schema name
            schema_attrs (List[str]): Schema attributes
            version (str, optional): Schema version. Defaults to "1.0".

        Returns:
            schema_id (str): Schema identifier
        """
        log(f"Registering schema {schema_name} ...")
        schema_body = {
            "schema_name": schema_name,
            "schema_version": version,
            "attributes": schema_attrs
        }
        schema_response = await self.admin_POST("/schemas", schema_body)
        log_json(json.dumps(schema_response), label="Schema:")
        await asyncio.sleep(2.0)
        print(schema_response)
        print(schema_response.keys())
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
        schema_id: str,
        schema_name: str,
        tag: str = None
    ):
        """ Register credential definition on the ledger.

        Args:
            schema_id (str): Schema identifier
            schema_name (str): Schema name
            tag (str, optional): Credential defintion tag. Defaults to None.

        Returns:
            schema_id, credential_definition_id (str, str): Schema identifier and credential definition identifier
        """
        cred_def_tag = tag if tag else (self.ident + "." + schema_name).replace(" ", "_")
        log(f"Registering credential defintion {cred_def_tag} ...")
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
    
    async def offer_credential(
        self, 
        connection_id: str, 
        schema_id: str, 
        cred_def_id: str, 
        attributes_json: str, 
        schema_issuer_did: str = None
    ):
        """ Offer a credential to a holder using the issue-credentials-2.0 protocol

        Args:
            connection_id (str): Connection identifier of the connection to the holder
            schema_id (str): Schema identifier of the offered credential
            cred_def_id (str): Credential definition identifier of the offered credential
            attributes_json (str): attributes field of the credential_preview field of the request body in JSON format 
            schema_issuer_did (str, optional): DID of the schema issuer. Defaults to None. Then, the issuer DID is expected to be equal to the schema issuer DID
        """
        log("Issuing credential ...")
        issuer_did = await self.get_did()
        schema_id_comps = schema_id.split(":")
        schema_name = schema_id_comps[-2]
        schema_version = schema_id_comps[-1]
        schema_issuer_did = issuer_did if not schema_issuer_did else schema_issuer_did
        log(f"schema_name: {schema_name}")
        log(f"schema_version: {schema_version}")
        log(f"schema_issuer_did: {schema_issuer_did}")
        issue_cred_body = {
            "auto_remove": True,
            "comment": "string",
            "connection_id": connection_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": json.loads(attributes_json)
            },
            "filter": {
                "indy": {
                    "cred_def_id": cred_def_id,
                    "issuer_did": issuer_did,
                    "schema_id": schema_id,
                    "schema_issuer_did": schema_issuer_did,
                    "schema_name": schema_name,
                    "schema_version": schema_version
                }
            }
        }
        resp = await self.admin_POST("/issue-credential-2.0/send-offer", data=issue_cred_body)
        log(f"Offered credential with \ncred_ex_id: {resp['cred_ex_id']}\nthread_id: {resp['thread_id']}")
        

    async def admin_request(
        self, method, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        """ Send a HTTP request to the agent's admin endpoint

        Args:
            method (str): HTTP Verb
            path (str): URL path relative to the admin endpoint
            data (Dict, optional): Request body. Defaults to None.
            text (bool, optional): If True return response as str, otherwise return response as Dict. Defaults to False.
            params (Dict, optional): URL parameters. Defaults to None.
            headers (Dict, optional): Request headers. Defaults to None.

        Raises:
            Exception: HTTP request failed
            Exception: Response can not be decoded to JSON

        Returns:
            ClientResponse: str or Dict representing the response; depends on text argument
        """
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
        """ Send a HTTP GET request to the agent's admin endpoint

        Args:
            path (str): URL path relative to the admin endpoint
            text (bool, optional): If True return response as str, otherwise return response as Dict. Defaults to False.
            params (Dict, optional): URL parameters. Defaults to None.
            headers (Dict, optional): Request headers. Defaults to None.

        Returns:
            ClientResponse: str or Dict representing the response; depends on text argument
        """
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
            log(f"Error during GET {path}: {str(e)}")
            raise

    async def admin_POST(
        self, path, data=None, text=False, params=None, headers=None
    ) -> ClientResponse:
        """ Send a HTTP POST request to the agent's admin endpoint.

        Args:
            path (str): URL path relative to the admin endpoint
            data (Dict, optional): Request body. Defaults to None.
            text (bool, optional): If True return response as str, otherwise return response as Dict. Defaults to False.
            params (Dict, optional): URL parameters. Defaults to None.
            headers (Dict, optional): Request headers. Defaults to None.

        Returns:
            ClientResponse: str or Dict representing the response; depends on text argument
        """
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
            log(f"Error during POST {path}: {str(e)}")
            raise

    async def terminate(self):
        """ Close the aiohttp client session. This method should be called on controller shutdown.
        """
        await self.client_session.close()

    async def command_prompt_loop(self):
        """ The following steps are repeated as long as the application is running: 
        Print out all available commands, wait for user input and execute the selected command. 

        Yields:
            Selected command in each iteration
        """
        while True:
            command = await prompt(self.command_prompt_loop_text())
            yield command
    
    def command_prompt_loop_text(self):
        """ Prints out all available commands
        """
        print("Select a command by its index or name:")
        for i, cmd_name in enumerate(self.commands):
            print(f"{i}: {cmd_name}")

    async def execute(self, command: str):
        """ Execute a command

        Args:
            command (str): If command can be cast to digit n the (n-1)th command is executed, else the command with name command is executed
        """
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

    def register_command(self, name: str, coro: Awaitable, arg_dict: Dict[str, str]=None):
        """ Register a command that can be executed with self.execute(command)

        Args:
            name (str): Command name
            coro (Awaitable): Async command method
            arg_dict (Dict[str, str], optional): Dict mapping argument names to argument specifications. An argument specification describes the accepted format for an argument:
            "1": Exact one string is expected
            "?": One or less string are expected
            "+": A list of strings is expected
            This method wraps coro with a helper method that executes a prompt for each argument and handling user input depending on the argument specification

        Raises:
            ValueError: _description_
        """
        if not arg_dict:
            self.commands[name] = coro
        else:
            # Define wrapper method that executes a prompt for each argument
            async def coro_with_prompt():
                args = {}
                for arg_name, arg_type in arg_dict.items():
                    if arg_type == "1":
                        args[arg_name] = await prompt(f"Enter {arg_name}: ")
                    elif arg_type == "?":
                        args[arg_name] = await prompt_opt(f"Enter {arg_name} or press <ENTER> to skip: ")
                    elif arg_type == "+":
                        args[arg_name] = await prompt_list(f"Enter comma-separated values for {arg_name}: ")
                    else:
                        raise ValueError(f"arg_type must be in ['1', '?', '+'] but is {arg_type}")
                await coro(**args)
            self.commands[name] = coro_with_prompt
            
    async def main(self, args):        
        self.client_session = ClientSession()

        try:
            if args.interactive:
                async for command in self.command_prompt_loop():
                    await self.execute(command)
            else:
                command = args.command
                if not command:
                    print("No command specified.")
                else:
                    await self.execute(command)
        finally:
            terminated = await self.terminate()

        await asyncio.sleep(1.0)

        if not terminated:
            os._exit(1)

if __name__ == "__main__":
    controller = Controller(
        ident="ServerController",
        endpoint="http://localhost:8121"
    )
    
    parser = arg_parser()
    args = parser.parse_args()
    
    try:
        asyncio.run(controller.main(args))
    except KeyboardInterrupt:
        sys.exit()

