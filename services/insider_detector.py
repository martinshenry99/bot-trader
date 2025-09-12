
class InsiderDetector:
    """
    Insider Detector for scoring, labeling, and candidate analysis.
    """
    def __init__(self, min_score=10):
        self.min_score = min_score

    def score_wallet(self, wallet, txs, token_events, lp_events, dev_wallets):
        score = 0
        # Deployer Proximity (0–6 pts)
        deployer_interactions = sum(1 for tx in txs if tx.get('counterparty') in dev_wallets)
        score += min(deployer_interactions, 6)
        # Early Buyer Behavior (0–5 pts)
        early_buys = sum(1 for event in token_events if event.get('buyer_rank', 999) <= 10)
        score += min(early_buys, 5)
        # High Early Multipliers (0–4 pts)
        high_mults = sum(1 for tx in txs if tx.get('multiplier', 0) >= 10 and tx.get('early'))
        score += min(high_mults, 4)
        # Cluster Trading (0–3 pts)
        cluster_trades = sum(1 for tx in txs if tx.get('counterparty') in dev_wallets and tx.get('cluster'))
        score += min(cluster_trades, 3)
        # Suspicious Inflows (0–2 pts)
        suspicious_inflows = sum(1 for tx in txs if tx.get('from_fresh_deployer'))
        score += min(suspicious_inflows, 2)
        return score

    def label_wallet(self, score):
        if score >= 15:
            return "Probable Insider"
        elif score >= 10:
            return "Possible Insider"
        return "Normal"

    def compute_insider_score(self, wallet_address, txs, token_events, lp_events, dev_wallets):
        """
        Compute the insider score for a given wallet address
        """
        wallet = {'address': wallet_address, 'txs': txs, 'token_events': token_events, 'lp_events': lp_events}
        score = self.score_wallet(wallet, txs, token_events, lp_events, dev_wallets)
        label = self.label_wallet(score)
        return {
            'score': score,
            'label': label,
            'address': wallet_address
        }

    def analyze_candidates(self, candidates, dev_wallets):
        results = []
        for wallet in candidates:
            txs = wallet.get('txs', [])
            token_events = wallet.get('token_events', [])
            lp_events = wallet.get('lp_events', [])
            score = self.score_wallet(wallet, txs, token_events, lp_events, dev_wallets)
            label = self.label_wallet(score)
            results.append({
                'address': wallet.get('address'),
                'score': score,
                'label': label
            })
        return results
