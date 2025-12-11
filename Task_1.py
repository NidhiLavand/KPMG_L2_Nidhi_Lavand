import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import datetime

# ---------------------------------------------------------
# 1. CONFIGURATION & PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(layout="wide", page_title="US Trade & Tariff Tracker")

st.title("US Trade Monitor: Tariffs & Trade Deficits")
st.markdown("""
This dashboard visualizes **US Trade Deficits** (live data from US Census Bureau) 
combined with **Tariff Rates**. 
\n*Hover over a country to see the trade balance and tariff details.*
""")

# ---------------------------------------------------------
# 2. DATA FETCHING FUNCTIONS
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_census_trade_data():
    """
    Fetches the latest annual Import/Export data from the US Census Bureau API.
    Uses separate endpoints for Imports and Exports and merges them.
    """
    # 1. Dynamic Year Selection (Previous Year for full dataset)
    current_year = datetime.datetime.now().year
    target_year = current_year - 1 
    
    # 2. Define Endpoints
    # We use the Harmonized System (HS) endpoint which allows country-level aggregation
    url_exports = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
    url_imports = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
    
    # 3. Define Parameters
    # CTY_CODE = Country Code, CTY_NAME = Country Name
    # ALL_VAL_YR = Total Export Value (Year to Date)
    # GEN_VAL_YR = General Import Value (Year to Date)
    
    params_exp = {
        'get': 'CTY_CODE,CTY_NAME,ALL_VAL_YR',
        'time': str(target_year)
    }
    
    params_imp = {
        'get': 'CTY_CODE,CTY_NAME,GEN_VAL_YR',
        'time': str(target_year)
    }

    try:
        # --- Fetch Exports ---
        r_exp = requests.get(url_exports, params=params_exp)
        r_exp.raise_for_status()
        data_exp = r_exp.json()
        df_exp = pd.DataFrame(data_exp[1:], columns=data_exp[0]) # Skip header row

        # --- Fetch Imports ---
        r_imp = requests.get(url_imports, params=params_imp)
        r_imp.raise_for_status()
        data_imp = r_imp.json()
        df_imp = pd.DataFrame(data_imp[1:], columns=data_imp[0])

        # --- Process & Merge ---
        # Convert values to Billions (Census returns dollars)
        df_exp['Exports'] = pd.to_numeric(df_exp['ALL_VAL_YR']) / 1_000_000_000
        df_imp['Imports'] = pd.to_numeric(df_imp['GEN_VAL_YR']) / 1_000_000_000
        
        # Merge on Country Code (CTY_CODE is safer than Name)
        df_merged = pd.merge(df_exp[['CTY_CODE', 'CTY_NAME', 'Exports']], 
                             df_imp[['CTY_CODE', 'Imports']], 
                             on='CTY_CODE', 
                             how='outer')
        
        # Fill NaN with 0
        df_merged.fillna(0, inplace=True)

        # Calculate Balance
        df_merged['US Trade Balance ($B)'] = df_merged['Exports'] - df_merged['Imports']
        
        # Clean up Country Names (Census names are ALL CAPS)
        df_merged['Country Name'] = df_merged['CTY_NAME'].str.title()
        
        # Fix specific names to match Plotly/Standard ISO mapping
        name_fixes = {
            'Korea, South': 'South Korea',
            'United Kingdom': 'United Kingdom',
            'China': 'China',
            'Russian Federation': 'Russia',
            'Vietnam': 'Vietnam',
            'Germany': 'Germany'
        }
        df_merged['Country Name'] = df_merged['Country Name'].replace(name_fixes)
        
        return df_merged

    except Exception as e:
        st.error(f"Error fetching data from Census Bureau: {e}")
        return pd.DataFrame()

def get_tariff_data():
    """
    Returns a DataFrame of Tariff policies. 
    (Static data for demo purposes - update this list as policies change)
    """
    data = {
        'Country Name': ['Canada', 'Mexico', 'China', 'Germany', 'France', 'United Kingdom', 'India', 'Japan', 'South Korea', 'Brazil', 'Vietnam', 'Russia', 'Australia'],
        'Tariff Rate (%)': [0.0, 0.0, 19.3, 2.4, 2.6, 2.5, 3.2, 0.0, 0.0, 3.5, 2.8, 35.0, 0.0],
        'Category': ['FTA Partner', 'FTA Partner', 'Trade War', 'Normal Trade', 'Normal Trade', 'Normal Trade', 'Normal Trade', 'FTA Partner', 'FTA Partner', 'Normal Trade', 'Normal Trade', 'Sanctioned', 'FTA Partner'],
        'ISO_ALPHA_3': ['CAN', 'MEX', 'CHN', 'DEU', 'FRA', 'GBR', 'IND', 'JPN', 'KOR', 'BRA', 'VNM', 'RUS', 'AUS']
    }
    return pd.DataFrame(data)

# ---------------------------------------------------------
# 3. MAIN APPLICATION LOGIC
# ---------------------------------------------------------

# Load Data
with st.spinner('Fetching latest trade data from US Census Bureau...'):
    df_trade = get_census_trade_data()
    df_tariff = get_tariff_data()

if not df_trade.empty:
    # Merge Trade Data (Real-time) with Tariff Data (Static Policy)
    # We merge on 'Country Name' for this simple demo. 
    # (In production, using ISO codes for everything is more robust)
    
    merged_df = pd.merge(df_tariff, df_trade, on="Country Name", how="left")
    
    # Handle missing trade data for countries in our tariff list
    merged_df['US Trade Balance ($B)'] = merged_df['US Trade Balance ($B)'].fillna(0)
    merged_df['Exports'] = merged_df['Exports'].fillna(0)
    merged_df['Imports'] = merged_df['Imports'].fillna(0)

    # ---------------------------------------------------------
    # 4. PLOTLY MAP
    # ---------------------------------------------------------
    fig = px.choropleth(
        merged_df,
        locations="ISO_ALPHA_3",
        color="Tariff Rate (%)",
        hover_name="Country Name",
        color_continuous_scale=px.colors.sequential.Reds,
        projection="natural earth",
        title=f"<b>US Tariffs vs Trade Balance ({datetime.datetime.now().year - 1})</b>",
        hover_data={
            "ISO_ALPHA_3": False,
            "Category": True,
            "Tariff Rate (%)": ":.1f",
            "US Trade Balance ($B)": ":+$.2f", # Format: +$10.50 or -$20.00
            "Exports": ":$.1f",
            "Imports": ":$.1f"
        }
    )

    fig.update_layout(
        margin={"r":0,"t":40,"l":0,"b":0},
        height=600,
        geo=dict(
            showframe=False,
            showcoastlines=True,
            bgcolor='rgba(0,0,0,0)'
        ),
        coloraxis_colorbar=dict(
            title="Tariff Rate",
            ticksuffix="%"
        )
    )

    # Display in Streamlit
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------
    # 5. DATA TABLE
    # ---------------------------------------------------------
    with st.expander("📊 View Detailed Data Table"):
        display_cols = ['Country Name', 'Category', 'Tariff Rate (%)', 'US Trade Balance ($B)', 'Exports', 'Imports']
        st.dataframe(merged_df[display_cols].style.format({
            "Tariff Rate (%)": "{:.1f}%",
            "US Trade Balance ($B)": "${:+,.2f}B",
            "Exports": "${:,.2f}B",
            "Imports": "${:,.2f}B"
        }))

else:
    st.warning("Data currently unavailable. The Census API might be down or rate-limited.")