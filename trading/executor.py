
import logging
from services.zero_x import ZeroXService
from services.jupiter import JupiterService
from utils.key_manager import key_manager
from utils.cache import TTLCache

logger = logging.getLogger("executor")

class TradeExecutor:
    def __init__(self, key_manager: KeyRotationManager, safe_mode=True):
        self.key_manager = key_manager
        self.safe_mode = safe_mode
        self.zero_x = ZeroXService(key_manager)
        self.jupiter = JupiterService(key_manager)
        self.cache = TTLCache(ttl=30)

    async def execute_buy(self, token, amount, chain, slippage):
        if self.safe_mode:
            logger.info("SAFE_MODE enabled: dry-run only")
            return {"status": "dry-run", "token": token, "amount": amount, "chain": chain}
        try:
            if chain in ["ethereum", "bsc"]:
                quote = self.zero_x.get_swap_quote(token["sell"], token["buy"], amount)
                return {"status": "executed", "quote": quote}
            elif chain == "solana":
                quote = self.jupiter.get_swap_quote(token["input_mint"], token["output_mint"], amount)
                return {"status": "executed", "quote": quote}
            else:
                return {"error": "Unsupported chain"}
        except Exception as e:
            logger.error(f"Buy execution failed: {e}")
            return {"error": str(e)}

    async def execute_sell(self, token, amount, chain, slippage):
        if self.safe_mode:
            logger.info("SAFE_MODE enabled: dry-run only")
            return {"status": "dry-run", "token": token, "amount": amount, "chain": chain}
        try:
            if chain in ["ethereum", "bsc"]:
                quote = self.zero_x.get_swap_quote(token["sell"], token["buy"], amount)
                return {"status": "executed", "quote": quote}
            elif chain == "solana":
                quote = self.jupiter.get_swap_quote(token["input_mint"], token["output_mint"], amount)
                return {"status": "executed", "quote": quote}
            else:
                return {"error": "Unsupported chain"}
        except Exception as e:
            logger.error(f"Sell execution failed: {e}")
            return {"error": str(e)}

    async def panic_sell(self, tokens, chain, slippage):
        if self.safe_mode:
            logger.info("SAFE_MODE enabled: dry-run only")
            return {"status": "dry-run", "tokens": tokens, "chain": chain}
        results = []
        for token in tokens:
            result = await self.execute_sell(token, token.get("amount", 0), chain, slippage)
            results.append(result)
        return results
