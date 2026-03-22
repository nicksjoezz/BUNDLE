# launch_actions.py
import logging
import configparser
from typing import Dict, List, Optional, Tuple, Any
from solders.keypair import Keypair
from wallet import Token, Wallet
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solders.message import Message
from solders.transaction import Transaction, VersionedTransaction
import asyncio
import httpx
import random
import base58
import transaction
import json
import requests
from solders.commitment_config import CommitmentLevel
from solders.rpc.config import RpcSendTransactionConfig
from solders.rpc.requests import SendVersionedTransaction
import os
import websocket
import ssl
import time

config = configparser.ConfigParser()
config.read('config.ini')

IPFS_UPLOAD_URL = "https://pump.fun/api/ipfs"
PUMP_FUN_PROGRAM_ID = Pubkey.from_string(config.get('DEFAULT', 'PUMP_FUN_PROGRAM_ID'))

def get_associated_bonding_curve_address(mint: Pubkey, program_id: Pubkey) -> Tuple[Pubkey, int]:
    return Pubkey.find_program_address([b"bonding-curve", bytes(mint)], program_id)

async def get_sol_price_usd() -> float:
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        response.raise_for_status()
        data = response.json()
        return float(data.get("solana", {}).get("usd", 0))
    except Exception as e:
        logging.error(f"Error fetching SOL price: {e}")
        return 0.0

async def create_and_sign_local_tx(tx_data: Dict, signer_keypair: Keypair, mint_keypair: Optional[Keypair] = None) -> VersionedTransaction:
    url = "https://pumpportal.fun/api/trade-local"
    response = requests.post(url, json=tx_data, headers={"Content-Type": "application/json"})
    response.raise_for_status()

    signers = [signer_keypair]
    if mint_keypair:
        signers.append(mint_keypair)

    tx = VersionedTransaction.from_bytes(response.content)
    tx.sign(signers)
    return tx

async def clone_and_snipe(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool, existing_token_address: str, dev_buy_amount: float):
    logging.info(f"Executing Clone + Snipe for {token.name} from {existing_token_address}")
    try:
        async with httpx.AsyncClient() as client:
            helius_url = f"https://mainnet.helius-rpc.com/?api-key={launch_manager.helius_api_key}"
            payload = {"jsonrpc": "2.0", "id": "test", "method": "getAsset", "params": {"id": existing_token_address}}
            response = await client.post(helius_url, json=payload)
            response.raise_for_status()
            asset_data = response.json()
            asset_result = asset_data["result"]

            token_name = asset_result["content"]["metadata"].get("name", "Cloned")
            token_symbol = asset_result["content"]["metadata"].get("symbol", "CLONE")
            description = asset_result["content"]["metadata"].get("description", "")
            external_url = asset_result["content"].get("links", {}).get("website", "")
            image = asset_result["content"].get("links", {}).get("image", "")

            token_metadata_for_ipfs = {
                'name': token_name, 'symbol': token_symbol, 'description': description,
                'website': external_url, 'logo': image, 'showName': 'true'
            }

            res = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs)
            res.raise_for_status()
            metadata_uri = res.json().get('metadataUri', '')
            token.metadata_uri = metadata_uri

            mint_keypair = Keypair()
            create_tx_data = {
               'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
               'action': 'create',
               'tokenMetadata': {'name': token_name, 'symbol': token_symbol, 'uri': metadata_uri},
               'mint': str(mint_keypair.pubkey()),
               'denominatedInSol': 'true',
               'amount': dev_buy_amount,
               'slippage': launch_manager.default_slippage,
               'priorityFee': launch_manager.default_priority_fee,
               'pool': launch_manager.default_pool
            }

            tx = await create_and_sign_local_tx(create_tx_data, launch_manager.main_wallet.keypair, mint_keypair)
            tx_sig = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
            token.mint_address = str(mint_keypair.pubkey())
            logging.info(f"Token created: {token.mint_address} sig: {tx_sig}")

            sub_buy_txs = []
            signer_keypairs = []
            for i in range(min(num_wallets, len(launch_manager.sub_wallets))):
               wallet = launch_manager.sub_wallets[i]
               sub_buy_txs.append({
                    "publicKey": str(wallet.keypair.pubkey()),
                    "action": "buy",
                    "mint": token.mint_address,
                    "denominatedInSol": "true",
                    "amount": amounts[i],
                    "slippage": launch_manager.default_slippage,
                    'priorityFee': launch_manager.default_priority_fee,
                    'pool': "auto"
               })
               signer_keypairs.append(wallet.keypair)

            if use_jito:
                await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
            else:
                for sub_tx, signer in zip(sub_buy_txs, signer_keypairs):
                    tx = await create_and_sign_local_tx(sub_tx, signer)
                    await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
    except Exception as e:
        logging.error(f"Error in clone_and_snipe: {e}")
        raise

