# Redesigned Balance Page for BudgetBuddy
# Uses only Python + Streamlit + light CSS

import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt

# --- Styling Injection ---
st.markdown("""
<style>
    body {
        background-color: #0e1117;
        color: white;
        font-family: 'Segoe UI', sans-serif;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- MongoDB Setup ---
connection_string = st.secrets["connection"]
client = MongoClient(connection_string)
db = client.Finances
users_collection = db.users
logs = db.logs

# --- User Session ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
user = users_collection.find_one({"username": st.session_state.logged_in})
if not user:
    st.error("User not found. Please log in again.")
    st.stop()

# --- Balance Card ---
balance = round(user.get("balance", 0), 2)
color = "green" if balance > 0 else "red" if balance < 0 else "white"
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown(f'<div style="color: {color}; text-align: center; font-size: 4rem;"> ${balance}  </div>', unsafe_allow_html=True)

# --- Mode Toggle ---
view_expenses = st.toggle("Income/Expenses", value=True)
type_filter = "Expense" if view_expenses else "Income"

# --- Data Fetch + Visualization ---
data = logs.find({"type": type_filter, "user": st.session_state.logged_in})
df = pd.DataFrame(list(data))
if df.empty:
    st.warning("No transactions found. Add some to get started!")
    st.stop()

category_sum = df.groupby("category")["amount"].sum()
fig, ax = plt.subplots()
ax.pie(category_sum, labels=category_sum.index, autopct='%1.1f%%', startangle=90, textprops={'color': 'white'})
fig.patch.set_facecolor('#0e1117')
ax.set_facecolor('#0e1117')
ax.axis('equal')

# --- Visualization ---
with st.container():
    colA, colB = st.columns([2, 1])
    with colA:
        st.subheader(f"{type_filter} Breakdown")
        st.pyplot(fig, use_container_width=True)
    with colB:
        st.metric(f"Total {type_filter}s", f"${df['amount'].sum():.2f}")
        st.dataframe(category_sum.reset_index(), use_container_width=True, hide_index = True)

# --- Download Summary ---
with st.expander("📂 Download Transaction Summary"):
    time_frame = st.radio("Time Frame:", ["Week", "Month", "Year"])
    days = {"Week": 7, "Month": 31, "Year": 365}.get(time_frame, 7)
    start_date = datetime.now() - timedelta(days=days)
    end_date = datetime.now()

    categories = st.multiselect("Categories:", df["category"].unique().tolist(), default=df["category"].unique().tolist())
    if not categories:
        st.info("Select at least one category to download.")
    else:
        pipeline = [
            {"$addFields": {"date_obj": {"$dateFromString": {"dateString": "$date", "format": "%m/%d/%Y"}}}},
            {"$match": {
                "user": st.session_state.logged_in,
                "date_obj": {"$gte": start_date, "$lte": end_date},
                "category": {"$in": categories}
            }}
        ]
        filtered = logs.aggregate(pipeline)
        df_filtered = pd.DataFrame(list(filtered))
        if not df_filtered.empty:
            df_filtered.drop(columns=["_id", "user", "date_obj"], errors="ignore", inplace=True)
            st.download_button("Download CSV", df_filtered.to_csv(index=False).encode("utf-8"), "Transaction_Summary.csv")
        else:
            st.info("No matching transactions found.")

# --- Budget Status ---
budget_info = user.get("balance_info", {})
if budget_info.get("active"):
    budget = float(budget_info.get("budget", 0))
    duration = budget_info.get("duration", "Month")
    days = {"Week": 7, "Month": 31, "Year": 365}.get(duration, 31)
    start = datetime.now() - timedelta(days=days)
    pipeline = [
        {"$addFields": {"date_obj": {"$dateFromString": {"dateString": "$date", "format": "%m/%d/%Y"}}}},
        {"$match": {"user": st.session_state.logged_in, "type": "Expense", "date_obj": {"$gte": start}}}
    ]
    df_budget = pd.DataFrame(list(logs.aggregate(pipeline)))
    spent = df_budget["amount"].sum() if not df_budget.empty else 0
    if spent > budget:
        st.error(f"🚨 You exceeded your {duration.lower()}ly budget of \${budget:.2f} by spending \${spent:.2f}!")
    else:
        st.success(f"✅ You're within your {duration.lower()}ly budget of \${budget:.2f}. You've spent \${spent:.2f}.")

# --- Financial Tips ---
st.markdown("""
---
### 💡 Smart Budgeting Tips for Teens
- Track income and expenses weekly
- Set both short-term and long-term financial goals
- Follow the 50/30/20 rule for spending
- Build an emergency savings buffer
- Avoid impulse spending — sleep on it!
""")
