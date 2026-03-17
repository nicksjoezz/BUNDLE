# ui.py
import asyncio
import os
from launch_manager import LaunchManager  # Changed import
from launch_actions import *  # import launch actions here
# sniper_farmer_launch is implicitly imported with '*'
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
import logging
from wallet import Wallet, Token
from solders.pubkey import Pubkey
from base58 import b58encode
import threading # Added for threading
import json # Added for JSON file output
import time # Added for sleep

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

console = Console()


async def main_menu(launch_manager):
    menu_options = [
        ("Generate Wallets", 1),
        ("Wallet UI", 2),
        ("Launch UI", 3),
        ("Sniper Farmer", 4),
        ("Sell", 5),
        ("Vanity Address", 6),
        ("Exit", 7),
    ]

    while True:
        console.clear()
        console.print("[green]InfinityATO[/green]")
        console.print("Options:")

        table = Table(show_header=False, box=None)  # Create a table without headers and borders
        table.add_column(justify="left")

        for i, (option_name, _) in enumerate(menu_options):
            table.add_row(f"[bold]{i + 1}.[/bold] {option_name}")

        console.print(table)

        try:
            choice = Prompt.ask("Choose an option", default="5")
            try:
                choice = int(choice)
            except ValueError:
                logging.error("Invalid input, please enter a number")
                console.print("[red]Invalid input, please enter a number[/red]")
                await asyncio.sleep(1)
                continue
            if 1 <= choice <= len(menu_options):
                selected_option = menu_options[choice - 1]
                if selected_option[1] == 1:
                    console.print("Generating wallets...")
                    try:
                        wallet_amount = int(Prompt.ask("Enter the amount to make (max 20)", default="20"))
                        logging.info(f"User entered wallet amount: {wallet_amount}")
                        launch_manager.num_sub_wallets = wallet_amount
                        await launch_manager.generate_wallets()
                        console.print("[green]Generated Wallets Successfully![/green]")  # Success message
                        Prompt.ask("Press Enter to return to the main menu")  # Pause
                    except Exception as e:
                        logging.error(f"Invalid input: {e}")
                        console.print(f"[red]Invalid input: {e}[/red]")
                        await asyncio.sleep(2)

                elif selected_option[1] == 2:
                    await wallet_ui(launch_manager)

                elif selected_option[1] == 3:
                    await launch_ui(launch_manager)
                elif selected_option[1] == 4:
                    await sniper_farmer_ui(launch_manager) # Call the new UI function
                elif selected_option[1] == 5:
                    await sell_ui(launch_manager)
                elif selected_option[1] == 6:
                    await vanity_address_ui(launch_manager)
                elif selected_option[1] == 7:
                    break
            else:
                logging.warning(f"Invalid menu option chosen: {choice}")
                console.print("[red]Invalid Option[/red]")
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            console.print(f"[red]An unexpected error occurred: {e}[/red]")
            await asyncio.sleep(2)


async def wallet_ui(launch_manager):
    wallet_options = [
        ("Fund Wallets", 'f'),
        ("Balance", 'b'),
        ("Transfer Tokens", 'tt'),
        ("Transfer SOL", 'ts'),
        ("Refund SOL", 'r'),
        ("Wallet warmup mode", 'w'),
        ("Burn Dev Supply", 'bu'),
        ("Exit to Main Menu", 'e'),
    ]
    while True:
        console.clear()
        console.print("Wallet Management")
        table = Table(show_header=False, box=None)
        table.add_column(justify="left")
        for i, (option_name, _) in enumerate(wallet_options):
            table.add_row(f"[bold]{i + 1}.[/bold] {option_name} ([italic]{_}[/italic])")

        console.print(table)

        try:
            choice = Prompt.ask("Choose an option", choices=[_[1] for _ in wallet_options] + ['e'], default='e')
            if choice == 'f':
                await fund_wallets_ui(launch_manager)
                return
            elif choice == 'b':
                await check_balances_ui(launch_manager)
            elif choice == 'tt':
                await transfer_tokens_ui(launch_manager)
            elif choice == 'ts':
                await transfer_sol_ui(launch_manager)
            elif choice == 'r':
                await refund_sol_ui(launch_manager)
            elif choice == 'w':
                await wallet_warmup_ui(launch_manager)
            elif choice == 'bu':
                await burn_dev_supply_ui(launch_manager)
            elif choice == 'e':
                break
            else:
                logging.warning(f"Invalid wallet option chosen: {choice}")
                console.print("[red]Invalid option[/red]")
                await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            console.print(f"[red]An unexpected error occurred: {e}[/red]")
            await asyncio.sleep(2)


