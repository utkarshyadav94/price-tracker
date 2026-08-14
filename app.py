from __future__ import annotations

import pandas as pd
import streamlit as st

from database import add_product, delete_product, get_all_products, get_latest_price, get_price_history
from tracker_engine import run_tracker_once

st.set_page_config(page_title="Price & Stock Tracker", layout="wide")


@st.cache_data(ttl=30)
def _stock_status(in_stock_value: int) -> str:
    if in_stock_value is None:
        return "Unknown"
    return "In stock" if int(in_stock_value) == 1 else "Out of stock"


def load_products() -> list[dict]:
    rows = get_all_products()
    products: list[dict] = []
    for row in rows:
        current_price, in_stock = get_latest_price(row["id"])
        products.append(
            {
                "id": row["id"],
                "url": row["url"],
                "title": row["title"] or "Untitled",
                "target_price": row["target_price"],
                "current_price": current_price,
                "in_stock": _stock_status(in_stock),
                "created_at": row["created_at"],
            }
        )
    return products


st.title("E-Commerce Price & Stock Tracker")

with st.sidebar:
    st.header("Add product")
    url = st.text_input("Product URL")
    target_price = st.number_input("Target Price", min_value=0.0, step=1.0)
    if st.button("Track Product"):
        if url:
            added = add_product(url, target_price=target_price)
            if added is not None:
                st.success("Product added successfully")
                st.cache_data.clear()
            else:
                st.error("Unable to add product. Check the URL and try again.")
        else:
            st.error("Please enter a product URL")

    if st.button("Run Manual Scrape"):
        run_tracker_once()
        st.success("Scrape run completed")

st.subheader("Tracked Products")
products = load_products()
if products:
    products_df = pd.DataFrame(products)
    if "current_price" in products_df.columns:
        products_df["current_price"] = products_df["current_price"].astype("Float64")
    st.dataframe(products_df, width="stretch")

    selected_product_id = st.selectbox("Select product to inspect", options=[p["id"] for p in products], format_func=lambda x: next(p["title"] for p in products if p["id"] == x))
    if selected_product_id is not None:
        selected = next(p for p in products if p["id"] == selected_product_id)
        if st.button("Delete Selected Product"):
            delete_product(selected_product_id)
            st.cache_data.clear()
            st.experimental_rerun()

        history = get_price_history(selected_product_id)
        if history:
            history_df = pd.DataFrame(
                [
                    {
                        "price": row["price"],
                        "in_stock": _stock_status(row["in_stock"]),
                        "timestamp": row["timestamp"],
                    }
                    for row in history
                ]
            )
            if not history_df.empty:
                history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
                st.line_chart(history_df.set_index("timestamp")["price"])
                st.dataframe(history_df, width="stretch")
        else:
            st.info("No price history yet.")
else:
    st.info("No tracked products yet.")
