# launch_actions.py
import logging
import configparser # ADDED
from typing import Dict, List, Optional, Tuple, Any # ADDED Tuple, Any
from solders.keypair import Keypair
from wallet import Token, Wallet # Added Wallet for sniper farmer
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.message import Message
from solders.transaction import Transaction, VersionedTransaction
import asyncio
import httpx  # Import httpx for making HTTP requests
import random
import base58
import transaction # ADDED
import json
import requests  # Import requests
from solders.commitment_config import CommitmentLevel
from solders.rpc.config import RpcSendTransactionConfig
from solders.rpc.requests import SendVersionedTransaction
import os # ADDED for file handling
import websocket # Added for real-time liquidity monitoring
import ssl # Added for websocket
import time # Added for websocket

# Load configuration to get the PUMP_FUN_PROGRAM_ID
config = configparser.ConfigParser()
config.read('config.ini')

IPFS_UPLOAD_URL = "https://pump.fun/api/ipfs"  # Hardcoded IPFS upload URL
PUMP_FUN_PROGRAM_ID = Pubkey.from_string(config.get('DEFAULT', 'PUMP_FUN_PROGRAM_ID')) # Load from config.ini

def get_associated_bonding_curve_address(mint: Pubkey, program_id: Pubkey) -> Tuple[Pubkey, int]:
    """
    Derives the associated bonding curve PDA for a pump.fun token mint.
    """
    return Pubkey.find_program_address(
        [
            b"bonding-curve",
            bytes(mint)
        ],
        program_id
    )

async def get_sol_price_usd() -> float:
    """Fetches the current SOL price in USD from CoinGecko."""
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        response.raise_for_status()
        data = response.json()
        sol_price = data.get("solana", {}).get("usd")
        if sol_price:
            logging.info(f"Fetched SOL price: {sol_price} USD")
            return float(sol_price)
        else:
            logging.error("Could not fetch SOL price from CoinGecko. Response: %s", data)
            return 0.0 # Return 0 or raise an exception as appropriate
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching SOL price from CoinGecko: {e}")
        return 0.0 # Return 0 or raise an exception as appropriate