async def fund_wallets_ui(launch_manager):
    console.clear()
    try:
        use_unique = Prompt.ask("Do you wish to send unique amounts to each wallet? (y/n)", choices=["y", "n"],
                                default="n")

        amounts = []
        if use_unique == 'y':
            for i, wallet in enumerate(launch_manager.sub_wallets):
                try:
                    amount = float(Prompt.ask(f"Enter buy amount (SOL) for Wallet {i + 1}", default="0.01"))
                    amounts.append(amount)  # Storing amount for each wallet
                    logging.info(f"User entered amount {amount} for wallet {i + 1}")
                except ValueError:
                    logging.error("Invalid input for amount")
                    console.print("[red]Invalid input[/red]")
                    await asyncio.sleep(1)
                    return  # Exit funding
        else:
            amount = float(Prompt.ask("Enter amount (SOL) to fund each wallet", default="0.01"))
            amounts = [amount] * len(launch_manager.sub_wallets)

        await launch_manager.fund_wallets(amounts)
        console.print("[green]Wallets funded successfully![/green]")
        await asyncio.sleep(1)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)

async def transfer_tokens_ui(launch_manager):
    console.clear()
    try:
        wallet_index = int(Prompt.ask(f"Enter the wallet number (1-{len(launch_manager.sub_wallets)}) to transfer from", default="1")) - 1
        if not 0 <= wallet_index < len(launch_manager.sub_wallets):
            console.print("[red]Invalid wallet number[/red]")
            await asyncio.sleep(1)
            return

        to_address = Prompt.ask("Enter the recipient address", default="")
        token_address = Prompt.ask("Enter the token address to transfer", default="")
        from_wallet = launch_manager.sub_wallets[wallet_index]
        # Get the wallet
        await launch_manager.transfer_tokens(from_wallet, to_address, token_address)
        console.print("[green]Transfer tokens to other wallet successfully![/green]")
        await asyncio.sleep(1)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)


async def check_balances_ui(launch_manager):
    console.clear()
    console.print("Fetching balances...")
    total_balance = 0
    await asyncio.sleep(2) # ADDED DELAY at the start
    try:
        for i, wallet in enumerate(launch_manager.sub_wallets):
            await wallet.update_balance(launch_manager.rpc_client)
            total_balance += wallet.balance
            console.print(f"Wallet {i+1}: {wallet.balance:.10f} SOL")  # CHANGED HERE
            console.print("Token Balances:")
            for token_address, balance in wallet.token_balances.items():
                console.print(f"  {token_address}: {balance:.4f}")

        await launch_manager.main_wallet.update_balance(launch_manager.rpc_client)
        console.print(f"Dev Wallet: {launch_manager.main_wallet.balance:.10f} SOL") # Keep this
        console.print(f"Total Balance: {total_balance + launch_manager.main_wallet.balance:.4f} SOL")
        console.print("BALANCES MAY TAKE A FEW SECONDS TO LOAD, RERUN IF THEY DO NOT SHOW UP OR CHECK JITO TXS")
        Prompt.ask("Press Enter to return to the Wallet menu") # Pause
        await asyncio.sleep(2)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)


async def refund_sol_ui(launch_manager):
    try:
        await launch_manager.reclaim_sol()
        console.print("[green]SOL refunded to main wallet successfully![/green]")
        await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)

