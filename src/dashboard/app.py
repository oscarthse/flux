import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.flux_api.dependencies import get_db_connection
from src.flux_api.routers.analytics import get_daily_sales, get_inventory_recommendations

st.set_page_config(page_title="Flux Dashboard", layout="wide")

st.title("⚡ Flux: Restaurant Analytics")

# Sidebar
st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to", ["Executive Summary", "Inventory Optimization", "Sales Deep Dive"])

# Database Connection
db_gen = get_db_connection()
db = next(db_gen)

if page == "Executive Summary":
    st.header("Executive Summary")

    # Metrics
    sales_data = get_daily_sales(db)
    df_sales = pd.DataFrame(sales_data)

    if not df_sales.empty:
        total_revenue = float(df_sales['revenue'].sum())
        total_orders = float(df_sales['quantity'].sum())

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"€{total_revenue:,.2f}")
        col2.metric("Total Items Sold", f"{total_orders:,.0f}")
        col3.metric("FluxSharpe Score", "85.2", "Good") # Placeholder or aggregate

        # Sales Chart
        st.subheader("Revenue Trend")
        df_daily = df_sales.groupby('date')['revenue'].sum().reset_index()
        fig = px.line(df_daily, x='date', y='revenue', title="Daily Revenue")
        st.plotly_chart(fig, use_container_width=True)

elif page == "Inventory Optimization":
    st.header("Inventory Optimization (Newsvendor Model)")

    st.info("This module analyzes forecast demand vs. volatility to recommend optimal Par Levels.")

    recs = get_inventory_recommendations(db)
    df_recs = pd.DataFrame(recs)

    if not df_recs.empty:
        # High Impact Recommendations
        st.subheader("🚨 High Priority Actions")
        high_impact = df_recs[df_recs['flux_sharpe'] < 50]
        if not high_impact.empty:
            st.dataframe(high_impact)
        else:
            st.success("All inventory levels are optimized!")

        # Full Table
        st.subheader("All Ingredients")
        st.dataframe(df_recs.style.applymap(
            lambda x: 'color: red' if x == 'Increase' else 'color: green' if x == 'Decrease' else '',
            subset=['action']
        ))

        # Scatter Plot
        st.subheader("Efficiency Frontier")
        fig = px.scatter(df_recs, x="flux_sharpe", y="optimal_par",
                        size="current_par", color="action", hover_name="ingredient",
                        title="FluxSharpe Score vs Optimal Par")
        st.plotly_chart(fig, use_container_width=True)

elif page == "Sales Deep Dive":
    st.header("Sales Deep Dive")
    sales_data = get_daily_sales(db)
    df_sales = pd.DataFrame(sales_data)

    if not df_sales.empty:
        # Top Items
        st.subheader("Top Selling Items")
        top_items = df_sales.groupby('item_name')['quantity'].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_items)
