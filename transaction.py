# transaction.py
import requests
from solders.transaction import VersionedTransaction, Transaction # Keep both imports
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.pubkey import Pubkey
import logging
from base58 import b58encode, b58decode
import json
from typing import Dict, List, Union # Import Union
from solders.system_program import ID as SYSTEM_PROGRAM_ID, transfer, TransferParams
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash
from solders.message import Message
from solana.rpc.async_api import AsyncClient  # Correct import
import requests
import configparser
import os
import asyncio
from typing import TYPE_CHECKING
import httpx # Correct import
import base64 # Import base64
from spl.token.constants import TOKEN_PROGRAM_ID


if TYPE_CHECKING:
    from launch_manager import LaunchManager

async def send_helius_transaction(helius_api_key: str, tx: Union[VersionedTransaction, Transaction]) -> str: # Updated type hint to Union
    """Sends a VersionedTransaction or Transaction to the Helius API, auto-detecting type."""
    helius_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
    headers = {"Content-Type": "application/json"}

    try:
      async with httpx.AsyncClient() as client:
        if isinstance(tx, VersionedTransaction):
            # Handle VersionedTransaction (JSON Payload)
            commitment = CommitmentLevel.Confirmed # Or use a configurable commitment level
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            tx_payload = SendVersionedTransaction(tx, config).to_json() # Create structured JSON payload
            response = await client.post(helius_url, headers=headers, json=json.loads(tx_payload)) # Send JSON payload

        elif isinstance(tx, Transaction):
            # Handle Legacy Transaction (Base64 Payload)
            serialized_transaction = bytes(tx)
            txn_base64 = base64.b64encode(serialized_transaction).decode('utf-8')
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [txn_base64, {"encoding": "base64"}]
            }
            response = await client.post(helius_url, headers=headers, json=payload) # Send Base64 payload

        else:
            raise ValueError("Unsupported transaction type: Must be VersionedTransaction or Transaction")

        response.raise_for_status()
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Transaction failed: {response_data['error']}")
        return response_data['result']

    except Exception as e:
        logging.error(f"Error sending transaction to Helius: {e}")
        raise


# --- MODIFIED: Replaced get_token_balance with new implementation ---
def get_token_accounts(wallet_address: str, token_mint_address: str, helius_api_key: str): # <--- API KEY PASSED AS ARGUMENT
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {
                "mint": token_mint_address
            },
            {
                "encoding": "jsonParsed"
            }
        ]
    }
    rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}" # <--- API KEY USED HERE
    response = requests.post(rpc_url, headers=headers, json=payload)
    response_data = response.json()
    if 'error' in response_data:
        raise Exception(f"Error finding token account: {response_data['error']}")
    return response_data['result']['value']

def check_token_balance_helius(wallet_address: str, token_mint_address: str, helius_api_key: str) -> float: # <--- API KEY PASSED AS ARGUMENT
    token_accounts = get_token_accounts(wallet_address, token_mint_address, helius_api_key) # <--- API KEY PASSED HERE
    if not token_accounts:
        return 0
    if not token_accounts[0]['account']['data']['parsed']['info']: # ADDED CHECK HERE
        return 0
    account_data = token_accounts[0]['account']['data']['parsed']['info']
    token_amount = int(account_data['tokenAmount']['amount'])
    token_decimals = int(account_data['tokenAmount']['decimals'])
    actual_amount = token_amount / (10 ** token_decimals)
    return actual_amount

async def get_token_balance(rpc_url: str, mint_address: str, public_key: str, helius_api_key: str) -> float:  # ADDED helius_api_key ARGUMENT BACK
    """Get the token balance for a specific wallet."""
    # --- MODIFIED: Now calls check_token_balance_helius internally ---
    return check_token_balance_helius(public_key, mint_address, helius_api_key) # <--- API KEY PASSED HERE


# Kept for async calls
async def get_recent_blockhash(rpc_url: str) -> Hash:
    """Fetches the latest blockhash using httpx."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash",
                "params": [{"commitment": "finalized"}],  # Use 'finalized' for safety
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Error getting blockhash: {response_data['error']}")
        return Hash.from_string(response_data['result']['value']['blockhash'])


# --- NEW:  Synchronous blockhash retrieval (from Code B, modified) ---
def get_recent_blockhash_sync(rpc_url: str) -> str:
    """Fetches the latest blockhash SYNCHRONOUSLY using requests."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getLatestBlockhash",
        "params": [],  # No commitment level -  IMPORTANT!
    }
    try:
        response = requests.post(rpc_url, headers=headers, json=payload)
        response.raise_for_status()  # Add error handling
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Error getting blockhash: {response_data['error']}")
        return response_data['result']['value']['blockhash']
    except requests.exceptions.RequestException as e:
        logging.error(f"Error getting blockhash synchronously: {e}")
        raise

