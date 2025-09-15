"""
Database models for API monitoring
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

class APIRequest(Base):
    """Model for storing API request data"""
    __tablename__ = 'api_requests'
    
    id = Column(Integer, primary_key=True)
    api = Column(String, index=True)
    endpoint = Column(String)
    status_code = Column(Integer)
    latency = Column(Float)
    timestamp = Column(DateTime, index=True)
    response_data = Column(JSON, nullable=True)

class RateLimit(Base):
    """Model for storing rate limit data"""
    __tablename__ = 'rate_limits'
    
    id = Column(Integer, primary_key=True)
    api = Column(String, unique=True)
    limit = Column(Integer)
    window = Column(Integer)  # Time window in seconds
    current_usage = Column(Integer)
    last_reset = Column(DateTime)

class CircuitBreaker(Base):
    """Model for storing circuit breaker state"""
    __tablename__ = 'circuit_breakers'
    
    id = Column(Integer, primary_key=True)
    api = Column(String, unique=True)
    state = Column(String)  # closed, open, half-open
    failure_count = Column(Integer)
    last_failure = Column(DateTime)
    cooldown_period = Column(Integer)  # seconds
    threshold = Column(Integer)
    
# Database setup
DB_URL = os.getenv('DB_URL', 'sqlite:///api_monitoring.db')
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