async def clone_and_snipe(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool, existing_token_address: str, dev_buy_amount: float): # MODIFIED - Added dev_buy_amount
    """Clones metadata from an existing token and executes a snipe launch using Helius DAS API.  CREATE TOKEN SEPARATELY FIRST"""
    logging.info(
        f"Executing Clone + Snipe launch for token: {token.name} (cloning from {existing_token_address}) with {num_wallets} wallets, Jito: {use_jito}")

    try:
        # Fetch token metadata from Helius DAS API
        async with httpx.AsyncClient() as client:
            helius_url = f"https://mainnet.helius-rpc.com/?api-key={launch_manager.helius_api_key}"
            payload = {
                "jsonrpc": "2.0",
                "id": "test",
                "method": "getAsset",
                "params": {"id": existing_token_address}
            }
            response = await client.post(helius_url, json=payload)
            response.raise_for_status()  # Raise HTTPError for bad responses
            asset_data = response.json()

            if "result" not in asset_data or asset_data["result"] is None:
                raise ValueError(f"Could not retrieve asset data for {existing_token_address} from Helius.")

            asset_result = asset_data["result"]

            # Extract metadata from DAS API response
            token_name = asset_result["content"]["metadata"].get("name", "Cloned Token")
            token_symbol = asset_result["content"]["metadata"].get("symbol", "CTK")
            description = asset_result["content"]["metadata"].get("description", f"Cloned from {existing_token_address}")

            # Extract website. The DAS API stores these in a different place
            external_url = asset_result["content"].get("links", {}).get("website", "")

            # --- MODIFIED: Check for image.png in images folder ---
            image_folder = "images"
            image_path = None
            potential_image_path = os.path.join(image_folder, "image.png")

            if os.path.exists(potential_image_path):
                image_path = potential_image_path
                logging.info(f"[green]Found image in images folder: {image_path}[/green]")
                image = None  # Don't use DAS API image URL if image.png exists
            else:
                # --- MODIFIED: Use DAS API image URL if image.png doesn't exist ---
                image = asset_result["content"].get("links",{}).get("image", "")
                logging.info(f"[yellow]No image found in {image_folder}. Using image URL from DAS API.[/yellow]")

            token_metadata_for_ipfs = { # Metadata for IPFS upload - No URI yet
                'name': token_name,
                'symbol': token_symbol,
                'description': description,
                'website': external_url,
                'logo': image,  #  Use 'image' here (either DAS API or None)
                'showName': 'true',
            }
            files = {}
            f = None
            if image_path:  # If image_path was found, upload from file
                f = open(image_path, 'rb')
                files['file'] = (os.path.basename(image_path), f, 'image/png')  # or determine content type dynamically
                token_metadata_for_ipfs['logo'] = None  #  Clear DAS API image if uploading from file
                logging.info("Uploading image from images folder.")
            else:
                logging.info("Using image URL from DAS API.")


            # Directly using requests to upload to IPFS
            try:
                response = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files) # Explicitly use IPFS_UPLOAD_URL
                response.raise_for_status()
                ipfs_response = response.json()
                metadata_uri = ipfs_response.get('metadataUri', '')  # Get metadata URI, handle potential absence
                token.metadata_uri = metadata_uri  # Store metadata URI in Token object
                logging.info(f"IPFS upload successful, metadata URI: {metadata_uri}")
            except requests.exceptions.RequestException as e:
                logging.error(f"IPFS upload failed: {e}")
                raise
            final_token_metadata = { # Final token metadata with URI
                'name': token_name,
                'symbol': token_symbol,
                'uri': metadata_uri # Use the IPFS metadata URI
            }

            # --- ADDED: Define mint_keypair here ---
            mint_keypair = Keypair()

            # Phase 1: Create the token (Non-Jito) - **SIMPLIFIED TRANSACTION CREATION**
            create_tx = {
               'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
               'action': 'create',
               'tokenMetadata': final_token_metadata, # Use final token metadata with URI
               'mint': str(mint_keypair.pubkey()),  # mint_keypair is now defined
               'denominatedInSol': 'true',
               'amount': dev_buy_amount,  # MODIFIED - Use dev_buy_amount
               'slippage': launch_manager.default_slippage,
               'priorityFee': launch_manager.default_priority_fee,
               'pool': launch_manager.default_pool
            }
            logging.info("Creating token (Non-Jito)...")

            # Directly get the transaction bytes from PumpFun API - Like Standalone Script
            helius_url = f"https://rpc.helius.xyz/?api-key={launch_manager.helius_api_key}"  # Define helius_url here
            response = requests.post(
                "https://pumpportal.fun/api/trade-local",
                headers={'Content-Type': 'application/json'},
                data=json.dumps(create_tx)
            )
            response.raise_for_status() # Ensure request was successful

            tx_bytes = response.content # Get raw transaction bytes from response

            # Construct VersionedTransaction - Like Standalone Script
            tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [mint_keypair, launch_manager.main_wallet.keypair])

            # Prepare payload for Helius - Like Standalone Script
            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            tx_payload = SendVersionedTransaction(tx, config).to_json()


            helius_response = requests.post(
                url=helius_url,
                headers={"Content-Type": "application/json"},
                data=tx_payload # Send the prepared payload
            )
            helius_response.raise_for_status() # Check Helius response
            txSignature = helius_response.json().get('result', 'Transaction Failed')


            token.mint_address = str(mint_keypair.pubkey()) # Set mint address
            logging.info(f"Token {token.name} created with mint {token.mint_address} tx: {txSignature}")
            logging.info(f"Mint address for buys will be: {token.mint_address}") # ADDED LOGGING HERE

            # Phase 2: Sub-wallet buys (Jito or Non-Jito)
            sub_buy_txs = []
            signer_keypairs = []
            for i in range(num_wallets):
               wallet = launch_manager.sub_wallets[i]
               amount = amounts[i]
               sub_buy_txs.append({
                    "publicKey": str(wallet.keypair.pubkey()),
                    "action": "buy",
                    "mint": str(token.mint_address), # Use the mint address obtained from creation
                    "denominatedInSol": "true",
                    "amount": amount,
                    "slippage": launch_manager.default_slippage,
                    'priorityFee': launch_manager.default_priority_fee,
                    'pool': "auto"
               })
               signer_keypairs.append(wallet.keypair)

            if use_jito:
                logging.info("Submitting sub-wallet buys as Jito bundle...")
                await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
                logging.info(f"All sub-wallet buys submitted as Jito bundle for token {token.name}")
            else:
                logging.info("Submitting sub-wallet buys as separate transactions (Non-Jito)...")
                for sub_buy_tx, signer_keypair in zip(sub_buy_txs, signer_keypairs):
                    #Correct signing here too by creating versioned Transaction then sign the message
                    sub_buy_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(sub_buy_tx, Keypair(), signer_keypair) # Mint keypair is dummy here
                    #Correct versioned Transaction
                    tx = VersionedTransaction(VersionedTransaction.from_bytes(sub_buy_transaction_bytes['transaction'].encode('utf-8')).message, [signer_keypair])
                    txSignature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx) # MODIFIED - Pass tx
                    logging.info(f"Sub wallet bought token {token.name} mint {token.mint_address} tx: {txSignature}")
                logging.info(f"All sub-wallet buys submitted as separate transactions (Non-Jito) for token {token.name}")
            if f: # Close file manually AFTER the request is complete
                f.close()


    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP error fetching token data: {e}")
        raise
    except requests.exceptions.RequestException as e: # Catch request exceptions for API calls
        logging.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logging.error(f"Error in clone_and_snipe: {e}")
        raise

