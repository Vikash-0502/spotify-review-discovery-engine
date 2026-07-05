"""SQLAlchemy ORM schema — aligned with docs.md/phase-0/Data Model Draft.md."""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 384


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RawReview(Base):
    __tablename__ = "raw_reviews"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_raw_reviews_platform_external_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    review: Mapped["Review | None"] = relationship(back_populates="raw_review", uselist=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_posted_at", "posted_at"),
        Index("ix_reviews_platform", "platform"),
        Index("ix_reviews_sentiment", "sentiment"),
        Index("ix_reviews_is_discovery_related", "is_discovery_related"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    raw_review_id: Mapped[str] = mapped_column(String(36), ForeignKey("raw_reviews.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anonymized_author: Mapped[str] = mapped_column(String(50), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_discovery_related: Mapped[bool] = mapped_column(Boolean, default=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    user_segment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    raw_review: Mapped["RawReview"] = relationship(back_populates="review")
    embedding: Mapped["ReviewEmbedding | None"] = relationship(back_populates="review", uselist=False)
    theme_links: Mapped[list["ReviewTheme"]] = relationship(back_populates="review")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="review")


class ReviewEmbedding(Base):
    __tablename__ = "review_embeddings"
    __table_args__ = (
        Index(
            "ix_review_embeddings_vector_hnsw",
            "embedding_vector",
            postgresql_using="hnsw",
            postgresql_ops={"embedding_vector": "vector_cosine_ops"},
        ),
    )

    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id"), primary_key=True)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_vector: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    review: Mapped["Review"] = relationship(back_populates="embedding")


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    overall_sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    date_range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    top_keywords: Mapped[list] = mapped_column(JSON, default=list)
    readable_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    review_links: Mapped[list["ReviewTheme"]] = relationship(back_populates="theme")
    insights: Mapped[list["Insight"]] = relationship(back_populates="theme")
    quotes: Mapped[list["Quote"]] = relationship(back_populates="theme")


class ReviewTheme(Base):
    __tablename__ = "review_themes"

    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id"), primary_key=True)
    theme_id: Mapped[str] = mapped_column(String(36), ForeignKey("themes.id"), primary_key=True)
    membership_score: Mapped[float | None] = mapped_column(Float)

    review: Mapped["Review"] = relationship(back_populates="theme_links")
    theme: Mapped["Theme"] = relationship(back_populates="review_links")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    theme_id: Mapped[str] = mapped_column(String(36), ForeignKey("themes.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_review_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunity_score: Mapped[float | None] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    theme: Mapped["Theme"] = relationship(back_populates="insights")


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id"), nullable=False)
    theme_id: Mapped[str] = mapped_column(String(36), ForeignKey("themes.id"), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    is_representative: Mapped[bool] = mapped_column(Boolean, default=False)

    review: Mapped["Review"] = relationship(back_populates="quotes")
    theme: Mapped["Theme"] = relationship(back_populates="quotes")


class WeeklyPulse(Base):
    __tablename__ = "weekly_pulses"
    __table_args__ = (
        Index("ix_weekly_pulses_created_at", "created_at"),
        Index("ix_weekly_pulses_validation_passed", "validation_passed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    top_themes: Mapped[list] = mapped_column(JSON, default=list)
    quotes: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    sample_review_count: Mapped[int] = mapped_column(Integer, default=0)
    source_review_count: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    delivery_mode: Mapped[str] = mapped_column(String(50), default="dry_run")
    delivery_status: Mapped[str] = mapped_column(String(50), default="pending")
    document_id: Mapped[str | None] = mapped_column(String(255))
    document_url: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[str | None] = mapped_column(Text)
    date_range_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_range_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
