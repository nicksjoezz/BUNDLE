# Main.py
import asyncio
import os
from ui import main_menu
from launch_manager import LaunchManager
import configparser
import logging
from wallet import Wallet  # Import if you need to use the Wallet class directly here
from api import PumpFunAPI #Import the API


# --- Logging Setup (Correct and Efficient) ---
config = configparser.ConfigParser()
config.read('config.ini')
log_file = config.get('DEFAULT', 'LOG_FILE', fallback='infinityato.log')
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_path = os.path.join(log_dir, log_file)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,  # Set the desired logging level
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w'  # Overwrite log file each time
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)  # Warnings and above go to console
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)  # Add handler to root logger


async def main():
    config = configparser.ConfigParser()
    config.read('config.ini')

    try:
        RPC_URL = config.get('DEFAULT', 'RPC_URL')
        HELIUS_API_KEY = config.get('DEFAULT', 'HELIUS_API_KEY')
        PUMPFUN_API_URL = config.get('DEFAULT', 'PUMPFUN_API_URL')
        MAIN_WALLET_SEED = config.get('DEFAULT', 'MAIN_WALLET_SEED')
        NUM_SUB_WALLETS = int(config.get('DEFAULT', 'NUM_SUB_WALLETS'))
        WEBSOCKET_URL = config.get('DEFAULT', 'WEBSOCKET_URL')
        SNIPER_FARMER_TIME_TO_SELL_MINUTES = int(config.get('DEFAULT', 'SNIPER_FARMER_TIME_TO_SELL_MINUTES'))
        OUTPUT_FOLDER = config.get('DEFAULT', 'OUTPUT_FOLDER')
        STAGGER_DEFAULT_AMOUNT = float(config.get('DEFAULT', 'STAGGER_DEFAULT_AMOUNT'))
        STAGGER_DEFAULT_SLIPPAGE = int(config.get('DEFAULT', 'STAGGER_DEFAULT_SLIPPAGE'))
        STAGGER_DEFAULT_PRIORITY_FEE = float(config.get('DEFAULT', 'STAGGER_DEFAULT_PRIORITY_FEE'))
        # Removed STAGGER_DEFAULT_POOL
        DEFAULT_SLIPPAGE = int(config.get('DEFAULT', 'DEFAULT_SLIPPAGE'))
        DEFAULT_PRIORITY_FEE = float(config.get('DEFAULT', 'DEFAULT_PRIORITY_FEE'))
        # Removed DEFAULT_POOL


    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f"Error loading configuration: {e}")
        print(f"Error loading configuration. Check 'config.ini'.  Error: {e}")
        return  # Exit if config loading fails

    if not MAIN_WALLET_SEED:
        logging.error("MAIN_WALLET_SEED not set in config.ini.")
        print("MAIN_WALLET_SEED not set in config.ini. Please provide your main wallet's seed phrase.")
        return

    launch_manager = LaunchManager(
        rpc_url=RPC_URL,
        helius_api_key=HELIUS_API_KEY,
        pumpfun_api_url=PUMPFUN_API_URL,
        main_wallet_seed=MAIN_WALLET_SEED,
        num_sub_wallets=NUM_SUB_WALLETS,
        websocket_url=WEBSOCKET_URL,
        sniper_farmer_time_to_sell_minutes=SNIPER_FARMER_TIME_TO_SELL_MINUTES,
        output_folder=OUTPUT_FOLDER
    )
    # Set the parameters from the config
    launch_manager.default_slippage = DEFAULT_SLIPPAGE
    launch_manager.default_priority_fee = DEFAULT_PRIORITY_FEE
    # Removed default pool
    launch_manager.stagger_default_amount = STAGGER_DEFAULT_AMOUNT
    launch_manager.stagger_default_slippage = STAGGER_DEFAULT_SLIPPAGE
    launch_manager.stagger_default_priority_fee = STAGGER_DEFAULT_PRIORITY_FEE
    # Removed stagger default pool

    try:
        await launch_manager.init()  # Initialize the LaunchManager
        # Sub-wallets are now generated on demand via the UI
        launch_manager.pumpfun_api = PumpFunAPI(PUMPFUN_API_URL, RPC_URL)
        await main_menu(launch_manager)  # Start the main menu
    except Exception as e:
        logging.exception("An unhandled exception occurred:")  # Log the full traceback
        print(f"An unexpected error occurred: {e}")
    finally:
        if launch_manager:
            await launch_manager.close() # Close connections.
        logging.info("Application exited.")

if __name__ == "__main__":
    asyncio.run(main())