async def bundle_stagger_launch(launch_manager, token: Token, num_wallets: int, amounts: List[float], additional_params: Dict, clone_existing: bool = False, clone_address: str = None, dev_buy_amount: float = 0.001): # MODIFIED - Added dev_buy_amount
    """Executes a bundled and staggered launch with a random delay within an interval. CREATE TOKEN SEPARATELY FIRST"""
    logging.info(f"Executing bundled and stagger launch for token: {token.name} mint:None")
    if additional_params is None or 'delay' not in additional_params:
        logging.warning("A delay interval needs to be specified for staggered buy")
        return

    delay_interval = additional_params['delay']  # This is now the *maximum* delay
    mint_keypair = Keypair()  # Mint Keypair

    if not clone_existing:
        # Phase 1: Create the token (Non-Jito) - **SIGN WITH BOTH KEYPAIRS**
        token_metadata_for_ipfs = { # Metadata for IPFS upload - No URI yet
            'name': token.name,
            'symbol': token.symbol,
            'description': token.description,
            'telegram': token.telegram,
            'twitter': token.twitter,
            'website': token.website,
            'showName': 'true',
        }
        files = {}
        f = None # Initialize f outside the if block
        if token.image_path and os.path.exists(token.image_path): # Check if image path exists
            f = open(token.image_path, 'rb') # Open file, but DO NOT use 'with open'
            files['file'] = (os.path.basename(token.image_path), f, 'image/png') # or determine content type dynamically
        else:
            f = None # Ensure f is defined even if no image path

        # Directly using requests to upload to IPFS
        try:
            response = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files) # Explicitly use IPFS_UPLOAD_URL
            response.raise_for_status()
            ipfs_response = response.json()
            metadata_uri = ipfs_response.get('metadataUri', '')  # Get metadata URI, handle potential absence
            token.metadata_uri = metadata_uri  # Store metadata URI in Token object
            logging.info(f"IPFS upload successful, metadata URI: {metadata_uri}")
        except requests.exceptions.RequestException as e:
            logging.error(f"IPFS upload failed: {e}")
            raise
        final_token_metadata = { # Final token metadata with URI
            'name': token.name,
            'symbol': token.symbol,
            'uri': metadata_uri # Use the IPFS metadata URI
        }
        create_tx = {
            'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': final_token_metadata, # Use final token metadata with URI
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': dev_buy_amount,  # MODIFIED - Use dev_buy_amount
            'slippage': launch_manager.default_slippage,
            'priorityFee': launch_manager.default_priority_fee,
            'pool': launch_manager.default_pool
        }
        logging.info("Creating token (Non-Jito Staggered)...")

        # Directly get the transaction bytes from PumpFun API - Like Standalone Script
        helius_url = f"https://rpc.helius.xyz/?api-key={launch_manager.helius_api_key}" # Define helius_url here
        response = requests.post(
            "https://pumpportal.fun/api/trade-local",
            headers={'Content-Type': 'application/json'},
            data=json.dumps(create_tx)
        )
        response.raise_for_status() # Ensure request was successful

        # Construct VersionedTransaction - Like Standalone Script
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [mint_keypair, launch_manager.main_wallet.keypair])

        # Prepare payload for Helius - Like Standalone Script
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config).to_json()


        helius_response = requests.post(
            url=helius_url,
            headers={"Content-Type": "application/json"},
            data=tx_payload # Send the prepared payload
        )
        helius_response.raise_for_status() # Check Helius response
        txSignature = helius_response.json().get('result', 'Transaction Failed')


        token.mint_address = str(mint_keypair.pubkey()) # Set mint address
        logging.info(f"Token {token.name} created with mint {token.mint_address} tx: {txSignature}")
        logging.info(f"Mint address for buys will be: {token.mint_address}") # ADDED LOGGING HERE

        # Phase 2: Sub-wallet buys (Non-Jito Staggered)
        signer_keypairs = [launch_manager.main_wallet.keypair]  # Start with dev wallet sig, if it exists
        sub_buy_txs = []
        for i in range(num_wallets):
            wallet = launch_manager.sub_wallets[i]
            amount = amounts[i]

            sub_buy_txs.append({
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": clone_address if clone_existing else str(token.mint_address), # Use token.mint_address from creation
                "denominatedInSol": "true",
                "amount": amount,
                "slippage": launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': "auto"
            })
            signer_keypairs.append(wallet.keypair)
    try:
        logging.info ("Submitting staggered buys (Non-Jito)...")
        # Now Submit with a delay
        for sub_buy_tx, signer_keypair in zip(sub_buy_txs, signer_keypairs):
            try:

                #Correct versioned Transaction
                sub_buy_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(sub_buy_tx, Keypair(), signer_keypair) # Mint keypair is dummy here
                tx = VersionedTransaction(VersionedTransaction.from_bytes(sub_buy_transaction_bytes['transaction'].encode('utf-8')).message, [signer_keypair])
                txSignature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx) # MODIFIED - Pass tx
                logging.info(f"Sub wallet bought token {token.name} mint {token.mint_address} tx: {txSignature}")
                await asyncio.sleep(random.uniform(0, delay_interval))
            except Exception as e:
                logging.error(f"error sending heliues{e}")
    except Exception as e:
        logging.error(f"Error in bundle_stagger_launch: {e}")
        raise

