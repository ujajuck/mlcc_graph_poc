-- Bootstrap Apache AGE for the MLCC graph POC.
-- Runs once when the postgres container is initialized.

CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Two isolated named graphs - one per pipeline.
-- LightRAG's PGGraphStorage will call create_graph() itself when it first
-- initializes, but we eagerly create them here so ad-hoc Cypher sessions work
-- immediately after `docker compose up`.
SELECT create_graph('mlcc_graphify_to_lightrag')
WHERE NOT EXISTS (
    SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'mlcc_graphify_to_lightrag'
);

SELECT create_graph('mlcc_lightrag_only')
WHERE NOT EXISTS (
    SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'mlcc_lightrag_only'
);