async def bundle_stagger_launch(launch_manager, token: Token, num_wallets: int, amounts: List[float], additional_params: Dict, clone_existing: bool = False, clone_address: str = None, dev_buy_amount: float = 0.001):
    logging.info(f"Executing bundle stagger launch for {token.name}")
    try:
        delay_interval = additional_params.get('delay', 1.0)
        mint_keypair = Keypair()

        token_metadata_for_ipfs = {
            'name': token.name, 'symbol': token.symbol, 'description': token.description,
            'telegram': token.telegram, 'twitter': token.twitter, 'website': token.website, 'showName': 'true'
        }
        files = {}
        if token.image_path and os.path.exists(token.image_path):
            f = open(token.image_path, 'rb')
            files['file'] = (os.path.basename(token.image_path), f, 'image/png')
        else:
            f = None

        res = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files)
        if f: f.close()
        res.raise_for_status()
        metadata_uri = res.json().get('metadataUri', '')
        token.metadata_uri = metadata_uri

        create_tx_data = {
            'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': {'name': token.name, 'symbol': token.symbol, 'uri': metadata_uri},
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': dev_buy_amount,
            'slippage': launch_manager.default_slippage,
            'priorityFee': launch_manager.default_priority_fee,
            'pool': launch_manager.default_pool
        }

        tx = await create_and_sign_local_tx(create_tx_data, launch_manager.main_wallet.keypair, mint_keypair)
        await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
        token.mint_address = str(mint_keypair.pubkey())

        for i in range(min(num_wallets, len(launch_manager.sub_wallets))):
            wallet = launch_manager.sub_wallets[i]
            buy_tx_data = {
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": clone_address if clone_existing else token.mint_address,
                "denominatedInSol": "true",
                "amount": amounts[i],
                "slippage": launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': "auto"
            }
            tx = await create_and_sign_local_tx(buy_tx_data, wallet.keypair)
            await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
            await asyncio.sleep(random.uniform(0, delay_interval))
    except Exception as e:
        logging.error(f"Error in bundle_stagger_launch: {e}")
        raise

async def bundle_launch(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool, dev_buy_amount: float):
    logging.info(f"Executing bundle launch for {token.name}")
    try:
        mint_keypair = Keypair()
        token_metadata_for_ipfs = {
            'name': token.name, 'symbol': token.symbol, 'description': token.description,
            'telegram': token.telegram, 'twitter': token.twitter, 'website': token.website, 'showName': 'true'
        }
        files = {}
        if token.image_path and os.path.exists(token.image_path):
            f = open(token.image_path, 'rb')
            files['file'] = (os.path.basename(token.image_path), f, 'image/png')
        else:
            f = None

        res = requests.post(IPFS_UPLOAD_URL, data=token_metadata_for_ipfs, files=files)
        if f: f.close()
        res.raise_for_status()
        metadata_uri = res.json().get('metadataUri', '')
        token.metadata_uri = metadata_uri

        create_tx_data = {
           'publicKey': str(launch_manager.main_wallet.keypair.pubkey()),
           'action': 'create',
           'tokenMetadata': {'name': token.name, 'symbol': token.symbol, 'uri': metadata_uri},
           'mint': str(mint_keypair.pubkey()),
           'denominatedInSol': 'true',
           'amount': dev_buy_amount,
           'slippage': launch_manager.default_slippage,
           'priorityFee': launch_manager.default_priority_fee,
           'pool': launch_manager.default_pool
        }

        tx = await create_and_sign_local_tx(create_tx_data, launch_manager.main_wallet.keypair, mint_keypair)
        await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
        token.mint_address = str(mint_keypair.pubkey())

        sub_buy_txs = []
        signer_keypairs = []
        for i in range(min(num_wallets, len(launch_manager.sub_wallets))):
            wallet = launch_manager.sub_wallets[i]
            sub_buy_txs.append({
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": token.mint_address,
                "denominatedInSol": "true",
                "amount": amounts[i],
                "slippage": launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': "auto"
            })
            signer_keypairs.append(wallet.keypair)

        if use_jito:
            await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
        else:
             for sub_tx, signer in zip(sub_buy_txs, signer_keypairs):
                tx = await create_and_sign_local_tx(sub_tx, signer)
                await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
    except Exception as e:
        logging.error(f"Error in bundle_launch: {e}")
        raise

