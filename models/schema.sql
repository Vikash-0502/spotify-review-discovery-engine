-- Review Discovery Engine — SQL schema reference
-- Generated in Phase 1; tables are created via SQLAlchemy (scripts/init_db.py)

-- raw_reviews: unmodified collector output
-- reviews: cleaned, anonymized, normalized records
-- review_embeddings: semantic search index
-- themes: clustered feedback groups
-- review_themes: many-to-many review ↔ theme
-- insights: structured product discovery outputs
-- quotes: representative verbatim excerpts

-- See models/schema.py for authoritative ORM definitions.