async def transfer_sol_ui(launch_manager):
    console.clear()
    try:
        num_wallets = len(launch_manager.sub_wallets)
        from_wallet_index_str = Prompt.ask(f"Enter the index of the wallet to transfer SOL from (0 for main wallet, 1-{num_wallets} for sub-wallets)", default="0")
        from_wallet_index = int(from_wallet_index_str)

        if from_wallet_index == 0:
            from_wallet = launch_manager.main_wallet
        elif 1 <= from_wallet_index <= num_wallets:
            from_wallet = launch_manager.sub_wallets[from_wallet_index - 1] # Adjust to 0-based index
        else:
            console.print("[red]Invalid wallet index[/red]")
            await asyncio.sleep(1)
            return

        to_address = Prompt.ask("Enter the recipient address", default="")
        amount = float(Prompt.ask("Enter the amount of SOL to transfer", default="0.01"))


        await launch_manager.transfer_sol(from_wallet, to_address, amount)
        console.print(f"Transferred {amount} SOL from wallet {from_wallet.address} to {to_address}")
        await asyncio.sleep(1)

    except ValueError:
        console.print("[red]Invalid input[/red]")
        await asyncio.sleep(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)

async def wallet_warmup_ui(launch_manager):
    try:
        await launch_manager.wallet_warmup()
        console.print("[green]Wallets warmed up successfully![/green]")
        await asyncio.sleep(1)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)

async def burn_dev_supply_ui(launch_manager):
    try:
        token_address = Prompt.ask("Enter the token address to burn from the dev wallet", default="")
        confirmation = Prompt.ask(f"Are you sure you want to burn all tokens for {token_address}? (y/n)",
                                    choices=["y", "n"], default="n")

        if confirmation.lower() == "y":
            await launch_manager.burn_dev_supply(token_address)
            console.print(f"[green]Burned all tokens for {token_address} from dev wallet![/green]")
        else:
            console.print("[yellow]Burn operation cancelled.[/yellow]")
        await asyncio.sleep(1)

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)



async def sniper_farmer_ui(launch_manager):
    console.clear()
    console.print("[bold green]Sniper Farmer Launch[/bold green]")
    try:
        num_wallets_to_use = int(Prompt.ask(f"Enter the number of sub-wallets to use (1-{launch_manager.num_sub_wallets})", default="1"))
        if not 1 <= num_wallets_to_use <= launch_manager.num_sub_wallets:
            console.print("[red]Invalid number of wallets[/red]")
            await asyncio.sleep(1)
            return

        token_configs = []
        liquidity_threshold_usds = []
        dev_buy_amounts = []

        for i in range(num_wallets_to_use):
            console.print(f"\n[bold blue]--- Configuration for Wallet {i+1} ---[/bold blue]")
            token_name = Prompt.ask("Enter Token Name", default=f"Token{i+1}")
            token_symbol = Prompt.ask("Enter Token Symbol", default=f"TKN{i+1}")

            image_folder = "images"
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)

            image_path = None
            potential_image_path = os.path.join(image_folder, f"image_wallet_{i+1}.png")
            
            if Prompt.ask(f"Do you want to specify an image for Wallet {i+1}? (y/n)", choices=["y", "n"], default="n") == 'y':
                custom_image_path = Prompt.ask(f"Enter path to image file for Wallet {i+1} (e.g., images/image_wallet_{i+1}.png)", default=potential_image_path)
                if os.path.exists(custom_image_path):
                    image_path = custom_image_path
                    console.print(f"[green]Using image: {image_path}[/green]")
                else:
                    console.print(f"[yellow]Image not found at {custom_image_path}. Proceeding without image for this token.[/yellow]")
            else:
                console.print(f"[yellow]No image specified for this token.[/yellow]")

            token_description = Prompt.ask("Enter Token Description", default="")
            token_telegram = Prompt.ask("Enter Telegram link (optional)", default="")
            token_website = Prompt.ask("Enter Website link (optional)", default="")
            
            token_configs.append(Token(token_name, token_symbol, image_path=image_path,
                                       description=token_description, telegram=token_telegram, website=token_website))
            
            # Prompt for dev buy amount for each wallet
            dev_buy_amount = float(Prompt.ask(f"Enter amount (SOL) for Wallet {i+1} to buy on token creation", default="0.001"))
            dev_buy_amounts.append(dev_buy_amount)

            # Prompt for liquidity threshold for each wallet
            liquidity_threshold_usd = float(Prompt.ask(f"Enter the USD liquidity threshold for Wallet {i+1} (to trigger creator wallet sell)", default="100.0"))
            liquidity_threshold_usds.append(liquidity_threshold_usd)

        use_jito = Prompt.ask("Bundle transactions into one block with Jito? (y/n)", choices=["y", "n"], default="y") == 'y'

        # Call the new launch_actions function (to be implemented)
        await sniper_farmer_launch(launch_manager, token_configs, liquidity_threshold_usds, dev_buy_amounts, use_jito)

        console.print("[green]Sniper Farmer process initiated![/green]")
        Prompt.ask("Press Enter to return to the main menu")

    except ValueError:
        console.print("[red]Invalid input, please enter a number[/red]")
        await asyncio.sleep(1)
    except EOFError:
        logging.error("EOFError: Input stream closed unexpectedly. Exiting Sniper Farmer UI.")
        console.print("[red]Input stream closed unexpectedly. Returning to main menu.[/red]")
        await asyncio.sleep(2)
    except Exception as e:
        logging.error(f"An unexpected error occurred in Sniper Farmer UI: {e}")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        await asyncio.sleep(2)