async def bundle_launch(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool, dev_buy_amount: float): # MODIFIED - Added dev_buy_amount
    """Executes a bundle launch with a specified number of wallets and amounts. CREATE TOKEN SEPARATELY"""
    logging.info(f"Executing bundle launch for token: {token.name} mint:None with {num_wallets} wallets, Jito: {use_jito}")

    try:
        mint_keypair = Keypair()
        token_metadata_for_ipfs = { # Metadata for IPFS upload - No URI yet
            'name': token.name,
            'symbol': token.symbol,
            'description': token.description,
            'telegram': token.telegram,
            'twitter': token.twitter,
            'website': token.website,
            'showName': 'true',
        }
        files = {}
        f = None # Initialize f outside the if block
        if token.image_path and os.path.exists(token.image_path): # Check if image path exists
            f = open(token.image_path, 'rb') # Open file, but DO NOT use 'with open'
            files['file'] = (os.path.basename(token.image_path), f, 'image/png') # or determine content type dynamically
        else:
            f = None # Ensure f is defined even if no image path

         # Directly using requests to upload to IPFS
        try:
            response = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files) # Explicitly use IPFS_UPLOAD_URL
            response.raise_for_status()
            ipfs_response = response.json()
            metadata_uri = ipfs_response.get('metadataUri', '')  # Get metadata URI, handle potential absence
            token.metadata_uri = metadata_uri  # Store metadata URI in Token object
            logging.info(f"IPFS upload successful, metadata URI: {metadata_uri}")
        except requests.exceptions.RequestException as e:
            logging.error(f"IPFS upload failed: {e}")
            raise

        final_token_metadata = { # Final token metadata with URI
            'name': token.name,
            'symbol': token.symbol,
            'uri': metadata_uri # Use the IPFS metadata URI
        }
        logging.info(f"Token creation data {final_token_metadata}")

        # Phase 1: Create the token (Non-Jito) - **SIGN WITH BOTH KEYPAIRS**
        create_tx = {
           'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
           'action': 'create',
           'tokenMetadata': final_token_metadata, # Use final token metadata with URI
           'mint': str(mint_keypair.pubkey()),
           'denominatedInSol': 'true',
           'amount': dev_buy_amount,  # MODIFIED - Use dev_buy_amount
           'slippage': launch_manager.default_slippage,
           'priorityFee': launch_manager.default_priority_fee,
           'pool': launch_manager.default_pool
        }

        logging.info("Creating token (Non-Jito)...")
        helius_url = f"https://rpc.helius.xyz/?api-key={launch_manager.helius_api_key}" # Define helius_url here
        response = requests.post(
            "https://pumpportal.fun/api/trade-local",
            headers={'Content-Type': 'application/json'},
            data=json.dumps(create_tx)
        )
        logging.info(f"Pumpfun Create Token API Request Data: {json.dumps(create_tx)}") # ADDED LOGGING
        logging.info(f"Pumpfun Create Token API Raw Response: {response.text}") # ADDED LOGGING
        response.raise_for_status() # Ensure request was successful


        # Construct VersionedTransaction - Like Standalone Script
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [mint_keypair, launch_manager.main_wallet.keypair])


        # Prepare payload for Helius - Like Standalone Script
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config).to_json()


        helius_response = requests.post(
            url=helius_url,
            headers={"Content-Type": "application/json"},
            data=tx_payload # Send the prepared payload
        )
        helius_response.raise_for_status() # Check Helius response
        txSignature = helius_response.json().get('result', 'Transaction Failed')


        token.mint_address = str(mint_keypair.pubkey()) # Set mint address
        logging.info(f"Token {token.name} created with mint {token.mint_address} tx: {txSignature}")
        logging.info(f"Mint address for buys will be: {token.mint_address}") # ADDED LOGGING HERE


        # Phase 2: Sub-wallet buys (Jito or Non-Jito) - No Changes Below
        sub_buy_txs = []
        signer_keypairs = []
        for i in range(num_wallets):
            wallet = launch_manager.sub_wallets[i]
            amount = amounts[i]

            sub_buy_txs.append({
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": str(token.mint_address),  # USE token.mint_address HERE!
                "denominatedInSol": "true",
                "amount": amount,
                "slippage": launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': "auto"
            })
            signer_keypairs.append(wallet.keypair)


        if use_jito:
            logging.info("Submitting sub-wallet buys as Jito bundle...")
            await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
            logging.info(f"All sub-wallet buys submitted as Jito bundle for token {token.name}")
        else:
             logging.info("Submitting sub-wallet buys as separate transactions (Non-Jito)...")
             for sub_buy_tx, signer_keypair in zip(sub_buy_txs, signer_keypairs):
                #Correct signing here too by creating versioned Transaction then sign the message
                sub_buy_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(sub_buy_tx, Keypair(), signer_keypair) # Mint keypair is dummy here
                #Correct versioned Transaction
                tx = VersionedTransaction(VersionedTransaction.from_bytes(sub_buy_transaction_bytes['transaction'].encode('utf-8')).message, [signer_keypair])
                txSignature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx) # MODIFIED - Pass tx
                logging.info(f"Sub wallet bought token {token.name} mint {token.mint_address} tx: {txSignature}")
             logging.info(f"All sub-wallet buys submitted as separate transactions (Non-Jito) for token {token.name}")


    except Exception as e:
        logging.error(f"Error in bundle_launch: {e}")
        raise


