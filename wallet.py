# wallet.py
import asyncio
import os
from solders.keypair import Keypair
from base58 import b58encode, b58decode
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction, VersionedTransaction  # Import both
from solders.commitment_config import CommitmentLevel
import time
import requests
import json
from typing import Dict, Optional, Any
from solders.message import Message
from solders.hash import Hash
from solders.system_program import transfer, TransferParams
import logging
from mnemonic import Mnemonic
import transaction  # Import the transaction module
import random
import logging
import configparser
import os
from bip_utils import Bip39SeedGenerator, Bip32Slip10Ed25519
import base58

config = configparser.ConfigParser()
config.read('config.ini')
log_file = config.get('DEFAULT', 'LOG_FILE', fallback='infinityato.log')
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_path = os.path.join(log_dir, log_file)
logging.basicConfig(
    filename=log_path, level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', filemode='w'
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)


class Wallet:
    def __init__(self, seed_phrase: Optional[str] = None):
        self.keypair: Optional[Keypair] = None
        self.balance: float = 0
        self.seed_phrase: Optional[str] = seed_phrase
        self.address: Optional[str] = None
        self.token_balances: Dict[str, float] = {}
        self.name: Optional[str] = None
        self.bio: Optional[str] = None
        self.is_initialized: bool = False
        self.helius_api_key: Optional[str] = None
        self.default_slippage: int = 10
        self.default_priority_fee: float = 0.0005

    async def create_keypair(self):
        """Creates a keypair for a wallet using BIP44 derivation."""
        try:
            if self.seed_phrase:
                seed_bytes = Bip39SeedGenerator(self.seed_phrase).Generate()
                bip32_mst_ctx = Bip32Slip10Ed25519.FromSeed(seed_bytes)
                derivation_path = "m/44'/501'/0'/0'"
                bip32_der_ctx = bip32_mst_ctx.DerivePath(derivation_path)
                private_key = bip32_der_ctx.PrivateKey().Raw()
                self.keypair = Keypair.from_seed(private_key)
                pub_key_bytes = bip32_der_ctx.PublicKey().RawCompressed().ToBytes()
                self.address = base58.b58encode(pub_key_bytes[1:]).decode()
                logging.info(f'Created wallet with address: {self.address} from mnemonic')
            else:
                mnemonic = Mnemonic('english')
                self.seed_phrase = mnemonic.generate()
                seed_bytes = Bip39SeedGenerator(self.seed_phrase).Generate()
                bip32_mst_ctx = Bip32Slip10Ed25519.FromSeed(seed_bytes)
                derivation_path = "m/44'/501'/0'/0'"
                bip32_der_ctx = bip32_mst_ctx.DerivePath(derivation_path)
                private_key = bip32_der_ctx.PrivateKey().Raw()
                self.keypair = Keypair.from_seed(private_key)
                pub_key_bytes = bip32_der_ctx.PublicKey().RawCompressed().ToBytes()
                self.address = base58.b58encode(pub_key_bytes[1:]).decode()
                logging.info(f'Created wallet with address: {self.address} generated')
            self.is_initialized = True
        except Exception as e:
            logging.error(f'Error creating keypair: {e}')
            raise

    async def fund(self, rpc_url: str, helius_api_key: str, sol_amount: float, funder_keypair: Keypair, rpc_client: AsyncClient,
                    commitment: CommitmentLevel = CommitmentLevel.Confirmed):
        """Funds the wallet with SOL using Helius - Legacy Transaction"""
        try:
            logging.info(f"Funding wallet: {self.address} from wallet: {funder_keypair.pubkey()}")
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            recent_blockhash_str = transaction.get_recent_blockhash_sync(rpc_url)
            recent_blockhash = Hash.from_string(recent_blockhash_str)
            recipient_public_key = self.keypair.pubkey()
            lamports = int(sol_amount * 1_000_000_000)
            transfer_instruction = transfer(
                TransferParams(
                    from_pubkey=funder_keypair.pubkey(),
                    to_pubkey=recipient_public_key,
                    lamports=lamports,
                )
            )
            message = Message.new_with_blockhash(
                [transfer_instruction], funder_keypair.pubkey(), recent_blockhash
            )
            transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[funder_keypair])
            transaction_obj.sign([funder_keypair], recent_blockhash=recent_blockhash)

            signature = await transaction.send_helius_transaction(helius_api_key, transaction_obj)
            logging.info(f'Wallet {self.address} funded with {sol_amount} SOL via Helius, txid: {signature}')
        except Exception as e:
            logging.error(f'Error funding wallet {self.address}: {e}')
            raise

    async def update_balance(self, rpc_client: AsyncClient):
        """Updates the wallet's SOL balance"""
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            balance = await rpc_client.get_balance(Pubkey.from_string(self.address))
            self.balance = balance.value / 1_000_000_000
            logging.info(f'Updated balance for wallet {self.address}: {self.balance} SOL')
        except Exception as e:
            logging.error(f'Could not update balance for wallet {self.address}: {e}')
            raise

    async def import_keypair(self, private_key_str: str):
        """Imports a wallet from a private key"""
        try:
            decoded_key = b58decode(private_key_str)
            self.keypair = Keypair.from_bytes(decoded_key)
            self.address = str(self.keypair.pubkey())
            logging.info(f'Wallet imported with address {self.address}')
            self.is_initialized = True
        except Exception as e:
            logging.error(f'Could not import keypair: {e}')
            raise

    async def transfer_sol(self, rpc_url: str, helius_api_key: str, to_wallet_address: str):
        """Transfers SOL."""
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            if self.balance <= 0:
                logging.warning(f"Wallet {self.address} has no SOL to transfer")
                return
            recent_blockhash_str = transaction.get_recent_blockhash_sync(rpc_url)
            recent_blockhash = Hash.from_string(recent_blockhash_str)
            fee_buffer_lamports = 2_000_000
            transferable_lamports = int(self.balance * 1_000_000_000) - fee_buffer_lamports
            if transferable_lamports <= 0:
                logging.warning(
                    f"Wallet {self.address} has insufficient balance to transfer after reserving fee buffer.")
                return
            params = TransferParams(
                from_pubkey=self.keypair.pubkey(),
                to_pubkey=Pubkey.from_string(to_wallet_address),
                lamports=transferable_lamports,
            )
            transfer_instruction = transfer(params)
            message = Message.new_with_blockhash(
                [transfer_instruction], self.keypair.pubkey(), recent_blockhash
            )
            transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[self.keypair])
            transaction_obj.sign([self.keypair], recent_blockhash=recent_blockhash)

            signature = await transaction.send_helius_transaction(helius_api_key, transaction_obj)
            logging.info(
                f'Sent {transferable_lamports / 1_000_000_000} SOL from wallet {self.address} to {to_wallet_address}. txid: {signature}')
        except Exception as e:
            logging.error(f'Error sending transaction {e}')
            raise

    async def update_token_balances(self, rpc_client: AsyncClient, token_address: str):
        """Updates the wallet's token balance."""
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            balance = await transaction.get_token_balance(rpc_client.url, token_address, self.address)
            self.token_balances[token_address] = balance
            logging.info(
                f'Updated token balance {token_address} for wallet {self.address}: {self.token_balances[token_address]}')
        except Exception as e:
            logging.error(f'Could not update token balance for {token_address} {self.address} error: {e}')
            raise

    async def to_json(self) -> Dict:
        if not self.is_initialized:
            raise ValueError('Wallet is not initialized.')
        return {'address': self.address, 'name': self.name, 'bio': self.bio}

    async def reclaim_sol(self, rpc_url: str, helius_api_key: str, to_wallet_address: str):
        """Reclaims SOL back to the specified wallet."""
        logging.info(f"Reclaiming SOL back to wallet {to_wallet_address} from {self.address}")
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            if self.balance <= 0:
                logging.warning(f"Wallet {self.address} has no SOL to reclaim.")
                return
            recent_blockhash_str = transaction.get_recent_blockhash_sync(rpc_url)
            recent_blockhash = Hash.from_string(recent_blockhash_str)
            fee_buffer_lamports = 5_000_000
            transferable_lamports = int(self.balance * 1_000_000_000) - fee_buffer_lamports
            if transferable_lamports <= 0:
                logging.warning(f"Wallet {self.address} has insufficient balance to reclaim after fee buffer.")
                return
            params = TransferParams(
                from_pubkey=self.keypair.pubkey(),
                to_pubkey=Pubkey.from_string(to_wallet_address),
                lamports=transferable_lamports,
            )
            transfer_instruction = transfer(params)
            message = Message.new_with_blockhash(
                [transfer_instruction], self.keypair.pubkey(), recent_blockhash
            )
            transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[self.keypair])
            transaction_obj.sign([self.keypair], recent_blockhash=recent_blockhash)

            signature = await transaction.send_helius_transaction(helius_api_key, transaction_obj)
            logging.info(f"SOL reclaimed from wallet {self.address} to {to_wallet_address} via Helius, txid: {signature}")
        except Exception as e:
            logging.error(f"Error reclaiming SOL from wallet {self.address}: {e}")
            raise

    async def transfer_tokens(self, rpc_url: str, helius_api_key: str, to_wallet_address: str, token_address: str = None):
        """Transfers all tokens from wallet to dev wallet."""
        logging.info(f"Transferring tokens from {self.address} to {to_wallet_address}")
        try:
            if not self.is_initialized:
                raise ValueError('Wallet is not initialized.')
            if not token_address:
                logging.error("Token address missing for token transfer.")
                return
            recent_blockhash_str = transaction.get_recent_blockhash_sync(rpc_url)
            recent_blockhash = Hash.from_string(recent_blockhash_str)
            from spl.token.instructions import transfer, TransferParams
            from spl.token.constants import TOKEN_PROGRAM_ID
            from spl.associated_token_account import get_associated_token_address

            source_token_account = get_associated_token_address(self.keypair.pubkey(), Pubkey.from_string(token_address))
            dest_token_account = get_associated_token_address(Pubkey.from_string(to_wallet_address), Pubkey.from_string(token_address))
            balance = await transaction.get_token_balance(rpc_url, token_address, self.address)
            transfer_instruction = transfer(
                TransferParams(
                    program_id=TOKEN_PROGRAM_ID,
                    source=source_token_account,
                    dest=dest_token_account,
                    owner=self.keypair.pubkey(),
                    amount=int(balance),
                )
            )
            message = Message([transfer_instruction], recent_blockhash=recent_blockhash)
            transaction_obj = Transaction(message=message, recent_blockhash=recent_blockhash, from_keypairs=[self.keypair])
            transaction_obj.sign([self.keypair], recent_blockhash=recent_blockhash)

            signature = await transaction.send_helius_transaction(helius_api_key, transaction_obj)
            logging.info(f"Sent tokens from wallet {self.address} to dev wallet {to_wallet_address}")
        except Exception as e:
            logging.error(f"Error transferring tokens: {e}")
            raise

    async def wallet_warmup(self, launch_manager):
        """Buys/sells tokens for wallet warmup."""
        logging.info("Executing Wallet Warmup")
        try:
            rugcheck_url = "https://api.rugcheck.xyz/v1/stats/verified"
            response = requests.get(rugcheck_url)
            response.raise_for_status()
            rugcheck_data = response.json()
            pump_mints = [item['mint'] for item in rugcheck_data if item['mint'].endswith('pump')]
            if not pump_mints:
                logging.warning("No verified pump mints found.")
                return
            token_address = random.choice(pump_mints)
            try:
                data = {
                    "publicKey": str(self.keypair.pubkey()),
                    "action": "buy",
                    "mint": token_address,
                    "amount": 0.001,
                    "denominatedInSol": "true",
                    "slippage": self.default_slippage,
                    "priorityFee": self.default_priority_fee,
                    "pool": "pump"
                }
                buy_transaction_response = await launch_manager.pumpfun_api.create_local_transaction(data, Keypair(), self.keypair)
                tx_buy = VersionedTransaction(VersionedTransaction.from_bytes(buy_transaction_response['transaction'].encode('utf-8')).message, [self.keypair])
                tx_signature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx_buy)
                logging.info(f"Wallet {self.address} bought token {token_address} tx: {tx_signature}")
                await asyncio.sleep(10)

                data = {
                    "publicKey": str(self.keypair.pubkey()),
                    "action": "sell",
                    "mint": token_address,
                    "amount": await transaction.get_token_balance(launch_manager.rpc_url, token_address, self.address),
                    "denominatedInSol": "false",
                    "slippage": self.default_slippage,
                    "priorityFee": self.default_priority_fee,
                    "pool": "pump"
                }
                sell_transaction_response = await launch_manager.pumpfun_api.create_local_transaction(data, Keypair(), self.keypair)
                tx_sell = VersionedTransaction(VersionedTransaction.from_bytes(sell_transaction_response['transaction'].encode('utf-8')).message, [self.keypair])
                tx_signature = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx_sell)
                logging.info(f"Wallet {self.address} sold token {token_address} tx: {tx_signature}")
                logging.info(f"Wallet {self.address} warmed up with token {token_address} - BUY and SELL complete.")
            except Exception as e:
                logging.error(f"Error warming up wallet {self.address} with token {token_address}: {e}")
        except Exception as e:
            logging.error(f"Error in wallet_warmup: {e}")
        logging.info("Wallet Warmup Completed")


