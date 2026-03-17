from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import asyncio
import threading
import logging
import configparser
import os
import json
import time
from launch_manager import LaunchManager
from wallet import Token, Wallet
from launch_actions import bundle_launch, clone_and_snipe, snipe_only, bundle_stagger_launch

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global LaunchManager instance
launch_manager = None
loop = asyncio.new_event_loop()

def run_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=run_async_loop, args=(loop,), daemon=True).start()

def run_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, loop).result()

def init_launch_manager():
    global launch_manager
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

        # Set additional params from config
        launch_manager.default_slippage = int(config.get('DEFAULT', 'DEFAULT_SLIPPAGE'))
        launch_manager.default_priority_fee = float(config.get('DEFAULT', 'DEFAULT_PRIORITY_FEE'))
        launch_manager.stagger_default_amount = float(config.get('DEFAULT', 'STAGGER_DEFAULT_AMOUNT'))
        launch_manager.stagger_default_slippage = int(config.get('DEFAULT', 'STAGGER_DEFAULT_SLIPPAGE'))
        launch_manager.stagger_default_priority_fee = float(config.get('DEFAULT', 'STAGGER_DEFAULT_PRIORITY_FEE'))

        run_async(launch_manager.init())
        run_async(launch_manager.create_sub_wallets()) # Load existing or create new

        logger.info("LaunchManager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize LaunchManager: {e}")

init_launch_manager()

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    config = configparser.ConfigParser()
    config.read('config.ini')
    if request.method == 'GET':
        return jsonify({section: dict(config[section]) for section in config.sections()})
    else:
        new_config = request.json
        for section, options in new_config.items():
            if section not in config:
                config.add_section(section)
            for key, value in options.items():
                config.set(section, key, str(value))
        with open('config.ini', 'w') as f:
            config.write(f)
        init_launch_manager() # Re-init
        return jsonify({"status": "success"})

@app.route('/api/wallets', methods=['GET'])
def get_wallets():
    wallets = []
    # Main wallet
    wallets.append({
        "address": launch_manager.main_wallet.address,
        "type": "main",
        "balance": launch_manager.main_wallet.balance
    })
    # Sub wallets
    for i, w in enumerate(launch_manager.sub_wallets):
        wallets.append({
            "address": w.address,
            "type": "sub",
            "index": i + 1,
            "balance": w.balance,
            "token_balances": w.token_balances
        })
    return jsonify(wallets)