# --- MODIFIED: transfer_spl_token function to use solders primitives ---
async def transfer_spl_token(
    sender_keypair: Keypair,
    recipient_address: str,
    token_mint_address: str,
    amount: float,
    helius_api_key: str,
    rpc_client: AsyncClient # ADDED rpc_client
) -> str:
    """Transfers SPL tokens to a recipient address using solders primitives."""
    try:
        recipient_pubkey = Pubkey.from_string(recipient_address)
        token_mint_pubkey = Pubkey.from_string(token_mint_address)
        source_ata = get_associated_token_address(sender_keypair.pubkey(), token_mint_pubkey)
        dest_ata = get_associated_token_address(recipient_pubkey, token_mint_pubkey)

        balance = await get_token_balance(rpc_client.url, token_mint_address, str(sender_keypair.pubkey()), helius_api_key) # Get balance to ensure enough tokens
        if balance < amount:
            raise Exception(f"Insufficient token balance: {balance} for transfer amount: {amount}")

        # 1. Prepare Instruction Data for SPL Token Transfer
        instruction_data = bytearray()
        instruction_data.extend(int(3).to_bytes(1, byteorder='little'))  # Command: Transfer (3)
        instruction_data.extend(int(amount * (10**9)).to_bytes(8, byteorder='little')) # Amount (adjust decimals if needed)

        # 2. Create AccountMeta list
        account_metas = [
            AccountMeta(pubkey=source_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=dest_ata, is_signer=False, is_writable=True),
            AccountMeta(pubkey=sender_keypair.pubkey(), is_signer=True, is_writable=False),
        ]

        # 3. Construct Instruction
        transfer_instruction = Instruction(
            program_id=TOKEN_PROGRAM_ID,
            data=bytes(instruction_data),
            accounts=account_metas,
        )

        recent_blockhash = await get_recent_blockhash(rpc_client.url)
        message = Message(instructions=[transfer_instruction], recent_blockhash=recent_blockhash, payer=sender_keypair.pubkey())
        transaction = VersionedTransaction(message, [sender_keypair]) # Create versioned transaction
        signature = await send_helius_transaction(helius_api_key, transaction) # Send via Helius

        logging.info(f"SPL Token transfer successful (solders). Signature: {signature}")
        return signature
    except Exception as e:
        logging.error(f"Error transferring SPL tokens (solders): {e}")
        raise


async def submit_jito_bundle(pumpfun_api_url: str, helius_api_key: str, transactions: List[Dict], signer_keypairs: List[Keypair], rpc_client: AsyncClient) -> List[str]:
    """Submits transactions in batches to respect Jito's 5 transaction limit per bundle."""
    logging.info(f"Creating jito bundle from: {transactions}")
    all_signatures = []
    chunk_size = 5  # Jito's transaction limit
    try:
      #1, Batch and chunk the transactions
      for i in range(0, len(transactions), chunk_size):
          batch_transactions = transactions[i:i + chunk_size]
          batch_signer_keypairs = signer_keypairs[i:i+chunk_size]
          logging.info(f"Processing transactions batch {i // chunk_size + 1}")
          # 1. Prepare the request to PumpPortal's trade-local endpoint
          url = f"{pumpfun_api_url}/api/trade-local"
          logging.info(f"Making request to {url} with data: {json.dumps(batch_transactions)}")

          response = requests.post(url, json=batch_transactions, headers={"Content-Type": "application/json"})
          response.raise_for_status()  # Raise HTTPError for bad responses
          encoded_transactions = response.content
          encoded_signed_transactions = []
          tx_signatures = []

          for index, tx_data in enumerate(batch_transactions): # batch_transactions is already chunked
              logging.info(f"Processing transaction {index}")
              recent_blockhash_resp = get_recent_blockhash_sync(rpc_client.url)
              recent_blockhash = Hash.from_string(recent_blockhash_resp)

              from_pk = Pubkey.from_string(tx_data["publicKey"])
              if tx_data["action"] == "transferSol" or tx_data["action"] == "burnTokens":
                params = TransferParams(
                        from_pubkey=from_pk,
                        to_pubkey=Pubkey.from_string(tx_data["mint"]),
                        lamports=int(tx_data["amount"] * 1_000_000_000),
                    )
                transfer_instruction = transfer(params)
                message = Message([transfer_instruction],recent_blockhash=Hash(recent_blockhash))
                transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[batch_signer_keypairs[index]])
                transaction_obj.sign([batch_signer_keypairs[index]], recent_blockhash=recent_blockhash)
                signature = await send_helius_transaction(helius_api_key, VersionedTransaction(message, transaction_obj.signatures)) # MODIFIED HERE - Versioned Transaction conversion
                encoded_signed_transactions.append(b58encode(bytes(transaction_obj)).decode())
                tx_signatures.append(str(signature))
              elif tx_data["action"] == "createLookupTable":
                  continue
              else:
                  print ("doing it all wrong")
                  continue


              logging.info(f"Transaction {index} signed with signature: {tx_signatures[-1]}")

          # 3. Submit to Jito Relayer
          jito_url = "https://mainnet.block-engine.jito.wtf/api/v1/bundles"
          jito_payload = {
              "jsonrpc": "2.0",
              "id": 1,
              "method": "sendBundle",
              "params": [
                  encoded_signed_transactions
              ]
          }

          logging.info(f"Submitting bundle to Jito Relayer: {jito_url}")
          jito_response = requests.post(jito_url, json=jito_payload, headers={"Content-Type": "application/json"})
          jito_response.raise_for_status()

          jito_result = jito_response.json()
          logging.info(f"Jito Relayer response: {jito_result}")
          if jito_response.status_code == 200:
             print("Bundle submitted successfully.")
             for i, signature in enumerate(tx_signatures):
                 print(f'Transaction {i}: https://solscan.io/tx/{signature}')
          else:
             print("Failed to submit bundle.")
             print(jito_response.reason)
          all_signatures.extend(tx_signatures)
          await asyncio.sleep(1)

      return all_signatures

    except Exception as e:
        logging.error(f"Error creating Jito Bundle: {e}")
        raise