async def launch_ui(launch_manager):
    launch_options = [
        ("Bundle Launch", 1),
        ("Clone + Snipe Launch", 2),
        ("Snipe Only", 3),
        ("Bundle + Stagger", 4),
        ("Main menu", 5)
    ]
    while True:
        console.clear()
        console.print("Launch Manager")
        table = Table(show_header=False, box=None)
        table.add_column(justify="left")
        for i, (option_name, _) in enumerate(launch_options):
            table.add_row(f"[bold]{i + 1}.[/bold] {option_name}")
        console.print(table)

        try:
            choice = int(Prompt.ask("Choose an option", default="5"))
            logging.info(f"User chose launch option: {choice}")
            if choice == 1:
                console.print("Launching in Bundle Mode...")
                num_wallets = int(Prompt.ask(f"Enter the number of wallets to use (1-{launch_manager.num_sub_wallets})",
                                            default="3"))
                if not 1 <= num_wallets <= launch_manager.num_sub_wallets:
                    console.print("[red]Invalid number of wallets[/red]")
                    await asyncio.sleep(1)
                    continue
                token_name = Prompt.ask("Enter Token Name", default="MyToken")
                token_symbol = Prompt.ask("Enter Token Symbol", default="MTK")

                # Check for image in the 'images' subfolder
                image_folder = "images"
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)

                image_path = None
                potential_image_path = os.path.join(image_folder, "image.png") # This is the change

                if os.path.exists(potential_image_path):
                    image_path = potential_image_path
                    console.print(f"[green]Found image: {image_path}[/green]")
                else:
                    console.print(f"[yellow]No image found in {image_folder}. Proceeding without image.[/yellow]")
                 #Request info for token to put into IPFS
                token_description = Prompt.ask("Enter Token Description", default="")
                token_telegram = Prompt.ask("Enter Telegram link (optional)", default="")
                token_website = Prompt.ask("Enter Website link (optional)", default="")
                token = Token(token_name, token_symbol, image_path=image_path, description = token_description, telegram=token_telegram, website=token_website)

                # New Prompt for Dev Wallet Buy Amount (ADDED HERE)
                dev_buy_amount_str = Prompt.ask("Enter amount (SOL) to buy with Dev Wallet on create", default="0.001")
                try:
                    dev_buy_amount = float(dev_buy_amount_str)
                except ValueError:
                    console.print("[red]Invalid input for Dev Wallet Buy Amount. Using default 0.001[/red]")
                    dev_buy_amount = 0.001 # Default value if input is invalid
                logging.info(f"User entered Dev Wallet Buy Amount: {dev_buy_amount}")


                amounts = []
                for i in range(num_wallets):
                   amount = float(Prompt.ask(f"Enter buy amount (SOL) for Wallet {i + 1}", default="0.01"))
                   amounts.append(amount)
                use_jito = Prompt.ask("Bundle transactions into one block with Jito? (y/n)", choices=["y", "n"], default="y")
                await bundle_launch(launch_manager, token, num_wallets, amounts, use_jito == 'y', dev_buy_amount=dev_buy_amount) # MODIFIED - Pass dev_buy_amount
                console.print("Launched token")
                await asyncio.sleep(1)

            elif choice == 2:
              console.print("Launching in Clone + Snipe Mode...")
              num_wallets = int(Prompt.ask(
                    f"Enter the number of wallets to use (1-{launch_manager.num_sub_wallets})",
                    default="5"))
              if not 1 <= num_wallets <= launch_manager.num_sub_wallets:
                    console.print("[red]Invalid number of wallets[/red]")
                    await asyncio.sleep(1)
                    continue
              existing_token_address = Prompt.ask("Enter the Existing Token Address to Clone and Snipe",
                                                     default="").strip()

              # New Prompt for Dev Wallet Buy Amount (ADDED HERE)
              dev_buy_amount_str = Prompt.ask("Enter amount (SOL) to buy with Dev Wallet on create", default="0.001")
              try:
                  dev_buy_amount = float(dev_buy_amount_str)
              except ValueError:
                  console.print("[red]Invalid input for Dev Wallet Buy Amount. Using default 0.001[/red]")
                  dev_buy_amount = 0.001 # Default value if input is invalid
              logging.info(f"User entered Dev Wallet Buy Amount: {dev_buy_amount}")


              try:

                    amounts = []
                    for i in range(num_wallets):
                        amount = float(Prompt.ask(f"Enter buy amount (SOL) for Wallet {i + 1}", default="0.005"))
                        amounts.append(amount)
                    use_jito = Prompt.ask("Bundle transactions into one block with Jito? (y/n)", choices=["y", "n"], default="y")
                    token = Token("Cloned", "clone")
                    await clone_and_snipe(launch_manager, token, num_wallets, amounts, use_jito == 'y', existing_token_address, dev_buy_amount=dev_buy_amount) # MODIFIED - Pass dev_buy_amount
                    console.print("Launched token")
                    await asyncio.sleep(1)
              except Exception as e:
                    logging.error(f"Error with Clone + Snipe Launch: {e}")
                    console.print(f"[red]Error with Clone + Snipe Launch: {e}[/red]")
            elif choice == 3:
                 console.print("Launching in Snipe Only Mode...")
                 num_wallets = int(Prompt.ask(f"Enter the number of wallets to use (1-{launch_manager.num_sub_wallets})",
                                            default="3"))  # number of wallets to use
                 if not 1 <= num_wallets <= launch_manager.num_sub_wallets:
                    console.print("[red]Invalid number of wallets[/red]")
                    await asyncio.sleep(1)
                    continue

                 token_address = Prompt.ask("Enter Token Address To Snipe", default="")

                 # *** THIS IS THE KEY CHANGE ***
                 token = Token("Snipe", "SNIPE") # Changed Token creation
                 token.mint_address = token_address   # SET THE MINT ADDRESS HERE!

                 amounts = []
                 for i in range(num_wallets):
                    amount = float(Prompt.ask(f"Enter buy amount (SOL) for Wallet {i + 1}", default="0.01"))
                    amounts.append(amount)
                 use_jito = Prompt.ask("Bundle transactions into one block with Jito? (y/n)", choices=["y", "n"], default="y")
                 await snipe_only(launch_manager, token, num_wallets, amounts, use_jito == 'y')
                 console.print("Launched token")
                 await asyncio.sleep(1)

            elif choice == 4:
                console.print("Launching in Bundle + Stagger mode...")
                num_wallets = int(Prompt.ask(f"Enter the number of wallets to use (1-{launch_manager.num_sub_wallets})",
                                        default="3"))
                if not 1 <= num_wallets <= launch_manager.num_sub_wallets:
                   console.print("[red]Invalid number of wallets[/red]")
                   await asyncio.sleep(1)
                   continue

                bundle_or_clone = Prompt.ask("Create new token (C) or clone existing (E)?", choices=["c", "e"], default="c")
                clone_address = None
                if bundle_or_clone == 'e':
                    clone_address = Prompt.ask("Enter the existing token address to clone", default="").strip()

                token_name = None
                token_symbol = None
                if bundle_or_clone == 'c':
                    token_name = Prompt.ask("Enter Token Name", default="MyToken")
                    token_symbol = Prompt.ask("Enter Token Symbol", default="MTK")
                #token = Token(token_name, token_symbol)
                image_folder = "images"  # Define image folder name
                if not os.path.exists(image_folder):  # Create the folder if it doesn't exist
                    os.makedirs(image_folder)

                image_path = None
                potential_image_path = os.path.join(image_folder, "image.png") # This is the change

                if os.path.exists(potential_image_path):
                    image_path = potential_image_path
                    console.print(f"[green]Found image: {image_path}[/green]")
                else:
                    console.print(
                        f"[yellow]No image found in {image_folder}. Proceeding without image.[/yellow]")
                token_description = Prompt.ask("Enter Token Description", default="")
                token_telegram = Prompt.ask("Enter Telegram link (optional)", default="")
                token_website = Prompt.ask("Enter Website link (optional)", default="")

                token = Token(token_name, token_symbol, image_path=image_path,description = token_description, telegram=token_telegram, website=token_website)

                # New Prompt for Dev Wallet Buy Amount (ADDED HERE)
                dev_buy_amount_str = Prompt.ask("Enter amount (SOL) to buy with Dev Wallet on create", default="0.001")
                try:
                    dev_buy_amount = float(dev_buy_amount_str)
                except ValueError:
                    console.print("[red]Invalid input for Dev Wallet Buy Amount. Using default 0.001[/red]")
                    dev_buy_amount = 0.001 # Default value if input is invalid
                logging.info(f"User entered Dev Wallet Buy Amount: {dev_buy_amount}")


                amounts = []
                for i in range(num_wallets):
                    amount = float(Prompt.ask(f"Enter buy amount (SOL) for Wallet {i + 1}", default="0.01"))
                    amounts.append(amount)
                #delay = float(Prompt.ask("Enter Stagger delay", default="1.0"))
                use_jito = Prompt.ask("Bundle transactions into one block with Jito? (y/n)", choices=["y", "n"], default="n")
                delay = float(Prompt.ask("Enter Stagger delay", default="1.0"))
                await bundle_stagger_launch(launch_manager, token, num_wallets, amounts,
                                            {'delay': delay}, bundle_or_clone == 'e', clone_address, dev_buy_amount=dev_buy_amount) # MODIFIED - Pass dev_buy_amount
                console.print("Launched token in bundle stagger mode")
                await asyncio.sleep(1)

            elif choice == 5:
                break
            else:
                logging.warning(f"Invalid launch option chosen: {choice}")
                console.print("[red]Invalid Option[/red]")
                await asyncio.sleep(1)
        except ValueError:
            logging.error("Invalid input, please enter a number")
            console.print("[red]Invalid input, please enter a number[/red]")
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            console.print(f"[red]An unexpected error occurred: {e}[/red]")
            await asyncio.sleep(2)


