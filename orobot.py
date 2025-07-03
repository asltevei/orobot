import os
import time
import json
import requests
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OroSwapBot:
    def __init__(self):
        self.rpc_url = os.getenv('RPC_URL', 'https://testnet-rpc.zigchain.com/')
        self.private_key = os.getenv('PRIVATE_KEY')
        self.max_loops = int(os.getenv('MAX_LOOPS', 10))
        self.swap_amount = int(os.getenv('SWAP_AMOUNT', 1000000))
        self.liquidity_amount = int(os.getenv('LIQUIDITY_AMOUNT', 500000))
        
        # Contract addresses
        self.oro_contract = "zig10rfjm85jmzfhravjwpq3hcdz8ngxg7lxd0drkr.uoro"
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.account = Account.from_key(self.private_key)
        self.wallet_address = self.account.address
        
        # Router and Factory addresses (you'll need to get these from OroSwap)
        self.router_address = None  # Will be fetched
        self.factory_address = None  # Will be fetched
        
        logger.info(f"Initialized bot for wallet: {self.wallet_address}")
    
    def get_contract_addresses(self):
        """Fetch contract addresses from OroSwap API"""
        try:
            # This would typically come from OroSwap documentation or API
            # For now, we'll use placeholder addresses
            self.router_address = "0x..." # Replace with actual router address
            self.factory_address = "0x..." # Replace with actual factory address
            logger.info("Contract addresses loaded")
        except Exception as e:
            logger.error(f"Failed to get contract addresses: {e}")
    
    def get_router_abi(self):
        """Standard Uniswap V2 Router ABI (compatible with most DEXs)"""
        return [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "swapExactTokensForTokens",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenA", "type": "address"},
                    {"internalType": "address", "name": "tokenB", "type": "address"},
                    {"internalType": "uint256", "name": "amountADesired", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountBDesired", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountAMin", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountBMin", "type": "uint256"},
                    {"internalType": "address", "name": "to", "type": "address"},
                    {"internalType": "uint256", "name": "deadline", "type": "uint256"}
                ],
                "name": "addLiquidity",
                "outputs": [
                    {"internalType": "uint256", "name": "amountA", "type": "uint256"},
                    {"internalType": "uint256", "name": "amountB", "type": "uint256"},
                    {"internalType": "uint256", "name": "liquidity", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "getAmountsOut",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def get_erc20_abi(self):
        """Standard ERC20 ABI for token interactions"""
        return [
            {
                "inputs": [
                    {"internalType": "address", "name": "spender", "type": "address"},
                    {"internalType": "uint256", "name": "amount", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"internalType": "address", "name": "owner", "type": "address"},
                    {"internalType": "address", "name": "spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def check_balance(self, token_address):
        """Check token balance"""
        try:
            if token_address == "native":
                balance = self.w3.eth.get_balance(self.wallet_address)
                return balance
            else:
                token_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=self.get_erc20_abi()
                )
                balance = token_contract.functions.balanceOf(self.wallet_address).call()
                return balance
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return 0
    
    def approve_token(self, token_address, spender_address, amount):
        """Approve token spending"""
        try:
            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self.get_erc20_abi()
            )
            
            # Check current allowance
            current_allowance = token_contract.functions.allowance(
                self.wallet_address, 
                spender_address
            ).call()
            
            if current_allowance >= amount:
                logger.info(f"Already approved sufficient amount: {current_allowance}")
                return True
            
            # Approve transaction
            approve_tx = token_contract.functions.approve(
                spender_address, 
                amount
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address)
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(approve_tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Approval transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"Approval confirmed: {receipt.transactionHash.hex()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error approving token: {e}")
            return False
    
    def swap_tokens(self, token_in, token_out, amount_in, min_amount_out=0):
        """Swap tokens using the router"""
        try:
            router_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=self.get_router_abi()
            )
            
            # Approve token spending
            if not self.approve_token(token_in, self.router_address, amount_in):
                return False
            
            # Get amounts out
            path = [Web3.to_checksum_address(token_in), Web3.to_checksum_address(token_out)]
            amounts_out = router_contract.functions.getAmountsOut(amount_in, path).call()
            
            if min_amount_out == 0:
                min_amount_out = int(amounts_out[1] * 0.95)  # 5% slippage
            
            # Build swap transaction
            deadline = int(time.time()) + 1800  # 30 minutes
            
            swap_tx = router_contract.functions.swapExactTokensForTokens(
                amount_in,
                min_amount_out,
                path,
                self.wallet_address,
                deadline
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 300000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address)
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(swap_tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Swap transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"Swap confirmed: {receipt.transactionHash.hex()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error swapping tokens: {e}")
            return False
    
    def add_liquidity(self, token_a, token_b, amount_a, amount_b):
        """Add liquidity to the pool"""
        try:
            router_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.router_address),
                abi=self.get_router_abi()
            )
            
            # Approve both tokens
            if not self.approve_token(token_a, self.router_address, amount_a):
                return False
            if not self.approve_token(token_b, self.router_address, amount_b):
                return False
            
            # Build add liquidity transaction
            deadline = int(time.time()) + 1800  # 30 minutes
            min_amount_a = int(amount_a * 0.95)  # 5% slippage
            min_amount_b = int(amount_b * 0.95)  # 5% slippage
            
            add_liquidity_tx = router_contract.functions.addLiquidity(
                Web3.to_checksum_address(token_a),
                Web3.to_checksum_address(token_b),
                amount_a,
                amount_b,
                min_amount_a,
                min_amount_b,
                self.wallet_address,
                deadline
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 400000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address)
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(add_liquidity_tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"Add liquidity transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            logger.info(f"Add liquidity confirmed: {receipt.transactionHash.hex()}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding liquidity: {e}")
            return False
    
    def run_bot(self):
        """Main bot loop"""
        logger.info("Starting OroSwap Bot...")
        
        # Get contract addresses
        self.get_contract_addresses()
        
        if not self.router_address:
            logger.error("Router address not found. Please update the script with correct addresses.")
            return
        
        for loop_count in range(self.max_loops):
            logger.info(f"Starting loop {loop_count + 1}/{self.max_loops}")
            
            try:
                # Check balances
                zig_balance = self.check_balance("native")  # Assuming ZIG is native token
                oro_balance = self.check_balance(self.oro_contract)
                
                logger.info(f"ZIG Balance: {zig_balance}")
                logger.info(f"ORO Balance: {oro_balance}")
                
                # Perform swap (ZIG -> ORO)
                if zig_balance > self.swap_amount:
                    logger.info("Performing ZIG -> ORO swap...")
                    if self.swap_tokens("native", self.oro_contract, self.swap_amount):
                        logger.info("Swap successful!")
                        time.sleep(5)  # Wait for blockchain update
                    else:
                        logger.error("Swap failed!")
                        continue
                
                # Add liquidity
                updated_oro_balance = self.check_balance(self.oro_contract)
                if updated_oro_balance > self.liquidity_amount and zig_balance > self.liquidity_amount:
                    logger.info("Adding liquidity...")
                    if self.add_liquidity(
                        "native", 
                        self.oro_contract, 
                        self.liquidity_amount, 
                        self.liquidity_amount
                    ):
                        logger.info("Liquidity added successfully!")
                    else:
                        logger.error("Add liquidity failed!")
                
                # Wait before next loop
                if loop_count < self.max_loops - 1:
                    logger.info("Waiting 30 seconds before next loop...")
                    time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in loop {loop_count + 1}: {e}")
                continue
        
        logger.info("Bot completed all loops.")

def main():
    bot = OroSwapBot()
    bot.run_bot()

if __name__ == "__main__":
    main()
