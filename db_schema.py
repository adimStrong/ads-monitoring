"""
Database schema and setup for BINGO365 Monitoring
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()


class Agent(Base):
    """Agent/Team member table"""
    __tablename__ = 'agents'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    performances = relationship("AdPerformance", back_populates="agent")
    contents = relationship("AdContent", back_populates="agent")

    def __repr__(self):
        return f"<Agent(name='{self.name}')>"


class AdPerformance(Base):
    """Daily ad performance metrics per agent"""
    __tablename__ = 'ad_performance'

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=False)
    date = Column(Date, nullable=False)
    total_ad = Column(Integer, default=0)
    campaign = Column(String(255))
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr_percent = Column(Float, default=0.0)
    cpc = Column(Float, default=0.0)
    conversion_rate = Column(Float, default=0.0)
    rejected_count = Column(Integer, default=0)
    deleted_count = Column(Integer, default=0)
    active_count = Column(Integer, default=0)
    remarks = Column(Text)
    creative_folder = Column(Text)
    content_type = Column(String(100))
    content_summary = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="performances")

    # Indexes
    __table_args__ = (
        Index('idx_performance_agent_date', 'agent_id', 'date'),
        Index('idx_performance_date', 'date'),
    )


class AdContent(Base):
    """Ad content/creative tracking per agent"""
    __tablename__ = 'ad_content'

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=False)
    date = Column(Date, nullable=False)
    content_type = Column(String(50))  # 'Primary Text' or 'Headline'
    primary_content = Column(Text)
    condition = Column(String(100))
    status = Column(String(50))
    primary_adjustment = Column(Text)
    remarks = Column(Text)
    content_hash = Column(String(64))  # SHA256 hash for quick duplicate detection
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agent = relationship("Agent", back_populates="contents")

    # Indexes
    __table_args__ = (
        Index('idx_content_agent_date', 'agent_id', 'date'),
        Index('idx_content_date', 'date'),
        Index('idx_content_hash', 'content_hash'),
    )


class ContentSimilarity(Base):
    """Pre-computed content similarity scores"""
    __tablename__ = 'content_similarity'

    id = Column(Integer, primary_key=True)
    content_id_1 = Column(Integer, ForeignKey('ad_content.id'), nullable=False)
    content_id_2 = Column(Integer, ForeignKey('ad_content.id'), nullable=False)
    similarity_score = Column(Float, nullable=False)
    analysis_date = Column(Date, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_similarity_content1', 'content_id_1'),
        Index('idx_similarity_content2', 'content_id_2'),
        Index('idx_similarity_score', 'similarity_score'),
    )


class DailyStats(Base):
    """Aggregated daily statistics per agent"""
    __tablename__ = 'daily_stats'

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=False)
    date = Column(Date, nullable=False)
    total_content_posts = Column(Integer, default=0)
    unique_content_count = Column(Integer, default=0)
    recycled_content_count = Column(Integer, default=0)
    content_freshness_score = Column(Float, default=0.0)  # Percentage of unique content
    avg_similarity_score = Column(Float, default=0.0)

    # Indexes
    __table_args__ = (
        Index('idx_daily_stats_agent_date', 'agent_id', 'date'),
    )


def init_database():
    """Initialize database and create tables"""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    print("Database tables created successfully!")
    return engine


def get_session():
    """Get database session"""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    return Session()


def seed_agents():
    """Seed initial agent data"""
    from config import AGENTS

    session = get_session()
    try:
        for agent_config in AGENTS:
            existing = session.query(Agent).filter_by(name=agent_config["name"]).first()
            if not existing:
                agent = Agent(name=agent_config["name"])
                session.add(agent)
                print(f"Added agent: {agent_config['name']}")
        session.commit()
        print("Agents seeded successfully!")
    except Exception as e:
        session.rollback()
        print(f"Error seeding agents: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    print("Initializing BINGO365 Monitoring Database...")
    init_database()
    seed_agents()
