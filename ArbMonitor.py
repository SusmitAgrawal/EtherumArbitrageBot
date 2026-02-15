import requests
from web3 import Web3 #library to work with Etherum and retrieval of related data.
import time
import json
import random
from dotenv import load_dotenv
import os

#load env vars:
load_dotenv()

#Setup to obtain live market data
INFURA_URL = f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}"
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Pool and ABI Setup to retrieve uniswap data
POOL_ADDRESS = Web3.to_checksum_address("0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")
POOL_ABI = json.loads('''[
    {"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"liquidity","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],"stateMutability":"view","type":"function"}
]''')

# Trading Constants
UNISWAP_GAS_USE = 184523  # Average gas used for a V3 swap (can be changed)
SYMBOL = "ETHUSDC"
ORDER_DEPTH = 5
MIN_PROFIT = 0.01
MAX_ITER = 10
MAX_TRADE_SIZE=50*(10**9)

def get_gas_cost_usd(eth_price):
    """Calculates the current cost of a swap in USD."""
    gas_price_wei = w3.eth.gas_price
    gas_cost_eth = (gas_price_wei * UNISWAP_GAS_USE) / 10**18
    return gas_cost_eth * eth_price*random.uniform(1,25)

def get_uniswap_price():
    contract = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
    slot0 = contract.functions.slot0().call()
    ratio_raw = (slot0[0] / (2**96))**2
    return (1 / ratio_raw) * (10**12)

def get_binance_price():
    return float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYMBOL}").json()['price'])

def get_current_liquidity():
    contract = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
    current_liquidity = contract.functions.liquidity().call()

    return current_liquidity

def calculate_optimal_size(binance_price, current_sqrtP, liquidity):
    """
    Finds the exact amount of ETH to trade so that Uniswap price 
    becomes equal to the Binance price. Includes slippage calculations too.
    """
    target_sqrtP = int(((binance_price / 10**12)**0.5) * (2**96))
    delta_sqrtP = target_sqrtP - current_sqrtP
    raw_eth_size = (liquidity * abs(delta_sqrtP)) // (2**96)
    optimal_eth = raw_eth_size / 10**18
    
    return optimal_eth

def monitor():
    print("--- Etherum Arbitrage Bot ---")
    last_block = 0
    net_profit = 0

    total_qty = 0
    for iteration in range(MAX_ITER):
        print(iteration+1)
        try:
            current_block = w3.eth.block_number

            if current_block > last_block:
                uni_p = get_uniswap_price()
                bin_p = get_binance_price()
                
                # Get the raw data needed for math
                contract = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)
                slot0 = contract.functions.slot0().call()
                L = contract.functions.liquidity().call()
                sqrtPriceX96 = slot0[0]
                print(L)
                optimal_size = calculate_optimal_size(bin_p, sqrtPriceX96, L)
                safe_trade_size = min(optimal_size, MAX_TRADE_SIZE) 
                
                if safe_trade_size > 0.01: # Don't trade tiny amounts
                    print(f"Optimal Trade Calculated: {safe_trade_size:.4f} ETH")
                
                gross_profit = (uni_p - bin_p) * safe_trade_size
                gas_cost_usd = get_gas_cost_usd(bin_p)
                trade_profit = (gross_profit - gas_cost_usd)
                print(f"\n[Block {current_block}] | Binance ETH Price: ${bin_p:,.2f}")
                print(f"\n[Block {current_block}] | Uniswap ETH Price: ${uni_p:,.2f}")
                print(f"Gross Gap: ${gross_profit:+.2f}")
                print(f"Gas Cost:  ${gas_cost_usd:.2f}")
                print(f"Trade DIRECTION: {'BUY @ Binance, SELL @ Uniswap' if trade_profit > 0 else 'BUY @ Uniswap, SELL @ Binance'}")
                print(f"Trade PROFIT: {'Profitable, Execute BUY @ Binance, SELL @ Uniswap, with Profit = ' if trade_profit > 0 else 'Profitable, execute BUY @ Uniswap, SELL @ Binance with Profit = '} ${trade_profit:+.2f}")
                if abs(trade_profit) > MIN_PROFIT:
                     net_profit += abs(trade_profit)     
                     print(f"NET PROFIT: ${net_profit:+.2f}")
                
                last_block = current_block
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
    print(f"FINAL NET PROFIT: ${net_profit:+.2f}")
    
if __name__ == "__main__":
    monitor()