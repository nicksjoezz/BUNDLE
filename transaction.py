# transaction.py
import requests
from solders.transaction import VersionedTransaction, Transaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from solders.pubkey import Pubkey
import logging
from base58 import b58encode, b58decode
import json
from typing import Dict, List, Union, Optional
from solders.system_program import ID as SYSTEM_PROGRAM_ID, transfer, TransferParams
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash
from solders.message import Message
from solana.rpc.async_api import AsyncClient
import configparser
import os
import asyncio
import httpx
import base64
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.associated_token_account import get_associated_token_address

async def send_helius_transaction(helius_api_key: str, tx: Union[VersionedTransaction, Transaction]) -> str:
    """Sends a VersionedTransaction or Transaction to the Helius API, auto-detecting type."""
    helius_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
    headers = {"Content-Type": "application/json"}

    try:
      async with httpx.AsyncClient() as client:
        if isinstance(tx, VersionedTransaction):
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            tx_payload = SendVersionedTransaction(tx, config).to_json()
            response = await client.post(helius_url, headers=headers, json=json.loads(tx_payload))

        elif isinstance(tx, Transaction):
            serialized_transaction = bytes(tx)
            txn_base64 = base64.b64encode(serialized_transaction).decode('utf-8')
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [txn_base64, {"encoding": "base64"}]
            }
            response = await client.post(helius_url, headers=headers, json=payload)

        else:
            raise ValueError("Unsupported transaction type")

        response.raise_for_status()
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Transaction failed: {response_data['error']}")
        return response_data['result']

    except Exception as e:
        logging.error(f"Error sending transaction to Helius: {e}")
        raise

def get_token_accounts(wallet_address: str, token_mint_address: str, helius_api_key: str):
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet_address,
            {"mint": token_mint_address},
            {"encoding": "jsonParsed"}
        ]
    }
    rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
    response = requests.post(rpc_url, headers=headers, json=payload)
    response_data = response.json()
    if 'error' in response_data:
        raise Exception(f"Error finding token account: {response_data['error']}")
    return response_data['result']['value']

def check_token_balance_helius(wallet_address: str, token_mint_address: str, helius_api_key: str) -> float:
    token_accounts = get_token_accounts(wallet_address, token_mint_address, helius_api_key)
    if not token_accounts:
        return 0
    try:
        account_data = token_accounts[0]['account']['data']['parsed']['info']
        token_amount = int(account_data['tokenAmount']['amount'])
        token_decimals = int(account_data['tokenAmount']['decimals'])
        return token_amount / (10 ** token_decimals)
    except (KeyError, IndexError):
        return 0

async def get_token_balance(rpc_url: str, mint_address: str, public_key: str, helius_api_key: str) -> float:
    return check_token_balance_helius(public_key, mint_address, helius_api_key)

async def get_recent_blockhash(rpc_url: str) -> Hash:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash",
                "params": [{"commitment": "finalized"}],
            },
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Error getting blockhash: {response_data['error']}")
        return Hash.from_string(response_data['result']['value']['blockhash'])

