# launch_manager.py
import random
from solders.keypair import Keypair
from base58 import b58encode
from solders.pubkey import Pubkey
from wallet import Wallet, Token, _create_sub_wallets, _save_wallets # Added _save_wallets
import json
import time
import os
from solders.transaction import VersionedTransaction, Transaction
from typing import Dict, List, Optional, Any
from solders.message import Message
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
from solders.commitment_config import CommitmentLevel
from solders.hash import Hash
from solana.rpc.async_api import AsyncClient
import logging
import requests
import configparser
import os
import transaction  # Import the new transaction module
import asyncio

# --- Logging Setup ---
config = configparser.ConfigParser()
config.read('config.ini')
log_file = config.get('DEFAULT', 'LOG_FILE', fallback='infinityato.log')
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_path = os.path.join(log_dir, log_file)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

class LaunchManager:
    def __init__(self, rpc_url: str, helius_api_key:str, pumpfun_api_url:str, main_wallet_seed: str, num_sub_wallets: int = 20, websocket_url: str = "wss://pumpportal.fun/api/data", sniper_farmer_time_to_sell_minutes: int = 5, output_folder: str = "output"):
        self.rpc_url = rpc_url
        self.helius_api_key = helius_api_key
        self.pumpfun_api_url = pumpfun_api_url
        self.main_wallet = Wallet(main_wallet_seed)
        self.sub_wallets = []
        self.num_sub_wallets = num_sub_wallets
        self.rpc_client = None  # Will be initialized in self.init()
        self.websocket_url = websocket_url
        self.sniper_farmer_time_to_sell_minutes = sniper_farmer_time_to_sell_minutes # New parameter
        self.websocket = None
        self.connected = False
        self.subscriptions = set()
        self.output_folder = output_folder
        self.default_slippage: int = 10
        self.default_priority_fee: float = 0.0005
        self.stagger_default_amount: float = 0.001
        self.stagger_default_slippage: int = 10
        self.stagger_default_priority_fee: float = 0.0001

        self.default_pool: str = "pump" # ADDED

    async def init(self):
        try:
            await self.main_wallet.create_keypair()
            if self.main_wallet.address is None:
                raise Exception("Failed to load dev wallet from seed phrase. Check seed and RPC URL.")
            self.rpc_client = AsyncClient(self.rpc_url)  # Initialize AsyncClient here
            self.main_wallet.helius_api_key = self.helius_api_key # pass heluis api key
            # Removed await self.generate_wallets() from init
            logging.info(f"Launch Manager Initialized, main wallet address: {self.main_wallet.address}")
        except Exception as e:
            logging.error(f"Error during initialization: {e}")
            raise

    async def create_sub_wallets(self):
       """Creates multiple subwallets."""
       try:
          self.sub_wallets = await _create_sub_wallets(self.num_sub_wallets)
          for wallet in self.sub_wallets:
               wallet.helius_api_key = self.helius_api_key
       except Exception as e:
          logging.error(f"Error creating sub-wallets: {e}")
          raise

    async def generate_wallets(self):
        try:
           # Removed main_wallet from the call as it's a class member
           self.sub_wallets = await _create_sub_wallets(self.num_sub_wallets)
           await _save_wallets(self.output_folder, self.main_wallet, self.sub_wallets)
           for wallet in self.sub_wallets:
               wallet.helius_api_key = self.helius_api_key
        except Exception as e:
           logging.error(f"Error generating wallets: {e}")
           raise

    async def fund_wallets(self, amounts: List[float]):
        """Fund wallets with the given amounts."""
        try:
            # Update Dev Wallet Balance Before Funding
            await self.main_wallet.update_balance(self.rpc_client)
            logging.info(f"Funding from Main Wallet: {self.main_wallet.address} with balance: {self.main_wallet.balance}")
            # Update all sub-wallets balances
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            for i, wallet in enumerate(self.sub_wallets):
                amount = amounts[i]
                if self.main_wallet.balance < amount:
                    logging.warning(
                        f"Dev Wallet {self.main_wallet.address} has insufficient balance.  Balance: {self.main_wallet.balance}, Requested: {amount}.  Skipping this wallet."
                    )
                    continue  # Skip to the next wallet

                logging.info(f"Funding wallet {wallet.address} with {amount} SOL from {self.main_wallet.address}")

                # Call Wallet's fund method.
                await wallet.fund(self.rpc_url, self.helius_api_key, amount, self.main_wallet.keypair, self.rpc_client)
                await asyncio.sleep(2) # ADDED DELAY

                # Update main_wallet balance *after* each sub-wallet funding
                await self.main_wallet.update_balance(self.rpc_client)
                await asyncio.sleep(2) # ADDED DELAY

        except Exception as e:
            logging.error(f"Error funding wallets: {e}")
            raise



    async def transfer_sol(self, from_wallet: Wallet, to_address: str, amount: float):
        """Transfers SOL."""
        try:
            if not from_wallet.is_initialized:
                raise ValueError(f"Wallet {from_wallet.address} is not initialized.")
            if amount <= 0:
                raise ValueError("Transfer amount must be greater than zero.")

            # Update balances before transferring
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            logging.info(f"Transferring {amount} SOL from wallet {from_wallet.address} to {to_address}") #ADDED LOG
            # Reclaim SOL using the wallet transfer function
            await from_wallet.transfer_sol(self.rpc_url, self.helius_api_key, to_address)
            logging.info(
                f"Transferred {amount} SOL from wallet {from_wallet.address} to {to_address} via transfer sol function")

        except Exception as e:
            logging.error(f"Error transferring SOL from wallet {from_wallet.address} to {to_address}: {e}")
            raise

    async def dump_all(self, percentage_to_sell: float):
        """Dumps all tokens across all wallets"""
        logging.info(f"Dumping all wallets with percentage: {percentage_to_sell}")
        try:
            # Update balances before dumping
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            transactions = []
            signer_keypairs = []
            # Sell tokens in each wallet
            for wallet in self.sub_wallets:
                for token_address in wallet.token_balances.keys():
                    try:
                        data = {
                            "publicKey": str(wallet.keypair.pubkey()),
                            "action": "sell",
                            "mint": token_address,
                            "amount": wallet.token_balances[token_address] * (percentage_to_sell / 100),
                            "denominatedInSol": "false",
                            "slippage": self.default_slippage,
                            "priorityFee": self.default_priority_fee,
                            # Removed pool
                        }
                        transactions.append(data)
                        signer_keypairs.append(wallet.keypair)
                    except Exception as e:
                        logging.error(f"Error selling from wallet {wallet.address} token {token_address}: {e}")

            # Sell tokens from the main wallet
            for token_address in self.main_wallet.token_balances.keys():
                try:

                    data = {
                        "publicKey": str(self.main_wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": self.main_wallet.token_balances[token_address] * (percentage_to_sell / 100),
                        "denominatedInSol": "false",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(self.main_wallet.keypair)
                except Exception as e:
                    logging.error(f"Error selling from main wallet token {token_address}: {e}")
            await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client) # Re-added pump fun api url
        except Exception as e:
            logging.error(f"Error in dump_all: {e}")

    async def reclaim_sol(self):
        """Reclaims all SOL back to the funding wallet"""
        logging.info(f"Reclaiming SOL back to funding wallet {self.main_wallet.address}")
        try:
            # Update balances before reclaiming
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            for wallet in self.sub_wallets:
                logging.info(f"Reclaiming SOL from sub-wallet: {wallet.address}") #ADDED LOG
                await wallet.reclaim_sol(self.rpc_url, self.helius_api_key, self.main_wallet.address) # CHANGED HERE

        except Exception as e:
            logging.error(f"Error reclaiming SOL: {e}")

    async def delayed_sell(self, delay_in_seconds: int):
        """Sells 100% of tokens with a delay between wallets."""
        logging.info(f"Selling all tokens with delay of {delay_in_seconds}")

        # Update balances before selling
        await self.main_wallet.update_balance(self.rpc_client)
        for wallet in self.sub_wallets:
            await wallet.update_balance(self.rpc_client)

        transactions = []
        signer_keypairs = []
        for wallet in self.sub_wallets:
            try:
                for token_address in wallet.token_balances.keys():
                    try:
                        await asyncio.sleep(delay_in_seconds)

                        data = {
                            "publicKey": str(wallet.keypair.pubkey()),
                            "action": "sell",
                            "mint": token_address,
                            "amount": wallet.token_balances[token_address],
                            "denominatedInSol": "false",
                            "slippage": self.default_slippage,
                            "priorityFee": self.default_priority_fee,
                            # Removed pool
                        }
                        transactions.append(data)
                        signer_keypairs.append(wallet.keypair)
                    except Exception as e:
                        logging.error(f"Error selling from wallet {wallet.address} token {token_address}: {e}")
            except Exception as e:
                logging.error(f"Error in delayed_sell for wallet {wallet.address}: {e}")
        await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client) # Removed pump fun

    async def transfer_tokens(self, from_wallet: Wallet, to_wallet_address: str, token_address: str = None):
        """Transfers all tokens from a wallet to specified dev wallet"""
        logging.info(f"Transferring all tokens from {from_wallet.address} to {to_wallet_address}")
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            if not token_address:
                logging.error("Token address missing for token transfer.")
                return
            recent_blockhash_str = transaction.get_recent_blockhash_sync(self.rpc_url)
            recent_blockhash = Hash.from_string(recent_blockhash_str)
            from spl.token.instructions import transfer, TransferParams
            from spl.token.constants import TOKEN_PROGRAM_ID
            from spl.associated_token_account import get_associated_token_address

            source_token_account = get_associated_token_address(from_wallet.keypair.pubkey(), Pubkey.from_string(token_address))
            dest_token_account = get_associated_token_address(Pubkey.from_string(to_wallet_address), Pubkey.from_string(token_address))
            balance = await transaction.get_token_balance(self.rpc_url, token_address, from_wallet.address, self.helius_api_key) # Pass helius_api_key
            transfer_instruction = transfer(
                TransferParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=source_token_account,
                    dest=dest_token_account,
                    owner=from_wallet.keypair.pubkey(),
                    amount=int(balance),
                )
            )
            message = Message([transfer_instruction], recent_blockhash=recent_blockhash)
            transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[from_wallet.keypair])
            transaction_obj.sign([from_wallet.keypair], recent_blockhash=recent_blockhash)

            signature = await transaction.send_helius_transaction(self.helius_api_key, transaction_obj) # Use transaction_obj
            logging.info(f"Sent tokens from wallet {from_wallet.address} to dev wallet {to_wallet_address}")
        except Exception as e:
            logging.error(f"Error transferring tokens: {e}")
            raise

    async def single_wallet_sell(self, wallet_address: str, percentage_to_sell: float = 100):
        """Sells a percentage of tokens from a specific wallet"""
        logging.info(f"Selling {percentage_to_sell}% of tokens from wallet {wallet_address}")

        try:
            # Update balances before selling from single wallet
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)
            transactions = []
            signer_keypairs = []
            target_wallet = next((wallet for wallet in self.sub_wallets if wallet.address == wallet_address), None)
            if not target_wallet:
                logging.error(f"Wallet with address {wallet_address} not found.")
                return

            for token_address in target_wallet.token_balances.keys():
                try:

                    data = {
                        "publicKey": str(target_wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": target_wallet.token_balances[token_address] * (percentage_to_sell / 100),
                        "denominatedInSol": "false",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(target_wallet.keypair)
                except Exception as e:
                    logging.error(f"Error selling from wallet {target_wallet.address} token {token_address}: {e}")
            await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client) # Removed pumpfun

        except Exception as e:
            logging.error(f"Error in single_wallet_sell: {e}")

    async def dev_dump_all(self):
        """Dumps all the tokens from sub wallets to the dev wallet and sell all from the dev wallet"""
        logging.info("Executing Dev Dump All")
        try:
            # Update balances before dev dump all
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            transactions = []
            signer_keypairs = []
            # Transfer tokens from sub-wallets to dev wallet
            for wallet in self.sub_wallets:
                for token_address in wallet.token_balances.keys():
                    await self.transfer_tokens(wallet, self.main_wallet.address, token_address)

            # Sell tokens from dev wallet
            for token_address, balance in self.main_wallet.token_balances.items():
                try:

                    data = {
                        "publicKey": str(self.main_wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": balance,
                        "denominatedInSol": "false",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(self.main_wallet.keypair)
                except Exception as e:
                    logging.error(f"Error selling tokens from dev wallet: {e}")
            await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client) # Removed pumpfun

        except Exception as e:
            logging.error(f"Error in dev_dump_all: {e}")
        logging.info("Dev Dump All Completed")

    async def transfer_sell(self, to_wallet_address: str):
        """Transfers all tokens to a specific wallet and sells all from that wallet"""
        logging.info(f"Transferring all tokens to {to_wallet_address} and selling")
        try:
            # Update balances before transfer and sell
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)
            transactions = []
            signer_keypairs = []
            target_wallet = next((wallet for wallet in self.sub_wallets if wallet.address == to_wallet_address), None)
            if not target_wallet:
                logging.error(f"Wallet with address {to_wallet_address} not found.")
                return

            #Transfer all the tokens
            for token_address, balance in self.main_wallet.token_balances.items():
                try:
                   await self.transfer_tokens(self.main_wallet, to_wallet_address, token_address)
                except Exception as e:
                  logging.error(f"Error selling tokens from dev wallet: {e}")

            # Sell tokens from target wallet
            for token_address, balance in target_wallet.token_balances.items():
                try:

                    data = {
                        "publicKey": str(target_wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": balance,
                        "denominatedInSol": "false",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(target_wallet.keypair)
                except Exception as e:
                    logging.error(f"Error selling tokens from dev wallet: {e}")
            await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client) # Removed pumpfun

        except Exception as e:
            logging.error(f"Error in transfer_sell: {e}")
        logging.info("Transfer Sell Completed")

    async def wallet_warmup(self):
        """Buys a small amount of random tokens and sells back."""
        logging.info("Executing Wallet Warmup")
        try:
            # Update balances before wallet warmup
            await self.main_wallet.update_balance(self.rpc_client)
            for wallet in self.sub_wallets:
                await wallet.update_balance(self.rpc_client)

            transactions = []
            signer_keypairs = []
            # 1. Fetch Verified Pump Mints
            rugcheck_url = "https://api.rugcheck.xyz/v1/stats/verified"
            response = requests.get(rugcheck_url)
            response.raise_for_status()
            rugcheck_data = response.json()
            pump_mints = [item['mint'] for item in rugcheck_data if item['mint'].endswith('pump')]
            if not pump_mints:
                logging.warning("No verified pump mints found.")
                return

            # Prepare Wallets and Transactions
            num_wallets = len(self.sub_wallets)
            mints_per_wallet = len(pump_mints) // num_wallets
            if mints_per_wallet == 0:
                logging.warning("Not enough pump mints for all wallets.")
                return

            # Loop through wallets
            for i, wallet in enumerate(self.sub_wallets):
                start_index = i * mints_per_wallet
                end_index = start_index + mints_per_wallet
                wallet_mints = pump_mints[start_index:end_index]

                token_address = random.choice(wallet_mints)
                try:
                    # Buy small amount
                    data = {
                        "publicKey": str(wallet.keypair.pubkey()),
                        "action": "buy",
                        "mint": token_address,
                        "amount": 0.001,  # Small buy amount
                        "denominatedInSol": "true",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(wallet.keypair)
                    await asyncio.sleep(10)
                    # Sell back
                    data = {
                        "publicKey": str(wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": token_address,
                        "amount": wallet.token_balances.get(token_address, 0),  # should check tokens for the current account
                        "denominatedInSol": "false",
                        "slippage": self.default_slippage,
                        "priorityFee": self.default_priority_fee,
                        # Removed pool
                    }
                    transactions.append(data)
                    signer_keypairs.append(wallet.keypair)

                    logging.info(f"Wallet {wallet.address} warmed up with token {token_address}")
                except Exception as e:
                    logging.error(f"Error warming up wallet {wallet.address} : {e}")
            await transaction.submit_jito_bundle(self.pumpfun_api_url, self.helius_api_key, transactions, signer_keypairs, self.rpc_client)

        except Exception as e:
            logging.error(f"Error in wallet_warmup: {e}")
        logging.info("Wallet Warmup Completed")

    async def burn_dev_supply(self, token_address: str): # MODIFIED - burn_dev_supply function
        """Burns all tokens of a specified address from the dev wallet."""
        logging.info(f"Burning all tokens for address: {token_address} from dev wallet") # MODIFIED LOGGING
        BURN_ADDRESS = "11111111111111111111111111111111" # Burn Address

        try:
            # Update balances before burning
            await self.main_wallet.update_balance(self.rpc_client)
            dev_wallet_balance = await transaction.get_token_balance( # MODIFIED - Use get_token_balance
                rpc_url=self.rpc_url,
                mint_address=token_address,
                public_key=str(self.main_wallet.keypair.pubkey()),
                helius_api_key=self.helius_api_key # <--- ADD HELIUS API KEY HERE - IMPORTANT!
            )
            logging.info(f"Dev wallet token balance before burn: {dev_wallet_balance}") # Log balance

            if dev_wallet_balance <= 0:
                logging.warning(f"No tokens to burn for mint {token_address} in dev wallet") # MODIFIED LOGGING
                return

            # Transfer tokens to burn address using transfer_spl_token function
            burn_amount = dev_wallet_balance # Burn all tokens
            tx_signature = await transaction.transfer_spl_token( # MODIFIED - Use transfer_spl_token
                sender_keypair=self.main_wallet.keypair,
                recipient_address=BURN_ADDRESS,
                token_mint_address=token_address,
                amount=burn_amount,
                helius_api_key=self.helius_api_key,
                rpc_client=self.rpc_client # Pass rpc_client
            )


            logging.info(f"Burned {burn_amount} tokens of {token_address} from dev wallet. Transaction Signature: {tx_signature}") # MODIFIED LOGGING


        except Exception as e:
            logging.error(f"Error in burn_dev_supply for token {token_address}: {e}")


    async def _send_websocket_message(self, payload: Dict):
        """Helper function to send a message through the WebSocket."""
        if self.websocket is None or not self.connected:
            logging.warning("Websocket connection is closed or not established")
            return
        try:
            import websockets
            await self.websocket.send(json.dumps(payload))
        except Exception as e:
            logging.error(f"Error sending message: {payload} error {e}")
            raise

    async def connect_websocket(self):
        """Connects to the WebSocket and starts listening for messages."""
        try:
            import websockets
            self.websocket = await websockets.connect(self.websocket_url)
            self.connected = True
            logging.info("WebSocket connection established.")
            await self._receive_messages()
        except Exception as e:
            self.connected = False
            logging.error(f"Error establishing WebSocket connection: {e}")
            raise

    async def _receive_messages(self):
        """Receives messages from the websocket and prints them"""
        if self.websocket is None or not self.connected:
            logging.warning("Websocket connection was closed, can't receive messages")
            return
        try:
            while True:
                message = await self.websocket.recv()
                logging.info(f"Received Message: {message}")
                try:
                    data = json.loads(message)
                    if data.get("method") == "subscribeNewToken":
                        logging.info(f"New Token Found {data}")
                except Exception as e:
                    logging.error(f"Error processing message: {e}")
        except Exception as e:
            logging.warning("Websocket closed unexpectedly")
            self.connected = False
            await self.close_websocket()
            raise

    async def close_websocket(self):
        """Closes the websocket connection."""
        try:
            if self.websocket:
                await self.websocket.close()
                self.connected = False
                logging.info("Websocket connection closed")
        except Exception as e:
            logging.error(f"Error closing websocket: {e}")
            raise

    async def close(self):
        """Closes the RPC client."""
        try:
            if self.rpc_client:
                await self.rpc_client.close()
            await self.close_websocket()
        except Exception as e:
            logging.error(f"Error during close: {e}")
            raise