async def snipe_only(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool):
    """Executes a snipe only launch"""
    logging.info(f"Executing snipe only for token: {token.name} mint:{token.mint_address} with {num_wallets} wallets") # Fixed logging - using token.mint_address
    sub_buy_txs = []
    signer_keypairs = []

    if not token.mint_address: # ADDED CHECK HERE
        logging.error("Mint address is missing for snipe_only launch.")
        raise ValueError("Mint address is required for snipe_only launch.")


    for i in range(num_wallets):
        wallet = launch_manager.sub_wallets[i]
        amount = amounts[i]

        sub_buy_txs.append({
            "publicKey": str(wallet.keypair.pubkey()),
            "action": "buy",
            "mint": str(token.mint_address),  # USE token.mint_address HERE - IMPORTANT!
            "denominatedInSol": "true",
            "amount": amount,
            "slippage": launch_manager.default_slippage,
            'priorityFee': launch_manager.default_priority_fee,
            'pool': "auto"
        })
        signer_keypairs = [wallet.keypair]

    try:
        if use_jito:
            await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key,
                                                  sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
        else:
            # Normal transactions using create_local_transaction
            logging.info("Submitting transactions separately, non-jito way")
            mint_keypair = Keypair()  # This is not needed
            # 4. wallet buy
            for sub_buy_tx, signer_keypair in zip(sub_buy_txs, signer_keypairs):
                try:
                    sub_buy_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(
                        sub_buy_tx, mint_keypair, signer_keypair)

                    #Correct versioned Transaction
                    tx = VersionedTransaction(VersionedTransaction.from_bytes(sub_buy_transaction_bytes['transaction'].encode('utf-8')).message, [signer_keypair])
                    txSignature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx) # MODIFIED - Pass tx
                except Exception as e:
                    logging.error(f"Error creating or sending transaction: {e}")
                    raise #Re-raise

    except Exception as e:
        logging.error(f"Error in snipe_only: {e}")
        raise


async def staggered_buy(launch_manager, token: Token, additional_params: Dict):
    """Executes a staggered buy across wallets with delay."""
    logging.info(f"Executing staggered buy for token: {token.name} mint:{token.mint_address}")
    if additional_params is None or 'delay' not in additional_params:
        logging.warning("A delay needs to be specified for staggered buy")
        return
    delay = additional_params['delay']
    amount = additional_params.get('amount', launch_manager.stagger_default_amount)  # Default is 0.001
    slippage = additional_params.get('slippage', launch_manager.stagger_default_slippage)  # Default is 10
    priority_fee = additional_params.get('priority_fee',
                                          launch_manager.stagger_default_priority_fee)  # Default is 0.0001
    pool = additional_params.get('pool', launch_manager.stagger_default_pool)  # Default is pump
    sub_buy_txs = []
    signer_keypairs = []
    for i, wallet in enumerate(launch_manager.sub_wallets):
        try:

            sub_buy_txs.append({
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": token.mint_address,
                "denominatedInSol": "true",
                "amount": amount,
                "slippage": slippage,
                'priorityFee': priority_fee,
                'pool': pool
            })
            signer_keypairs = [wallet.keypair]

        except Exception as e:
            logging.error(f"Error during staggered buy {e}")
            raise
    logging.info("Submitting staggered buys (Non-Jito)...")
    try:
      for sub_buy_tx, signer_keypair in zip(sub_buy_txs, signer_keypairs):
        try:
           #Correct signing here too by creating versioned Transaction then sign the message
           sub_buy_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(sub_buy_tx, Keypair(), signer_keypair) # Mint keypair is dummy here
           tx = VersionedTransaction(VersionedTransaction.from_bytes(sub_buy_transaction_bytes['transaction'].encode('utf-8')).message, [signer_keypair])
           txSignature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx) # MODIFIED - Pass tx

        except Exception as e:
            logging.error(f"error sending heliues{e}")
    except Exception as e:
        logging.error(f"Error submitting bundle: {e}")
        raise