async def sell_ui(launch_manager):
    sell_options = [
        ("Dump All", 1),
        ("Delayed Sell %", 2),
        ("Single Wallet Sell", 3),
        ("Dev Dump All", 4),
        ("Transfer Sell", 5),
        ("Return to Main Menu", 6)
    ]
    while True:
        console.clear()
        console.print("Sell Manager")
        table = Table(show_header=False, box=None)
        table.add_column(justify="left")
        for i, (option_name, _) in enumerate(sell_options):
            table.add_row(f"[bold]{i + 1}.[/bold] {option_name}")
        console.print(table)

        try:
            choice = int(Prompt.ask("Choose an option", default="6"))
            logging.info(f"User chose sell option: {choice}")
            if choice == 1:
                percentage_to_sell = float(Prompt.ask("Enter percentage to sell (1-100)", default="100"))
                await launch_manager.dump_all(percentage_to_sell=percentage_to_sell)

            elif choice == 2:
                delay = float(Prompt.ask("Enter the delay in seconds between each wallet", default="0"))
                await launch_manager.delayed_sell(delay_in_seconds=delay)
                await asyncio.sleep(1)


            elif choice == 3:
                try:
                    wallet_index = int(Prompt.ask(
                        f"Enter the wallet number (1-{len(launch_manager.sub_wallets)}) to sell from",
                        default="1")) - 1  # Adjust for 0-based indexing
                    if not 0 <= wallet_index < len(launch_manager.sub_wallets):
                        console.print("[red]Invalid wallet number[/red]")
                        await asyncio.sleep(1)
                        continue

                    percentage_to_sell = float(Prompt.ask("Enter percentage to sell (1-100)", default="100"))
                    wallet_address = launch_manager.sub_wallets[wallet_index].address # Get address from wallets
                    await launch_manager.single_wallet_sell(wallet_address=wallet_address, percentage_to_sell=percentage_to_sell)
                    await asyncio.sleep(1)
                except ValueError:
                    logging.error("Invalid input for single wallet sell parameters")
                    console.print("[red]Invalid input[/red]")
                    await asyncio.sleep(1)

            elif choice == 4:
                await launch_manager.dev_dump_all()
                await asyncio.sleep(1)

            elif choice == 5:
                 try:
                    wallet_index = int(Prompt.ask(
                        f"Enter the wallet number (1-{len(launch_manager.sub_wallets)}) to transfer tokens to",
                        default="1")) - 1  # Adjust for 0-based indexing
                    if not 0 <= wallet_index < len(launch_manager.sub_wallets):
                        console.print("[red]Invalid wallet number[/red]")
                        await asyncio.sleep(1)
                        continue
                    to_wallet_address = launch_manager.sub_wallets[wallet_index].address

                    await launch_manager.transfer_sell(to_wallet_address=to_wallet_address)
                    await asyncio.sleep(1)

                 except ValueError:
                    logging.error("Invalid input for select wallet to transfer parameters")
                    console.print("[red]Invalid input[/red]")
                    await asyncio.sleep(1)


            elif choice == 6:
                break
            else:
                logging.warning(f"Invalid sell option chosen: {choice}")
                console.print("[red]Invalid Option[/red]")
                await asyncio.sleep(1)
        except ValueError:
            logging.error("Invalid input, please enter a number")
            console.print("[red]Invalid input, please enter a number[/red]")
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            console.print(f"[red]An unexpected error occurred: {e}[/red]")
            await asyncio.sleep(2)