@app.route('/api/wallets/generate', methods=['POST'])
def generate_new_wallets():
    data = request.json
    num = int(data.get('num', 20))
    try:
        launch_manager.num_sub_wallets = num
        run_async(launch_manager.generate_wallets())
        return jsonify({"status": "success", "count": len(launch_manager.sub_wallets)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/wallets/export', methods=['GET'])
def export_wallets():
    try:
        export_data = {
            "main_wallet": {
                "address": launch_manager.main_wallet.address,
                "seed": launch_manager.main_wallet.seed_phrase
            },
            "sub_wallets": [
                {
                    "address": w.address,
                    "seed": w.seed_phrase
                } for w in launch_manager.sub_wallets
            ]
        }
        return jsonify(export_data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/wallets/balances', methods=['POST'])
def update_balances():
    try:
        run_async(launch_manager.main_wallet.update_balance(launch_manager.rpc_client))
        for w in launch_manager.sub_wallets:
            run_async(w.update_balance(launch_manager.rpc_client))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sell/delayed', methods=['POST'])
def sell_delayed():
    data = request.json
    delay = float(data.get('delay', 1))
    try:
        run_async(launch_manager.delayed_sell(delay))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/launch/sniper-farmer', methods=['POST'])
def launch_sniper_farmer():
    data = request.json
    # This is complex because it involves multiple tokens.
    # For now, I'll implement a simplified version or just expose the existing one if possible.
    # The existing sniper_farmer_launch expects a lot of params.
    return jsonify({"status": "error", "message": "Not fully implemented in API yet"}), 501

@app.route('/api/wallets/fund', methods=['POST'])
def fund_wallets():
    data = request.json
    amounts = data.get('amounts', [])
    try:
        run_async(launch_manager.fund_wallets(amounts))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/wallets/transfer-sol', methods=['POST'])
def transfer_sol():
    data = request.json
    from_index = data.get('from_index') # 0 for main, 1+ for sub
    to_address = data.get('to_address')
    amount = float(data.get('amount'))

    if from_index == 0:
        from_wallet = launch_manager.main_wallet
    else:
        from_wallet = launch_manager.sub_wallets[from_index - 1]

    try:
        run_async(launch_manager.transfer_sol(from_wallet, to_address, amount))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/wallets/reclaim', methods=['POST'])
def reclaim_sol():
    try:
        run_async(launch_manager.reclaim_sol())
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/launch/bundle', methods=['POST'])
def launch_bundle():
    if 'image' in request.files:
        image_file = request.files['image']
        image_path = os.path.join('images', image_file.filename)
        image_file.save(image_path)
    else:
        image_path = request.form.get('image_path')

    token = Token(
        name=request.form.get('name'),
        symbol=request.form.get('symbol'),
        description=request.form.get('description', ''),
        telegram=request.form.get('telegram', ''),
        twitter=request.form.get('twitter', ''),
        website=request.form.get('website', ''),
        image_path=image_path
    )
    num_wallets = int(request.form.get('num_wallets', 3))
    amount = float(request.form.get('amount', 0.01))
    amounts = [amount] * num_wallets
    use_jito = request.form.get('use_jito', 'true').lower() == 'true'
    dev_buy_amount = float(request.form.get('dev_buy_amount', 0.001))

    try:
        # Run in background to avoid timeout
        def run_launch():
            run_async(bundle_launch(launch_manager, token, num_wallets, amounts, use_jito, dev_buy_amount))
            # Save to history
            h = load_history()
            h['tokens'].append({
                "name": token.name,
                "symbol": token.symbol,
                "address": token.mint_address,
                "type": "bundle",
                "timestamp": time.time()
            })
            h['performance']['launches'] += 1
            save_history(h)

        threading.Thread(target=run_launch).start()
        return jsonify({"status": "initiated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/launch/clone-snipe', methods=['POST'])
def launch_clone_snipe():
    data = request.json
    token_data = data.get('token')
    token = Token(name=token_data.get('name'), symbol=token_data.get('symbol'))
    num_wallets = data.get('num_wallets')
    amounts = data.get('amounts')
    use_jito = data.get('use_jito', True)
    existing_address = data.get('existing_address')
    dev_buy_amount = data.get('dev_buy_amount', 0.001)

    try:
        threading.Thread(target=lambda: run_async(clone_and_snipe(launch_manager, token, num_wallets, amounts, use_jito, existing_address, dev_buy_amount))).start()
        return jsonify({"status": "initiated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sell/dump-all', methods=['POST'])
def sell_dump_all():
    data = request.json
    percentage = data.get('percentage', 100)
    try:
        run_async(launch_manager.dump_all(percentage))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sell/single', methods=['POST'])
def sell_single():
    data = request.json
    address = data.get('address')
    percentage = data.get('percentage', 100)
    try:
        run_async(launch_manager.single_wallet_sell(address, percentage))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/sell/dev-dump', methods=['POST'])
def sell_dev_dump():
    try:
        run_async(launch_manager.dev_dump_all())
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "initialized": launch_manager is not None,
        "main_wallet": launch_manager.main_wallet.address if launch_manager else None,
        "sub_wallets_count": len(launch_manager.sub_wallets) if launch_manager else 0
    })

# Tracking for Dashboard
HISTORY_FILE = 'history.json'

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {"tokens": [], "performance": {"total_profit": 0, "launches": 0}}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(load_history())

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists("frontend/dist/" + path):
        return send_from_directory('frontend/dist', path)
    else:
        return send_from_directory('frontend/dist', 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
