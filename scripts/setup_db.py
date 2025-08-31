#!/usr/bin/env python3
"""
Database initialization script for Meme Trader V4 Pro
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import create_tables, get_db_session, User, Token
from config import Config

def initialize_database():
    """Initialize database with tables and sample data"""
    try:
        print("🗄️  Initializing Meme Trader V4 Pro Database...")
        
        # Validate configuration
        Config.validate()
        print("✅ Configuration validated successfully")
        
        # Create all tables
        create_tables()
        print("✅ Database tables created successfully")
        
        # Add sample data
        db = get_db_session()
        try:
            # Check if sample data already exists
            existing_tokens = db.query(Token).count()
            if existing_tokens == 0:
                # Add sample tokens for testing
                sample_tokens = [
                    Token(
                        address="0x742d35Cc6aD5C87B7c2d3fa7f5C95Ab3cde74d6b",
                        name="Test Token 1",
                        symbol="TEST1",
                        decimals=18,
                        is_monitored=False,
                        price_usd=0.001,
                        market_cap=1000000,
                        liquidity_usd=50000,
                        volume_24h=10000
                    ),
                    Token(
                        address="0xA0b86a33E6441ba0BB7e1ae5E3e7BAaD5D1D7e3c",
                        name="Test Token 2", 
                        symbol="TEST2",
                        decimals=18,
                        is_monitored=False,
                        price_usd=0.0005,
                        market_cap=500000,
                        liquidity_usd=25000,
                        volume_24h=5000
                    )
                ]
                
                for token in sample_tokens:
                    db.add(token)
                
                db.commit()
                print("✅ Sample tokens added to database")
            else:
                print("✅ Database already contains token data")
                
        finally:
            db.close()
        
        print("\n🚀 Database initialization completed successfully!")
        print("\n📊 Database Schema:")
        print("   • users - Telegram user accounts")
        print("   • wallets - User wallet addresses")
        print("   • tokens - Token information and analysis")
        print("   • trades - Trade execution records")
        print("   • transactions - Blockchain transaction history")
        print("   • monitoring_alerts - Real-time alerts")
        
        print(f"\n💾 Database Location: {Config.DATABASE_URL}")
        print("🟢 Ready to start the Meme Trader bot!")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = initialize_database()
    sys.exit(0 if success else 1)
