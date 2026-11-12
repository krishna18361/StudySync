from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        with engine.begin() as conn:
            if "users" in tables:
                user_cols = [c["name"] for c in inspector.get_columns("users")]
                if "learner_level" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN learner_level VARCHAR(32) DEFAULT 'beginner'"))
                if "learning_preferences" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN learning_preferences JSON DEFAULT NULL"))
            if "summaries" in tables:
                summary_cols = [c["name"] for c in inspector.get_columns("summaries")]
                if "examples" not in summary_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN examples JSON DEFAULT '[]'"))
                if "status" not in summary_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN status VARCHAR(32) DEFAULT 'ready'"))
                if "error" not in summary_cols:
                    conn.execute(text("ALTER TABLE summaries ADD COLUMN error TEXT DEFAULT NULL"))
            if "quizzes" in tables:
                quiz_cols = [c["name"] for c in inspector.get_columns("quizzes")]
                if "status" not in quiz_cols:
                    conn.execute(text("ALTER TABLE quizzes ADD COLUMN status VARCHAR(32) DEFAULT 'ready'"))
                if "error" not in quiz_cols:
                    conn.execute(text("ALTER TABLE quizzes ADD COLUMN error TEXT DEFAULT NULL"))
            if "topic_scores" in tables:
                topic_cols = [c["name"] for c in inspector.get_columns("topic_scores")]
                if "skipped" not in topic_cols:
                    conn.execute(text("ALTER TABLE topic_scores ADD COLUMN skipped INTEGER DEFAULT 0"))
    except Exception:
        # Schema already matches or doesn't support alter
        pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