async def bundle_sell_all(launch_manager, percentage_to_sell: float):
    """Dumps all tokens across all wallets using bundle and jito"""
    logging.info(f"Dumping all wallets with percentage: {percentage_to_sell}")
    try:
        # Update balances before dumping
        await launch_manager.main_wallet.update_balance(launch_manager.rpc_client)
        for wallet in launch_manager.sub_wallets:
            await wallet.update_balance(launch_manager.rpc_client)

        transactions = []
        signer_keypairs = []
        # Sell tokens in each wallet
        for wallet in launch_manager.sub_wallets:
            for token_address in wallet.token_balances.keys():
                try:
                    data = {
                        "publicKey": str(wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": wallet.token_balances[token_address] * (percentage_to_sell / 100),
                        "denominatedInSol": "false",
                        "slippage": launch_manager.default_slippage,
                        "priorityFee": launch_manager.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(wallet.keypair)
                except Exception as e:
                    logging.error(f"Error selling from wallet {wallet.address} token {token_address}: {e}")

        # Sell tokens from the main wallet
        for token_address in launch_manager.main_wallet.token_balances.keys():
            try:

                data = {
                    "publicKey": str(launch_manager.main_wallet.keypair.pubkey()),
                    "action": "sell",
                    "mint": token_address,
                    "amount": launch_manager.main_wallet.token_balances[token_address] * (percentage_to_sell / 100),
                    "denominatedInSol": "false",
                    "slippage": launch_manager.default_slippage,
                    "priorityFee": launch_manager.default_priority_fee,
                    # Removed pool
                }
                transactions.append(data)
                signer_keypairs.append(launch_manager.main_wallet.keypair)
            except Exception as e:
                logging.error(f"Error selling from main wallet token {token_address}: {e}")
        await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, transactions, signer_keypairs, launch_manager.rpc_client) #Removed pump fun api url
    except Exception as e:
        logging.error(f"Error in dump_all: {e}")


# Global variables for synchronous WebSocket handling
_ws_connection = None
_sell_triggered = False
_current_sol_price_usd = 0.0
_global_liquidity_threshold_usd = 0.0
_token_config_for_ws: Optional[Token] = None
_creator_wallet_for_ws: Optional[Wallet] = None
_launch_manager_for_ws: Optional[Any] = None # Using Any to avoid circular import if LaunchManager is not fully imported
_helius_api_key_for_ws: Optional[str] = None
_bonding_curve_address_for_ws: Optional[Pubkey] = None


def _on_message(ws, message):
    """
    Handles incoming messages from the WebSocket.
    """
    global _sell_triggered, _current_sol_price_usd, _global_liquidity_threshold_usd, _token_config_for_ws, _creator_wallet_for_ws, _launch_manager_for_ws, _helius_api_key_for_ws

    try:
        data = json.loads(message)
        
        if data.get("method") == "accountNotification":
            result_value = data.get("params", {}).get("result", {}).get("value")
            if result_value:
                lamports = result_value.get("lamports")
                sol_liquidity = lamports / 1_000_000_000
                
                logging.info('\n--- Bonding Curve Pool Update Detected (Price/Liquidity Change) ---')
                logging.info(f"Token Mint: {_token_config_for_ws.mint_address}")
                logging.info(f"Pool SOL Balance: {sol_liquidity:.9f} SOL ({lamports} lamports)")
                logging.info(f"Owner Program: {result_value.get('owner')}")

                if _current_sol_price_usd > 0:
                    usd_liquidity = sol_liquidity * _current_sol_price_usd
                    logging.info(f"Current USD liquidity: {usd_liquidity:.2f} USD")

                    if usd_liquidity >= _global_liquidity_threshold_usd:
                        logging.info(f"[{_token_config_for_ws.name}] Liquidity threshold ({_global_liquidity_threshold_usd} USD) met! Initiating sell.")
                        logging.info(f"[{_token_config_for_ws.name}] Liquidity threshold ({_global_liquidity_threshold_usd} USD) met! Setting sell trigger.")
                        _sell_triggered = True # Signal to stop monitoring
                        ws.close() # Close WebSocket connection
                else:
                    logging.warning("SOL price not available, cannot calculate USD liquidity.")

        elif data.get("id") == 1 and isinstance(data.get("result"), int):
            logging.info(f"Subscription confirmed with ID: {data.get('result')}")

        elif data.get("error"):
            logging.error(f"\n!!! RPC Error !!!: {data.get('error')}")

    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from message: {message}")
    except Exception as e:
        logging.error(f"An unexpected error occurred in _on_message: {e}")

def _on_error(ws, error):
    logging.error(f"### WebSocket Error ###: {error}")

def _on_close(ws, close_status_code, close_msg):
    logging.info(f"Disconnected from Solana. Status Code: {close_status_code}, Message: {close_msg}")

def _on_open(ws):
    """
    Handles WebSocket open events and initiates the subscription.
    """
    logging.info("Connected to Solana WebSocket!")
    ws.send(json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "accountSubscribe",
        "params": [
            str(_bonding_curve_address_for_ws),
            {"encoding": "jsonParsed", "commitment": "confirmed"}
        ]
    }))
    logging.info(f"Subscribing to account updates for {_bonding_curve_address_for_ws}.")

