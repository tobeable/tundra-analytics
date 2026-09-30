import json

import streamlit as st

from src.cortex import cortex_embed
from src.db import run_query, run_query_df


def _embedding_to_pg_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in vec) + "]"


def show():
    st.header("Semantic Search")
    st.caption("Find accounts by meaning, not just keywords.")

    query = st.text_input("Describe the type of account you're looking for:",
                          placeholder="e.g. fast-growing healthcare companies")

    if not query:
        st.info("Enter a description above to search.")
        return

    with st.spinner("Embedding query and searching..."):
        query_vec = cortex_embed(query)
        vec_literal = _embedding_to_pg_literal(query_vec)

        results = run_query_df(
            """
            SELECT c.customer_id,
                   c.company_name,
                   c.industry,
                   c.account_tier,
                   c.description,
                   co.country_name,
                   round((1 - (ce.embedding <=> %(vec)s::vector))::numeric, 4) AS similarity
            FROM customer_embeddings ce
            JOIN customers c  ON c.customer_id  = ce.customer_id
            JOIN countries co ON co.country_code = c.country_code
            ORDER BY ce.embedding <=> %(vec)s::vector
            LIMIT 20
            """,
            {"vec": vec_literal},
        )

    if results.empty:
        st.warning("No embeddings found. Have you generated them yet?")
    else:
        st.subheader(f"Top {len(results)} matches")
        st.dataframe(results, hide_index=True, width="stretch")
