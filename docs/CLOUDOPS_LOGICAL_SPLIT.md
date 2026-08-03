# CloudOps Logical Split

1. Source ledgers: append-only proof, authority, provenance, incidents and rollback.
2. Operational state: small typed tables with TTL and exact owner.
3. Read models: derived dashboards only; never authoritative.
4. Archive: superseded tabs and experiments, preserved read-only.

The existing 220-tab workbook remains the lineage carrier. New operational logic must use the consolidated state register rather than adding more DB_* tabs.
