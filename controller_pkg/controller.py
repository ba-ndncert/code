#!/usr/bin/env python3.9

import asyncio
import json
import logging
import sys
from typing import Awaitable, Dict, List, Tuple

from aiohttp import ClientSession, ClientResponse, ClientError

from utils import log_msg, log_json, prompt, prompt_list, prompt_opt, log

from controller_pkg.arg_parser import controller_parser

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
        admin_url: str,
        ledger_url: str="http://dev.greenlight.bcovrin.vonx.io"
    ):
        """ Initializes a controller for an Aries agent.

        Args:
            ident (str): The identity (name) of the controller
            endpoint (str): The endpoint under which the agent's admin page can be reached
            ledger_url (str): The endpoint under which the ledger can be reached
        """
        self.ident = ident
        self.did = None

        self.client_session = None

        self.ledger_url = ledger_url
        self.admin_url = admin_url
        
        self.log(f"LEDGER_URL: {self.ledger_url}; ADMIN URL: {self.admin_url}")

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
        self.register_command("issue_credential", self.issue_credential, {"thread_id": "1"})
        
    def log(self, msg):
        log(f"{self.ident}: {msg}")
        
    async def get_did(
        self
    ) -> str:
        """ Get the DID that the agent registered on the ledger. If no DID is registered yet, fetch_did() is called.

        Returns:
            str: The DID the agent registered on the ledger 
        """
        if not self.did:
            await self.fetch_did()
        
        self.log(f"Obtained DID: {self.did}")
        return self.did

    async def fetch_did(self):
        """ Fetch the DID that the agent registered on the ledger. If no DID is registered yet, register_did() is called.
        """
        self.log("Getting public DID ...")
        resp = await self.admin_GET("/wallet/did/public")
        if resp["result"] and "did" in resp["result"]:
            self.did = resp["result"]["did"]
        else:
            await self.register_did()

    async def register_did(
        self,
        is_endorser: bool=True
    ):  
        """ Register a DID for the agent on the ledger. Note that each time this method is invoked a new DID is assigned as public DID to the agent.
        
        Args:
            is_endorser (bool): If True, DID is registered with role "ENDORSER", else with role "". 

        Raises:
            Exception: DID could not be registered
        """
        self.log(f"Registering {self.ident} ...")
        
        data = {
            "alias": self.ident,
            "role": "ENDORSER" if is_endorser else ""
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
            self.log(f"nym_info: {nym_info}")
            
        await self.admin_POST("/wallet/did/public", params = {"did": self.did})
        self.log(f"Registered DID: {self.did}")
        
    async def has_connection(
        self,
        params: Dict
    ) -> bool:
        """ Send GET request to admin's /connections endpoint and returns True if there is at least one connection complying with
        the supplied parameters.

        Args:
            params (Dict): Available keys: alias, connection_protocol, invitation_key, my_did, state, their_did, their_public_did,
                their_role

        Returns:
            bool: True if at least one connection complies with the supplied parameters
        """
        resp =  await self.admin_GET("/connections", params=params)
        return len(resp["results"]) > 0
        
    async def create_invitation(
        self
    ) -> ClientResponse: 
        """ Create an invitation.

        Returns:
            ClientResponse: HTTP response object from /connections/create-invitation
        """
        self.log("Create invitation")
        return await self.admin_POST("/connections/create-invitation")
    
    async def receive_invitation(
        self, invitation: Dict
    ) -> ClientResponse:
        """ Receive an invitation.

        Args:
            invitation (Dict): An invitation object as in the "invitation" field of the response to create_invitation()

        Returns:
            ClientResponse: HTTP response object from /connections/receive-invitation
        """
        self.log("Receive invitation")
        return await self.admin_POST("/connections/receive-invitation", data=invitation)
        
    async def request_connection(
        self, connection_id: str
    ) -> ClientResponse:
        """ Request a connection from an inviter

        Args:
            connection_id (str): Identifier that invitee associates with the prospective connection

        Returns:
            ClientResponse: HTTP response object from /connections/{conn_id}/accept-invitation
        """
        self.log("Send connection request")
        return await self.admin_POST(f"/connections/{connection_id}/accept-invitation")
    
    async def accept_connection_request(
        self, their_did: str
    ):
        """ Accept a connection request from an invitee

        Args:
            their_did (str): The DID that the invitee associates with the connection

        Returns:
            ClientResponse: HTTP response object from /connections/{conn_id}/accept-request
        """
        self.log("Accept connection request")
        resp = await self.admin_GET("/connections", params={"their_did": their_did})
        connection_id = resp["results"][0]["connection_id"]
        return await self.admin_POST(f"/connections/{connection_id}/accept-request")

    async def register_schema_and_cred_def(
        self,
        schema_name,
        schema_attrs,
        version="1.0",
        tag=None
    ) -> Tuple[str, str]:
        """ Register schema and associated credential definition on the ledger.

        Args:
            schema_name (str): Schema name
            schema_attrs (List[str]): Schema attributes
            version (str, optional): Schema version. Defaults to "1.0".
            tag (str, optional): Credential definition tag. Defaults to None.
            
        Returns:
            Tuple[str, str]: Schema identifier and credential definition identifier
        """
        schema_id = await self.register_schema(
            schema_name=schema_name,
            schema_attrs=schema_attrs,
            version=version
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
    ) -> str:
        """ Register schema on the ledger.

        Args:
            schema_name (str): Schema name
            schema_attrs (List[str]): Schema attributes
            version (str, optional): Schema version. Defaults to "1.0".

        Returns:
            str: Schema identifier
        """
        self.log(f"Registering schema {schema_name} ...")
        created_schemas = await self.admin_GET("/schemas/created", params={"schema_name": schema_name})
        schema_exists = "schema_ids" in created_schemas and len(created_schemas["schema_ids"]) > 0
        if schema_exists:
            self.log(f"Schema with name {schema_name} exists already on ledger")
            return created_schemas["schema_ids"][0]
        schema_body = {
            "schema_name": schema_name,
            "schema_version": version,
            "attributes": schema_attrs
        }
        schema_response = await self.admin_POST("/schemas", schema_body)
        log_json(json.dumps(schema_response), label="Schema:")
        schema_id = schema_response["schema_id"]
        log_msg("Schema ID:", schema_id)
        return schema_id

    async def register_cred_def(
        self,
        schema_id: str,
        schema_name: str,
        tag: str = None
    ) -> Tuple[str, str]:
        """ Register credential definition on the ledger.

        Args:
            schema_id (str): Schema identifier
            schema_name (str): Schema name
            tag (str, optional): Credential defintion tag. Defaults to None.

        Returns:
            Tuple[str, str]: Schema identifier and credential definition identifier
        """
        cred_def_tag = tag if tag else (self.ident + "." + schema_name).replace(" ", "_")
        self.log(f"Registering credential definition {cred_def_tag} ...")
        cred_def_body = {
            "schema_id": schema_id,
            "support_revocation": False,
            "tag": cred_def_tag
        }
        cred_def_response = await self.admin_POST(
            "/credential-definitions", cred_def_body
        )
        cred_def_id = cred_def_response["credential_definition_id"]
        log_msg("Cred def ID:", cred_def_id)
        return schema_id, cred_def_id
    
    async def get_credential_exchange_records(self, params: Dict) -> ClientResponse:
        """ Send GET request to /issue-credential-2.0/records endpoint.

        Args:
            params (Dict): Parameters for filtering records. Available keys: connection_id, role, state, thread_id

        Returns:
            ClientResponse: HTTP response object from /issue-credential-2.0/records
        """
        return await self.admin_GET("/issue-credential-2.0/records", params=params)
    
    async def has_credential_exchange_record(self, params: Dict) -> bool:
        """ Check if there is a credential exchange record complying with the supplied parameters.

        Args:
            params (Dict): Parameters for filtering records. Available keys: connection_id, role, state, thread_id

        Returns:
            bool: True if at least one credential exchange record complies with the supplied parameters
        """
        return len((await self.get_credential_exchange_records(params))["results"]) > 0
    
    async def build_cred_preview_attributes_json(self, schema_id: str, default="default") -> Dict:
        """ Build the credential preview object for a schema id

        Args:
            schema_id (str): Schema identifier
            default (str, optional): Attribute value which is identical for all attribute names. Defaults to "default".

        Raises:
            RuntimeError: Leder has no schema with supplied schema_id

        Returns:
            Dict: Credential preview object
        """
        resp = await self.admin_GET(f"/schemas/{schema_id}")
        if not len(resp["schema"]):
            raise RuntimeError(f"Ledger has no schema with id: {schema_id}")
        attr_names = resp["schema"]["attrNames"] 
        return [{"name": attr_name, "value": default} for attr_name in attr_names]
    
    async def offer_credential(
        self, 
        connection_id: str, 
        schema_id: str, 
        cred_def_id: str, 
        attributes_json, 
        schema_issuer_did: str = None
    ) -> Tuple[str, str]:
        """ Offer a credential to a holder

        Args:
            connection_id (str): Connection identifier of the connection to the holder
            schema_id (str): Schema identifier of the offered credential
            cred_def_id (str): Credential definition identifier of the offered credential
            attributes_json (str, Dict): attributes field of the credential_preview field of the request body in JSON format (string or Dictionary) 
            schema_issuer_did (str, optional): DID of the schema issuer. Defaults to None. Then, the issuer DID is expected to be equal to the schema issuer DID
            
        Returns:
            Tuple[str, str]: Credential exchange identifier ("cred_ex_id") and thread identifier ("thread_id")
        """
        self.log("Offering credential ...")
        issuer_did = await self.get_did()
        schema_id_comps = schema_id.split(":")
        schema_name = schema_id_comps[-2]
        schema_version = schema_id_comps[-1]
        schema_issuer_did = schema_issuer_did or issuer_did
        issue_cred_body = {
            "auto_remove": True,
            "comment": "string",
            "connection_id": connection_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": attributes_json if isinstance(attributes_json, list)  else json.loads(attributes_json)
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
        self.log(f"Offered credential with \n\tcred_ex_id: {resp['cred_ex_id']}\n\tthread_id: {resp['thread_id']}")
        return resp["cred_ex_id"], resp["thread_id"]
    
    async def request_credential(self, thread_id: str) -> ClientResponse:
        """ Request a credential from an issuer

        Args:
            thread_id (str): Thread identifier of credential exchange

        Raises:
            RuntimeError: No credential exchange record with supplied thread_id in offer-received state

        Returns:
            ClientResponse: HTTP response object from /issue-credential-2.0/records/{cred_ex_id}/send-request
        """
        self.log("Requesting credential ...")
        params = {
            "thread_id": thread_id,
            "state": "offer-received"
        }
        if not await self.has_credential_exchange_record(params):
            raise RuntimeError(f"There is no offered credential with thread_id: {thread_id}")
        cred_ex_id = (await self.get_credential_exchange_records(params))["results"][0]["cred_ex_record"]["cred_ex_id"]
        return await self.admin_POST(f"/issue-credential-2.0/records/{cred_ex_id}/send-request")
    
    async def issue_credential(self, thread_id: str) -> ClientResponse:
        """ Issue credential to holder

        Args:
            thread_id (str): Thread identifier of credential exchange

        Raises:
            RuntimeError: No credential exchange record with supplied thread_id in offer-received state

        Returns:
            ClientResponse: HTTP response object from /issue-credential-2.0/records/{cred_ex_id}/issue
        """
        self.log("Issuing credential ...")
        params = {
            "thread_id": thread_id,
            "state": "request-received"
        }
        if not await self.has_credential_exchange_record(params):
            raise RuntimeError(f"There is no requested credential with thread_id: {thread_id}")
        cred_ex_id = (await self.get_credential_exchange_records(params))["results"][0]["cred_ex_record"]["cred_ex_id"]
        return await self.admin_POST(f"/issue-credential-2.0/records/{cred_ex_id}/issue", data={})

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
            self.log(f"Error during GET {path}: {str(e)}")
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
            self.log(f"Error during POST {path}: {str(e)}")
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
            sys.exit(1)

if __name__ == "__main__":
    controller = Controller(
        ident="ServerController",
        endpoint="http://localhost:8121"
    )
    
    parser = controller_parser()
    args = parser.parse_args()
    
    try:
        asyncio.run(controller.main(args))
    except KeyboardInterrupt:
        sys.exit()