def get_recent_blockhash_sync(rpc_url: str) -> str:
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getLatestBlockhash",
        "params": [],
    }
    try:
        response = requests.post(rpc_url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        if 'error' in response_data:
            raise Exception(f"Error getting blockhash: {response_data['error']}")
        return response_data['result']['value']['blockhash']
    except Exception as e:
        logging.error(f"Error getting blockhash synchronously: {e}")
        raise

async def submit_jito_bundle(pumpfun_api_url: str, helius_api_key: str, transactions: List[Dict], signer_keypairs: List[Keypair], rpc_client: AsyncClient) -> List[str]:
    """Submits transactions in batches to respect Jito's 5 transaction limit per bundle."""
    logging.info(f"Creating jito bundle for {len(transactions)} transactions")
    all_signatures = []
    chunk_size = 5

    for i in range(0, len(transactions), chunk_size):
        batch_transactions = transactions[i:i + chunk_size]
        batch_signer_keypairs = signer_keypairs[i:i + chunk_size]
        encoded_signed_transactions = []
        tx_signatures = []

        for index, tx_data in enumerate(batch_transactions):
            try:
                if tx_data["action"] in ["buy", "sell"]:
                    url = "https://pumpportal.fun/api/trade-local"
                    response = requests.post(url, json=tx_data, headers={"Content-Type": "application/json"})
                    response.raise_for_status()

                    tx = VersionedTransaction.from_bytes(response.content)
                    tx.sign([batch_signer_keypairs[index]])

                    encoded_signed_transactions.append(b58encode(bytes(tx)).decode())
                    tx_signatures.append(str(tx.signatures[0]))

                elif tx_data["action"] == "transferSol":
                    recent_blockhash_str = get_recent_blockhash_sync(rpc_client.url)
                    recent_blockhash = Hash.from_string(recent_blockhash_str)

                    from_pk = Pubkey.from_string(tx_data["publicKey"])
                    to_pk = Pubkey.from_string(tx_data["mint"])
                    lamports = int(float(tx_data["amount"]) * 1_000_000_000)

                    ix = transfer(TransferParams(from_pubkey=from_pk, to_pubkey=to_pk, lamports=lamports))
                    msg = Message.new_with_blockhash([ix], from_pk, recent_blockhash)
                    tx = VersionedTransaction(msg, [batch_signer_keypairs[index]])

                    encoded_signed_transactions.append(b58encode(bytes(tx)).decode())
                    tx_signatures.append(str(tx.signatures[0]))
            except Exception as e:
                logging.error(f"Failed to prepare transaction {index} for Jito bundle: {e}")

        if not encoded_signed_transactions:
            continue

        jito_url = "https://mainnet.block-engine.jito.wtf/api/v1/bundles"
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendBundle",
            "params": [encoded_signed_transactions]
        }

        try:
            res = requests.post(jito_url, json=payload, headers={"Content-Type": "application/json"})
            res.raise_for_status()
            logging.info(f"Jito bundle submitted: {res.json()}")
            all_signatures.extend(tx_signatures)
        except Exception as e:
            logging.error(f"Jito bundle submission failed: {e}")

        await asyncio.sleep(1)
    return all_signatures

async def transfer_spl_token(sender_keypair: Keypair, recipient_address: str, token_mint_address: str, amount: float, helius_api_key: str, rpc_client: AsyncClient) -> str:
    """Transfers SPL tokens using the available spl-token library and Helius for landing."""
    try:
        from spl.token.constants import TOKEN_PROGRAM_ID
        from spl.token.instructions import transfer, TransferParams
        from spl.associated_token_account import get_associated_token_address

        sender_pubkey = sender_keypair.pubkey()
        recipient_pubkey = Pubkey.from_string(recipient_address)
        mint_pubkey = Pubkey.from_string(token_mint_address)

        source_ata = get_associated_token_address(sender_pubkey, mint_pubkey)
        dest_ata = get_associated_token_address(recipient_pubkey, mint_pubkey)

        decimals = 6
        amount_raw = int(amount * (10 ** decimals))

        if amount_raw <= 0:
            logging.warning(f"Skipping SPL transfer: calculated raw amount is {amount_raw}")
            return "skipped"

        transfer_ix = transfer(TransferParams(
            program_id=TOKEN_PROGRAM_ID,
            source=source_ata,
            dest=dest_ata,
            owner=sender_pubkey,
            amount=amount_raw
        ))

        recent_blockhash_str = get_recent_blockhash_sync(rpc_client.url)
        recent_blockhash = Hash.from_string(recent_blockhash_str)

        msg = Message.new_with_blockhash([transfer_ix], sender_pubkey, recent_blockhash)
        tx = VersionedTransaction(msg, [sender_keypair])

        signature = await send_helius_transaction(helius_api_key, tx)
        logging.info(f"SPL transfer successful: {signature}")
        return signature
    except Exception as e:
        logging.error(f"Error in transfer_spl_token: {e}")
        raise