async def _create_sub_wallets(num_sub_wallets):
    """Creates subwallets."""
    try:
        sub_wallets = []
        for i in range(num_sub_wallets):
            wallet = Wallet()
            await wallet.create_keypair()
            sub_wallets.append(wallet)
            logging.info(f"Sub-wallet {i + 1} created, address: {wallet.address}")
        return sub_wallets
    except Exception as e:
        logging.error(f"Error creating sub-wallets: {e}")
        raise


async def generate_wallets(num_sub_wallets, output_folder, main_wallet):
    """Generates wallets."""
    try:
        await main_wallet.create_keypair()
        logging.info(f"Creating wallets, main wallet address: {main_wallet.address}")
        sub_wallets = await _create_sub_wallets(num_sub_wallets)
        await _save_wallets(output_folder, main_wallet, sub_wallets)
        return sub_wallets
    except Exception as e:
        logging.error(f"Error generating wallets: {e}")
        raise


async def _save_wallets(output_folder, main_wallet, sub_wallets):
    """Saves wallet info to file."""
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        filename = os.path.join(output_folder, "wallet_info.txt")
        with open(filename, 'w') as f:
            f.write("Main Wallet:\n")
            f.write(f"Address: {main_wallet.address}\n")
            f.write(f"Seed phrase: {main_wallet.seed_phrase}\n")
            f.write("\nSub Wallets:\n")
            for i, wallet in enumerate(sub_wallets):
                f.write(f"Wallet {i + 1}:\n")
                f.write(f"Address: {wallet.address}\n")
                f.write(f"Seed phrase: {wallet.seed_phrase}\n")
                if wallet.name:
                    f.write(f"Name: {wallet.name}\n")
                if wallet.bio:
                    f.write(f"Bio: {wallet.bio}\n")
                f.write("\n")
        logging.info(f"Wallet information saved to: {filename}")
    except Exception as e:
        logging.error(f"Error saving wallets: {e}")
        raise


class Token:
    def __init__(self, name: str, symbol: str, image_path: Optional[str] = None, description: Optional[str] = None, telegram: Optional[str] = None, twitter: Optional[str] = None, website: Optional[str] = None):
        self.name: str = name
        self.symbol: str = symbol
        self.image_path: Optional[str] = image_path
        self.description: Optional[str] = description
        self.telegram: Optional[str] = telegram
        self.twitter: Optional[str] = twitter
        self.website: Optional[str] = website
        self.metadata: Optional[Dict] = None
        self.mint_address: Optional[str] = None
        self.metadata_uri: Optional[str] = None

    def __str__(self) -> str:
        return f'Token Name: {self.name}, Symbol: {self.symbol} Address: {self.mint_address or "Not Created Yet"}'

    async def clone_metadata(self, existing_token):
        """Clones metadata from existing token."""
        try:
            self.metadata = existing_token.metadata
            logging.info(f'Metadata cloned from {existing_token.name}')
        except Exception as e:
            logging.error(f'Error cloning metadata: {e}')
            raise
