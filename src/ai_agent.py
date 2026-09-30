import re

import pandas as pd
import streamlit as st

from src.cortex import cortex_complete
from src.db import get_schema_context, run_query, run_query_df

_SYSTEM_PROMPT = f"""You are a SQL assistant for a Postgres SaaS analytics database.

{get_schema_context()}

Rules:
- Write PostgreSQL-compatible SQL only.
- NEVER use 'cancelled'; the correct status is 'churned'.
- Always use round((expr)::numeric, 2) for rounding.
- Use %(name)s for parameterized values (but you won't have runtime params, so use literals).
- Return ONLY the SQL query, no explanation, no markdown fences.
- For read queries (SELECT), return just the SQL.
- For write queries (INSERT/UPDATE/DELETE/DROP/ALTER/CREATE), prefix with exactly: -- WRITE_QUERY
- Limit results to 100 rows unless the user asks for more.

Example:
User: What is the total MRR by plan?
Assistant: SELECT p.plan_name, round(sum(s.mrr)::numeric, 2) AS total_mrr FROM subscriptions s JOIN plans p ON p.plan_id = s.plan_id WHERE s.status = 'active' GROUP BY p.plan_name ORDER BY total_mrr DESC
"""

_EXAMPLES = [
    "What is the total MRR?",
    "Which countries have the highest churn rate?",
    "Show me the top 10 customers by MRR",
    "How many active subscriptions per plan?",
    "Monthly revenue trend for the last 6 months",
]


def _extract_sql(text: str) -> str | None:
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    lines = [ln for ln in text.strip().splitlines() if not ln.startswith("--") or ln.startswith("-- WRITE")]
    cleaned = "\n".join(lines).strip()
    if cleaned.upper().startswith(("SELECT", "WITH", "-- WRITE")):
        return cleaned
    return None


def _is_write(sql: str) -> bool:
    return sql.lstrip().startswith("-- WRITE_QUERY")


def show():
    st.header("AI Agent")
    st.caption("Ask questions about your SaaS data in plain English.")

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []

    clicked_example = None
    cols = st.columns(len(_EXAMPLES))
    for i, ex in enumerate(_EXAMPLES):
        if cols[i].button(ex, key=f"ex_{i}"):
            clicked_example = ex

    question = st.chat_input("Ask a question about your data...") or clicked_example

    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "df" in msg:
                st.dataframe(msg["df"], hide_index=True, width="stretch")

    if question:
        st.session_state.agent_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                history = "\n".join(
                    f"{m['role'].title()}: {m['content']}"
                    for m in st.session_state.agent_messages[-6:]
                )
                prompt = f"{_SYSTEM_PROMPT}\n\nConversation:\n{history}\n\nAssistant:"
                response = cortex_complete(prompt)

            sql = _extract_sql(response)
            if not sql:
                st.markdown(response)
                st.session_state.agent_messages.append({"role": "assistant", "content": response})
            elif _is_write(sql):
                clean_sql = sql.replace("-- WRITE_QUERY", "").strip()
                st.warning("This is a write query. Review before executing:")
                st.code(clean_sql, language="sql")
                st.session_state.agent_messages.append(
                    {"role": "assistant", "content": f"Write query proposed:\n```sql\n{clean_sql}\n```"}
                )
                if st.button("Confirm and execute", key="confirm_write"):
                    try:
                        run_query(clean_sql)
                        st.success("Executed successfully.")
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.code(sql, language="sql")
                try:
                    df = run_query_df(sql)
                    if df.empty:
                        st.info("Query returned no rows.")
                        st.session_state.agent_messages.append(
                            {"role": "assistant", "content": f"```sql\n{sql}\n```\n_No rows returned._"}
                        )
                    else:
                        st.dataframe(df, hide_index=True, width="stretch")
                        st.session_state.agent_messages.append(
                            {"role": "assistant", "content": f"```sql\n{sql}\n```", "df": df}
                        )
                except Exception as e:
                    st.error(f"Query error: {e}")
                    st.session_state.agent_messages.append(
                        {"role": "assistant", "content": f"Query error: {e}"}
                    )
        st.rerun()