async def _perform_sell_action(launch_manager, token_config: Token, creator_wallet: Wallet, helius_api_key: str): # Removed creator_token_balance parameter
    """Performs the sell action when liquidity threshold is met or timed out."""
    await creator_wallet.update_balance(launch_manager.rpc_client) # Update balance before selling
    creator_token_balance = await transaction.get_token_balance(
        rpc_url=launch_manager.rpc_url,
        mint_address=token_config.mint_address,
        public_key=str(creator_wallet.keypair.pubkey()),
        helius_api_key=helius_api_key
    )

    if creator_token_balance > 0:
        sell_tx_data = {
            "publicKey": str(creator_wallet.keypair.pubkey()),
            "action": "sell",
            "mint": token_config.mint_address,
            "amount": creator_token_balance, # Sell 100%
            "denominatedInSol": "false",
            "slippage": launch_manager.default_slippage,
            "priorityFee": launch_manager.default_priority_fee,
            "pool": launch_manager.default_pool
        }
        
        logging.info(f"Selling {creator_token_balance} of {token_config.name} from creator wallet {creator_wallet.address}")
        
        sell_transaction_bytes = await launch_manager.pumpfun_api.create_local_transaction(sell_tx_data, Keypair(), creator_wallet.keypair)
        
        sell_tx = VersionedTransaction(VersionedTransaction.from_bytes(sell_transaction_bytes['transaction'].encode('utf-8')).message, [creator_wallet.keypair])
        sell_tx_signature = await transaction.send_helius_transaction(helius_api_key, sell_tx)
        logging.info(f"Creator wallet {creator_wallet.address} sold {token_config.name}, tx: {sell_tx_signature}")
    else:
        logging.warning(f"Creator wallet {creator_wallet.address} has no {token_config.name} to sell.")


async def monitor_liquidity_and_sell(launch_manager, token_config: Token, creator_wallet: Wallet, liquidity_threshold_usd: float, helius_api_key: str):
    """Monitors the liquidity of a token's bonding curve and sells when a threshold is met."""
    global _current_sol_price_usd, _bonding_curve_address_for_ws, _sell_triggered, _global_liquidity_threshold_usd, _token_config_for_ws, _creator_wallet_for_ws, _launch_manager_for_ws, _helius_api_key_for_ws
    
    _current_sol_price_usd = await get_sol_price_usd()
    if _current_sol_price_usd == 0.0:
        logging.error("Failed to get SOL price. Cannot monitor liquidity.")
        return

    token_mint_pubkey = Pubkey.from_string(token_config.mint_address)
    _bonding_curve_address_for_ws, _ = get_associated_bonding_curve_address(token_mint_pubkey, PUMP_FUN_PROGRAM_ID)
    _global_liquidity_threshold_usd = liquidity_threshold_usd
    _token_config_for_ws = token_config
    _creator_wallet_for_ws = creator_wallet
    _launch_manager_for_ws = launch_manager
    _helius_api_key_for_ws = helius_api_key
    _sell_triggered = False # Reset flag for new monitoring session
    
    if not _bonding_curve_address_for_ws:
        logging.error(f"Could not find bonding curve address for {token_config.name}. Skipping liquidity monitoring.")
        return
 
    helius_ws_url = config.get('DEFAULT', 'HELIUS_WEBSOCKET_URL')
    sniper_farmer_time_to_sell_minutes = int(config.get('DEFAULT', 'SNIPER_FARMER_TIME_TO_SELL_MINUTES'))
    
    logging.info(f"Monitoring Token Mint: {token_config.mint_address}")
    logging.info(f"Calculated Bonding Curve Address (The Pool): {_bonding_curve_address_for_ws}")
    logging.info(f"Connecting to: {helius_ws_url}")

    ws = websocket.WebSocketApp(
        helius_ws_url,
        on_open=_on_open,
        on_message=_on_message,
        on_error=_on_error,
        on_close=_on_close
    )

    import threading
    ws_thread = threading.Thread(target=ws.run_forever, kwargs={
        "sslopt": {"cert_reqs": ssl.CERT_NONE},
        "ping_interval": 10
    })
    ws_thread.daemon = True
    ws_thread.start()

    start_time = time.time()
    # Keep the asyncio loop running until _sell_triggered is set or timeout occurs
    while not _sell_triggered:
        elapsed_time = time.time() - start_time
        if elapsed_time > sniper_farmer_time_to_sell_minutes * 60:
            logging.info(f"[{token_config.name}] Time limit ({sniper_farmer_time_to_sell_minutes} minutes) reached. Initiating sell.")
            _sell_triggered = True
            ws.close()
            await _perform_sell_action(
                _launch_manager_for_ws,
                _token_config_for_ws,
                _creator_wallet_for_ws,
                _helius_api_key_for_ws
            )
            break
        await asyncio.sleep(1) # Check the flag periodically
    
    logging.info("Monitoring stopped.")

    if _sell_triggered: # If sell was triggered by liquidity threshold
        await _perform_sell_action(
            _launch_manager_for_ws,
            _token_config_for_ws,
            _creator_wallet_for_ws,
            _helius_api_key_for_ws
        )