async def vanity_address_ui(launch_manager):
    console.clear()
    console.print("[bold green]Vanity Address Generator[/bold green]")

    position_choice = Prompt.ask("Do you want to match at the [b]front[/b] or [b]back[/b] of the address?", choices=["front", "back"])
    match_string = Prompt.ask("Enter the string to match (case-insensitive)").lower()
    batch_size = int(Prompt.ask("Enter batch size for wallet generation (e.g., 1000)", default="1000"))
    num_threads = int(Prompt.ask("Enter number of threads to use", default="4"))

    found_wallets = []
    stop_event = threading.Event()

    console.print(f"Generating wallets to find addresses with '{match_string}' at the {position_choice}...")
    
    def generate_and_check_wallets_sync(): # Renamed to avoid async in thread target
        nonlocal found_wallets
        while not stop_event.is_set():
            wallets_batch = []
            for _ in range(batch_size):
                if stop_event.is_set():
                    break
                new_wallet = Wallet()
                # Synchronously create keypair for a single wallet
                asyncio.run(new_wallet.create_keypair())
                wallets_batch.append(new_wallet)

            for wallet in wallets_batch:
                if stop_event.is_set():
                    break
                address = wallet.address.lower()
                is_match = False
                if position_choice == "front":
                    if address.startswith(match_string):
                        is_match = True
                elif position_choice == "back":
                    if address.endswith(match_string):
                        is_match = True

                if is_match:
                    console.print(f"[green]Found matching wallet:[/green] Address: {wallet.address}, Seed: {wallet.seed_phrase}")
                    found_wallets.append({"address": wallet.address, "seed_phrase": wallet.seed_phrase})
                    # Optionally, stop all threads once a wallet is found
                    stop_event.set()
                    break

            if not stop_event.is_set():
                time.sleep(0.01) # Small sleep to yield control

    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=generate_and_check_wallets_sync)
        threads.append(thread)
        thread.start()

    try:
        while not stop_event.is_set():
            time.sleep(1) # Keep main thread alive and check for stop event
            # This count will not be accurate for multiple threads, but serves as a basic indicator
            console.print(f"Wallets found: {len(found_wallets)}", end="\r")

    except KeyboardInterrupt:
        console.print("[yellow]Stopping wallet generation...[/yellow]")
        stop_event.set()

    for thread in threads:
        thread.join()

    if found_wallets:
        output_filename = f"vanity_wallets_{match_string}.json"
        with open(output_filename, 'w') as f:
            json.dump(found_wallets, f, indent=4)
        console.print(f"[green]Found {len(found_wallets)} vanity wallets. Saved to {output_filename}[/green]")
    else:
        console.print("[red]No vanity wallets found.[/red]")

    Prompt.ask("Press Enter to return to the main menu")