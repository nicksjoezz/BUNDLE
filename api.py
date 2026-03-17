# api.py
import requests
import json
import base58
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solana.rpc.async_api import AsyncClient
from solana.exceptions import SolanaRpcException
import asyncio
from typing import Dict, Any, List, Optional
from solders.hash import Hash
from solders.message import Message
from solders.pubkey import Pubkey
import logging
import configparser
import os

# Load configuration to get the log file path
config = configparser.ConfigParser()
config.read('config.ini')
log_file = config.get('DEFAULT', 'LOG_FILE', fallback='infinityato.log') # fallback in case not set

# Create logs directory if it doesn't exist
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configure logging
log_path = os.path.join(log_dir, log_file)  # Path to the log file
logging.basicConfig(
    filename=log_path,  # Log to a file
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w' # 'w' for overwrite, 'a' for append
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler) # '' means root logger




class PumpFunAPI:
    def __init__(self, api_url, rpc_url, api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self.rpc_url = rpc_url
        self.rpc_client = AsyncClient(rpc_url)
        self._session = requests.Session()  # Initialize a session for connection pooling

    async def close(self):
        """Closes the session and RPC client."""
        try:
          if self._session:
            self._session.close()
          if self.rpc_client:
              await self.rpc_client.close()
        except Exception as e:
          logging.error(f"Error closing pumpfun api: {e}")

    async def _make_request(self, method: str, url: str, data: Optional[Dict] = None, files: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict:
        """Handles all the requests with error handling."""
        try:
            logging.info(f"Making {method} request to {url} to: {url} with data: {data}, headers: {headers}, files: {files}")
            if method == 'GET':
                response = self._session.get(url, headers=headers)
            elif method == 'POST':
                if files: # Handle POST requests with files differently
                    response = self._session.post(url, data=data, files=files, headers=headers) # Pass data directly
                else:
                    response = self._session.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf-8'), headers=headers) # JSON encode data if no files
            else:
                raise ValueError(f"Invalid HTTP method: {method}")

            logging.info(f"Request to {url} completed with status code: {response.status_code}")
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            try:
                return response.json()
            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from response: {response.text}")
                return {'transaction': response.text} #Return transaction as the RAW response
                #raise

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            raise  # Re-raise to be handled by calling function.

    async def create_wallet(self) -> Dict:
        """Creates a new wallet and returns the API key."""
        url = f"{self.api_url}/api/create-wallet"
        try:
            response = await self._make_request(method='GET', url=url)
            logging.info(f"Create wallet API response: {response}")
            return response
        except Exception as e:
            logging.error(f"Error creating wallet: {e}")
            raise

    async def create_ipfs_metadata(self, metadata: Dict, files: Optional[Dict] = None, content_type: str = 'image/png') -> Dict:
        """Uploads metadata to IPFS and returns the metadata URI."""
        url = f"{self.api_url}/api/ipfs"
        try:
            response = await self._make_request(method='POST', url=url, data=metadata, files=files) # Pass metadata directly as data
            logging.info(f"Create IPFS metadata response: {response}")
            return response
        except Exception as e:
            logging.error(f"Error creating IPFS metadata: {e}")
            raise

    async def create_transaction(self, data: Dict) -> Dict:
        """Creates a transaction on Pump.fun using the lightning API."""
        headers = {'Content-Type': 'application/json'}
        url = f"{self.api_url}/api/trade?api-key={self.api_key}"
        try:
            response = await self._make_request(method='POST', url=url, data=data, headers=headers) # Pass data directly
            logging.info(f"Create transaction API response: {response}")
            return response
        except Exception as e:
            logging.error(f"Error creating transaction: {e}")
            raise

    async def create_local_transaction(self, data: Dict, mint_keypair: Keypair, signer_keypair: Keypair) -> Dict:
        """Creates a local transaction for signing."""
        data['publicKey'] = str(signer_keypair.pubkey())
        headers = {'Content-Type': 'application/json'}
        url = f"{self.api_url}/api/trade-local"
        try:
            response_bytes = await self._make_request(method='POST', url=url, data=data, headers=headers) # Pass data directly
            #response = response_bytes['transaction']

            return response_bytes
        except Exception as e:
            logging.error(f"Error creating local transaction: {e}")
            raise

    async def create_jito_bundle(self, transactions: List[Dict], signer_keypairs: List[Keypair], mint_keypair: Optional[Keypair] = None) -> List[str]:
       """Creates a jito bundle from a list of transactions"""
       try:
          url = f"{self.api_url}/api/trade-local"
          response = await self._make_request(method='POST', url=url, data=json.dumps(transactions, ensure_ascii=False).encode('utf-8'), headers={"Content-Type": "application/json"})

          if not response or 'transactions' not in response:
                raise Exception("Invalid response from /api/trade-local")

          encoded_signed_transactions = response['transactions']
          tx_signatures = []

          # Now submit with Jito
          jito_response = await self._make_request(
                "POST",
                "https://mainnet.block-engine.jito.wtf/api/v1/bundles",
                data=json.dumps({
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sendBundle",
                    "params": [encoded_signed_transactions]
                }, ensure_ascii=False).encode('utf-8'),
               headers={"Content-Type": "application/json"}
            )

          if jito_response:
            tx_signatures = encoded_signed_transactions # These should already be signatures if transactions went fine
            return tx_signatures
          else:
            raise Exception(f"Error submitting bundle to jito")

       except Exception as e:
            print(f"Error creating Jito Bundle: {e}")
            raise # Re-raise the exception

    def _encode_transaction(self, tx: VersionedTransaction) -> str:
        """Encodes a VersionedTransaction to base58 string."""
        return base58.b58encode(bytes(tx)).decode()

    def _decode_transaction(self, encoded_tx: str) -> VersionedTransaction:
         """Decodes a base58 encoded string to VersionedTransaction."""
         return VersionedTransaction.from_bytes(base58.b58decode(encoded_tx))

    async def broadcast_transaction(self, tx: VersionedTransaction) -> str:
        """ Broadcasts the transaction to the network and returns the transaction id."""
        try:
            serialized_tx = base58.b58encode(bytes(tx)).decode() #removed bytes(tx.compile_message())
            result = await self.rpc_client.send_raw_transaction(bytes(tx))
            await self.rpc_client.confirm_transaction(result.value) #added result.value
            return result.value #added result.value
        except SolanaRpcException as e:
            print(f"Could not send raw transaction {e}")
            raise # Re-raise the exception to be handled by calling function

    async def get_token_balance(self, mint_address: str, public_key: str) -> float:
         """Get the token balance for a specific wallet."""
         url = f"https://pumpportal.fun/api/token/balance?mint={mint_address}&publicKey={public_key}"
         try:
            balance_data = await self._make_request(method='GET', url=url)
            return balance_data.get('balance', 0)
         except Exception as e:
            logging.error(f"Error getting token balance: {e}")
            raise