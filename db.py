"""
Database models for Meme Trader V4 Pro
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Create database URL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///meme_trader.db')

# Create engine
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    token_address = Column(String)
    token_symbol = Column(String)
    chain = Column(String)
    amount = Column(Float)
    purchase_price_usd = Column(Float)
    current_price_usd = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

def get_db_session():
    """Get database session"""
    return SessionLocal()

def create_tables():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)

# Create tables on import
create_tables()