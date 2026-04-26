-- pgvector is used by LightRAG's PGVectorStorage for chunk + entity embeddings.
-- The apache/age image is built on postgres but does not ship pgvector, so
-- LightRAG still works without it if vector_storage is routed to a different
-- backend (e.g. NanoVectorDB). This script is safe to keep: the CREATE is
-- guarded, and failures are tolerated by initdb's continue-on-error convention
-- when pgvector is absent.

DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION WHEN undefined_file THEN
        RAISE NOTICE 'pgvector not installed in this image - skipping. '
                     'Use a postgres image with pgvector, or set '
                     'LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage in .env.';
    END;
END
$$;
