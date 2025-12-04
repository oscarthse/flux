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
page = st.sidebar.radio("Go to", ["Executive Summary", "Inventory Optimization", "Sales Deep Dive", "Operations Performance"])

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

elif page == "Operations Performance":
    st.header("Operations Performance")

    from src.flux_api.routers.analytics import get_lost_sales_stats, get_waste_stats

    # 1. Lost Sales Analysis
    st.subheader("📉 Lost Sales Analysis")
    lost_sales_data = get_lost_sales_stats(db)
    df_lost = pd.DataFrame(lost_sales_data)

    if not df_lost.empty:
        total_lost_rev = df_lost['potential_revenue'].sum()
        lost_customers = df_lost['party_size'].sum()

        c1, c2 = st.columns(2)
        c1.metric("Total Lost Revenue", f"€{total_lost_rev:,.2f}", delta_color="inverse")
        c2.metric("Lost Customers", f"{lost_customers:,.0f}", delta_color="inverse")

        # Reason Breakdown
        st.markdown("### Reasons for Lost Sales")
        df_reason = df_lost.groupby('reason')['potential_revenue'].sum().reset_index()
        fig_reason = px.pie(df_reason, values='potential_revenue', names='reason', title="Lost Revenue by Reason")
        st.plotly_chart(fig_reason, use_container_width=True)

        # Time Series
        st.markdown("### Lost Revenue Over Time")
        df_lost['date'] = pd.to_datetime(df_lost['timestamp']).dt.date
        df_daily_lost = df_lost.groupby('date')['potential_revenue'].sum().reset_index()
        fig_lost_ts = px.bar(df_daily_lost, x='date', y='potential_revenue', title="Daily Lost Revenue")
        st.plotly_chart(fig_lost_ts, use_container_width=True)
    else:
        st.success("No lost sales recorded!")

    # 2. Waste Analysis
    st.subheader("🗑️ Food Waste Analysis")
    waste_data = get_waste_stats(db)
    df_waste = pd.DataFrame(waste_data)

    if not df_waste.empty:
        total_waste_cost = df_waste['waste_cost'].sum()

        st.metric("Total Waste Cost", f"€{total_waste_cost:,.2f}", delta_color="inverse")

        # Top Wasted Items
        st.markdown("### Top Wasted Ingredients (by Cost)")
        df_top_waste = df_waste.groupby('ingredient_name')['waste_cost'].sum().sort_values(ascending=False).head(10).reset_index()
        fig_waste = px.bar(df_top_waste, x='waste_cost', y='ingredient_name', orientation='h', title="Top 10 Ingredients by Waste Cost")
        st.plotly_chart(fig_waste, use_container_width=True)
    else:
        st.success("No waste recorded!")
