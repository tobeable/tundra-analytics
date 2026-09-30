import json
import streamlit as st
from snowflake.snowpark import Session


@st.cache_resource
def _get_session() -> Session:
    try:
        return Session.builder.configs({"connection": "default"}).create()
    except Exception:
        pass

    cfg = st.secrets["snowflake"]
    params = {
        "account": cfg["account"],
        "user": cfg["user"],
        "password": cfg["password"],
        "warehouse": cfg.get("warehouse", "COMPUTE_WH"),
        "authenticator": cfg.get("authenticator", "snowflake"),
    }
    if cfg.get("role"):
        params["role"] = cfg["role"]
    return Session.builder.configs(params).create()


def cortex_complete(prompt: str, model: str = "llama3.1-70b") -> str:
    session = _get_session()
    result = session.sql(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS response",
        params=[model, prompt],
    ).collect()
    return result[0]["RESPONSE"]


def cortex_embed(text: str) -> list[float]:
    session = _get_session()
    result = session.sql(
        "SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_1024("
        "'snowflake-arctic-embed-l-v2.0', ?) AS emb",
        params=[text],
    ).collect()
    emb = result[0]["EMB"]
    if isinstance(emb, str):
        emb = json.loads(emb)
    return emb