async def sniper_farmer_launch(launch_manager, token_configs: List[Token], liquidity_threshold_usds: List[float], dev_buy_amounts: List[float], use_jito: bool):
    """
    Executes the Sniper Farmer launch strategy:
    1. Creates tokens one by one using generated sub-wallets.
    2. Monitors liquidity for each token in real-time.
    3. Sells creator's holding when liquidity reaches a specified USD threshold.
    4. Reclaims all SOL to the main wallet after all operations.
    """
    logging.info(f"Starting Sniper Farmer launch for {len(token_configs)} tokens.")
    
    created_tokens_info = [] # To store mint address and associated wallet for selling

    try:
        # Phase 1: Create tokens one by one
        for i, token_config in enumerate(token_configs):
            wallet = launch_manager.sub_wallets[i] # Assign each token to a sub-wallet
            logging.info(f"\n[bold green]--- Creating Token for Wallet {i+1} ({wallet.address}) ---[/bold green]")

            mint_keypair = Keypair()
            
            token_metadata_for_ipfs = {
                'name': token_config.name,
                'symbol': token_config.symbol,
                'description': token_config.description,
                'telegram': token_config.telegram,
                'twitter': token_config.twitter,
                'website': token_config.website,
                'showName': 'true',
            }

            files = {}
            f = None
            if token_config.image_path and os.path.exists(token_config.image_path):
                f = open(token_config.image_path, 'rb')
                files['file'] = (os.path.basename(token_config.image_path), f, 'image/png')
                logging.info(f"Uploading image from {token_config.image_path}")
            else:
                logging.info("No image path provided or file not found. Proceeding without image.")

            try:
                response = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files)
                response.raise_for_status()
                ipfs_response = response.json()
                metadata_uri = ipfs_response.get('metadataUri', '')
                token_config.metadata_uri = metadata_uri
                logging.info(f"IPFS upload successful, metadata URI: {metadata_uri}")
            except requests.exceptions.RequestException as e:
                logging.error(f"IPFS upload failed for token {token_config.name}: {e}")
                raise
            finally:
                if f:
                    f.close()

            final_token_metadata = {
                'name': token_config.name,
                'symbol': token_config.symbol,
                'uri': metadata_uri
            }

            create_tx = {
                'publicKey': str(wallet.keypair.pubkey()), # Creator is the sub-wallet
                'action': 'create',
                'tokenMetadata': final_token_metadata,
                'mint': str(mint_keypair.pubkey()),
                'denominatedInSol': 'true',
                'amount': dev_buy_amounts[i],
                'slippage': launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': launch_manager.default_pool
            }

            logging.info(f"Creating token {token_config.name} (Non-Jito)...")
            helius_url = f"https://rpc.helius.xyz/?api-key={launch_manager.helius_api_key}"
            response = requests.post(
                "https://pumpportal.fun/api/trade-local",
                headers={'Content-Type': 'application/json'},
                data=json.dumps(create_tx)
            )
            response.raise_for_status()

            tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [mint_keypair, wallet.keypair])

            commitment = CommitmentLevel.Confirmed
            config = RpcSendTransactionConfig(preflight_commitment=commitment)
            tx_payload = SendVersionedTransaction(tx, config).to_json()

            helius_response = requests.post(
                url=helius_url,
                headers={"Content-Type": "application/json"},
                data=tx_payload
            )
            helius_response.raise_for_status()
            txSignature = helius_response.json().get('result', 'Transaction Failed')

            token_config.mint_address = str(mint_keypair.pubkey())
            logging.info(f"Token {token_config.name} created with mint {token_config.mint_address} by wallet {wallet.address}, tx: {txSignature}")
            
            created_tokens_info.append({
                'token': token_config,
                'creator_wallet': wallet,
                'mint_keypair': mint_keypair # Keep mint_keypair for signing if needed
            })

            # Phase 2: Monitor liquidity and sell
            logging.info(f"Monitoring liquidity for token {token_config.name} (mint: {token_config.mint_address})...")
            
            await monitor_liquidity_and_sell(
                launch_manager,
                token_config,
                wallet,
                liquidity_threshold_usds[i], # Use individual liquidity threshold
                launch_manager.helius_api_key
            )
            logging.info(f"Finished monitoring and selling for {token_config.name}.")

        # Phase 3: Reclaim all SOL to the main wallet
        logging.info("Reclaiming all SOL from sub-wallets to main wallet...")
        await launch_manager.reclaim_sol()
        logging.info("All SOL reclaimed.")

    except Exception as e:
        logging.error(f"Error in sniper_farmer_launch: {e}")
        raise