async def snipe_only(launch_manager, token: Token, num_wallets: int, amounts: List[float], use_jito: bool):
    logging.info(f"Executing snipe only for {token.mint_address}")
    try:
        sub_buy_txs = []
        signer_keypairs = []
        for i in range(min(num_wallets, len(launch_manager.sub_wallets))):
            wallet = launch_manager.sub_wallets[i]
            sub_buy_txs.append({
                "publicKey": str(wallet.keypair.pubkey()),
                "action": "buy",
                "mint": token.mint_address,
                "denominatedInSol": "true",
                "amount": amounts[i],
                "slippage": launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
                'pool': "auto"
            })
            signer_keypairs.append(wallet.keypair)

        if use_jito:
            await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, sub_buy_txs, signer_keypairs, launch_manager.rpc_client)
        else:
            for sub_tx, signer in zip(sub_buy_txs, signer_keypairs):
                tx = await create_and_sign_local_tx(sub_tx, signer)
                await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
    except Exception as e:
        logging.error(f"Error in snipe_only: {e}")
        raise

async def bundle_sell_all(launch_manager, percentage_to_sell: float):
    logging.info(f"Dumping all with {percentage_to_sell}%")
    try:
        await launch_manager.main_wallet.update_balance(launch_manager.rpc_client)
        for wallet in launch_manager.sub_wallets:
            await wallet.update_balance(launch_manager.rpc_client)

        transactions = []
        signer_keypairs = []
        for wallet in [launch_manager.main_wallet] + launch_manager.sub_wallets:
            for mint, balance in wallet.token_balances.items():
                if balance > 0:
                    transactions.append({
                        "publicKey": str(wallet.keypair.pubkey()),
                        "action": "sell",
                        "mint": mint,
                        "amount": balance * (percentage_to_sell / 100),
                        "denominatedInSol": "false",
                        "slippage": launch_manager.default_slippage,
                        "priorityFee": launch_manager.default_priority_fee,
                    })
                    signer_keypairs.append(wallet.keypair)

        if transactions:
            await transaction.submit_jito_bundle(launch_manager.pumpfun_api_url, launch_manager.helius_api_key, transactions, signer_keypairs, launch_manager.rpc_client)
    except Exception as e:
        logging.error(f"Error in bundle_sell_all: {e}")

_sell_triggered = False

def _on_message(ws, message):
    global _sell_triggered
    try:
        data = json.loads(message)
        if data.get("method") == "accountNotification":
            _sell_triggered = True
            ws.close()
    except Exception: pass

def _on_error(ws, error): logging.error(f"WS Error: {error}")
def _on_close(ws, c, m): pass
def _on_open(ws):
    ws.send(json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "accountSubscribe",
        "params": [str(_bonding_curve_address_for_ws), {"encoding": "jsonParsed", "commitment": "confirmed"}]
    }))

async def _perform_sell_action(launch_manager, token_config: Token, creator_wallet: Wallet, helius_api_key: str):
    try:
        creator_token_balance = await transaction.get_token_balance(launch_manager.rpc_url, token_config.mint_address, str(creator_wallet.keypair.pubkey()), helius_api_key)
        if creator_token_balance > 0:
            tx_data = {
                "publicKey": str(creator_wallet.keypair.pubkey()),
                "action": "sell",
                "mint": token_config.mint_address,
                "amount": creator_token_balance,
                "denominatedInSol": "false",
                "slippage": launch_manager.default_slippage,
                "priorityFee": launch_manager.default_priority_fee,
            }
            tx = await create_and_sign_local_tx(tx_data, creator_wallet.keypair)
            await transaction.send_helius_transaction(helius_api_key, tx)
    except Exception as e:
        logging.error(f"Sell action failed: {e}")

