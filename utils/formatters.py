from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def format_wallet_address(address, chain, label=None):
    short_addr = f"{address[:6]}...{address[-4:]}"
    explorer = {
        'ethereum': 'https://etherscan.io',
        'bsc': 'https://bscscan.com',
        'solana': 'https://solscan.io'
    }.get(chain, 'https://etherscan.io')
    url = f"{explorer}/address/{address}" if chain != 'solana' else f"{explorer}/account/{address}"
    if label:
        return f"[{label} ({short_addr})]({url})"
    return f"[{short_addr}]({url})"

def format_token_address(contract, chain, symbol=None):
    short_addr = f"{contract[:6]}...{contract[-4:]}"
    explorer = {
        'ethereum': 'https://etherscan.io',
        'bsc': 'https://bscscan.com',
        'solana': 'https://solscan.io'
    }.get(chain, 'https://etherscan.io')
    url = f"{explorer}/token/{contract}"
    if symbol:
        return f"[{symbol} ({short_addr})]({url})"
    return f"[{short_addr}]({url})"

def format_analysis_result(analysis):
    # Example formatting for wallet analysis
    addr = analysis.get('address', 'Unknown')
    chain = analysis.get('chain', 'Unknown')
    score = analysis.get('score', 0)
    insider_score = analysis.get('insider_score', 0)
    label = analysis.get('insider_label', 'Normal')
    win_rate = analysis.get('win_rate', 0)
    max_mult = analysis.get('max_mult', 0)
    avg_roi = analysis.get('avg_roi', 0)
    volume_usd = analysis.get('volume_usd', 0)
    trades_count = analysis.get('trades_count', 0)
    last_active = analysis.get('last_active', 0)
    return (
        f"🔍 *Wallet Analysis*\n"
        f"Address: `{addr}` [{chain}]\n"
        f"Score: {score}/100 | Insider: {label} ({insider_score}/20)\n"
        f"Win Rate: {win_rate:.1f}% | Max Mult: {max_mult:.1f}x | Avg ROI: {avg_roi:.1f}x\n"
        f"Volume: ${volume_usd:,.0f} | Trades: {trades_count}\n"
        f"Last Active: {last_active}\n"
    )