async def sniper_farmer_launch(launch_manager, token_configs: List[Token], liquidity_threshold_usds: List[float], dev_buy_amounts: List[float], use_jito: bool):
    logging.info(f"Starting Sniper Farmer for {len(token_configs)} tokens")
    global _bonding_curve_address_for_ws, _sell_triggered
    try:
        for i, token_config in enumerate(token_configs):
            if i >= len(launch_manager.sub_wallets): break
            wallet = launch_manager.sub_wallets[i]
            mint_keypair = Keypair()

            token_metadata = {'name': token_config.name, 'symbol': token_config.symbol, 'description': token_config.description}
            res = requests.post(IPFS_UPLOAD_URL, data=token_metadata)
            res.raise_for_status()
            metadata_uri = res.json().get('metadataUri', '')

            create_tx_data = {
                'publicKey': str(wallet.keypair.pubkey()),
                'action': 'create',
                'tokenMetadata': {'name': token_config.name, 'symbol': token_config.symbol, 'uri': metadata_uri},
                'mint': str(mint_keypair.pubkey()),
                'denominatedInSol': 'true',
                'amount': dev_buy_amounts[i],
                'slippage': launch_manager.default_slippage,
                'priorityFee': launch_manager.default_priority_fee,
            }

            tx = await create_and_sign_local_tx(create_tx_data, wallet.keypair, mint_keypair)
            await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
            token_config.mint_address = str(mint_keypair.pubkey())

            _bonding_curve_address_for_ws, _ = get_associated_bonding_curve_address(mint_keypair.pubkey(), PUMP_FUN_PROGRAM_ID)
            _sell_triggered = False

            ws_url = config.get('DEFAULT', 'HELIUS_WEBSOCKET_URL')
            ws = websocket.WebSocketApp(ws_url, on_open=_on_open, on_message=_on_message, on_error=_on_error, on_close=_on_close)

            import threading
            wst = threading.Thread(target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}})
            wst.daemon = True
            wst.start()

            start_t = time.time()
            limit = int(config.get('DEFAULT', 'SNIPER_FARMER_TIME_TO_SELL_MINUTES')) * 60
            while not _sell_triggered and (time.time() - start_t) < limit:
                await asyncio.sleep(1)

            if ws.sock and ws.sock.connected: ws.close()
            await _perform_sell_action(launch_manager, token_config, wallet, launch_manager.helius_api_key)

        await launch_manager.reclaim_sol()
    except Exception as e:
        logging.error(f"Sniper Farmer failed: {e}")
        raise

async def volume_bot_loop(launch_manager, mint_address: str, duration_minutes: int, min_buy: float, max_buy: float, delay_range: Tuple[float, float], stop_event: asyncio.Event):
    """Generates trading volume by rotating buys and sells across sub-wallets."""
    logging.info(f"Volume bot started for {mint_address} for {duration_minutes} minutes")
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)

    while time.time() < end_time and not stop_event.is_set():
        try:
            # Pick a random sub-wallet
            wallet = random.choice(launch_manager.sub_wallets)
            await wallet.update_balance(launch_manager.rpc_client)

            # Check if we should buy or sell
            token_balance = wallet.token_balances.get(mint_address, 0)

            if token_balance > 0 and random.random() > 0.4: # 60% chance to sell if holding
                # Sell a random portion
                sell_percent = random.uniform(0.5, 1.0)
                amount_to_sell = token_balance * sell_percent
                tx_data = {
                    "publicKey": str(wallet.keypair.pubkey()),
                    "action": "sell",
                    "mint": mint_address,
                    "amount": amount_to_sell,
                    "denominatedInSol": "false",
                    "slippage": launch_manager.default_slippage,
                    "priorityFee": launch_manager.default_priority_fee,
                }
                tx = await create_and_sign_local_tx(tx_data, wallet.keypair)
                sig = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
                logging.info(f"Volume Bot [SELL]: {sig}")
            else:
                # Buy a random amount
                buy_amount = random.uniform(min_buy, max_buy)
                if wallet.balance > (buy_amount + 0.01):
                    tx_data = {
                        "publicKey": str(wallet.keypair.pubkey()),
                        "action": "buy",
                        "mint": mint_address,
                        "amount": buy_amount,
                        "denominatedInSol": "true",
                        "slippage": launch_manager.default_slippage,
                        "priorityFee": launch_manager.default_priority_fee,
                    }
                    tx = await create_and_sign_local_tx(tx_data, wallet.keypair)
                    sig = await transaction.send_helius_transaction(launch_manager.helius_api_key, tx)
                    logging.info(f"Volume Bot [BUY]: {sig}")

            # Sleep for random interval
            await asyncio.sleep(random.uniform(*delay_range))

        except Exception as e:
            logging.error(f"Volume bot error: {e}")
            await asyncio.sleep(5)

    logging.info(f"Volume bot finished for {mint_address}")
