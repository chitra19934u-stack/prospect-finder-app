# app.py

import streamlit as st
import pandas as pd
import requests
import math
from io import BytesIO

st.set_page_config(page_title="Prospect Finder", layout="wide")
st.title("Prospect Finder App")

# -------------------------
# Upload customer file
# -------------------------

uploaded_file = st.file_uploader("Upload Customer Excel File", type=["xlsx"])

if uploaded_file:

    CustomerList_df = pd.read_excel(uploaded_file)

    st.success(f"Uploaded {len(CustomerList_df)} customers successfully!")

    # -------------------------
    # Google API Key
    # -------------------------

    api_key = st.secrets["GOOGLE_API_KEY"]

    st.info("Processing prospects... This may take a few moments.")

    # -------------------------
    # Haversine distance
    # -------------------------

    def haversine_m(lat1, lon1, lat2, lon2):

        R = 6371

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c * 1000

    # -------------------------
    # Google Places API
    # -------------------------

    def get_nearby_shops(api_key, lat, lon, radius=5000):

        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

        params = {
            "location": f"{lat},{lon}",
            "radius": radius,
            "keyword": "supermarket|grocery|store|market|hypermarket",
            "key": api_key,
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            st.error(f"Google API error: {response.status_code}")
            return []

        return response.json().get("results", [])

    # -------------------------
    # Find prospects
    # -------------------------

    def find_prospects(api_key, df):

        all_shops = []

        for _, row in df.iterrows():

            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
            except:
                continue

            shops = get_nearby_shops(api_key, lat, lon)

            for shop in shops:

                name = shop.get("name", "")
                types = [t.lower() for t in shop.get("types", [])]

                shop_lat = shop["geometry"]["location"]["lat"]
                shop_lon = shop["geometry"]["location"]["lng"]

                address = shop.get("vicinity", "")

                all_shops.append(
                    {
                        "Shop Name": name,
                        "Address": address,
                        "Category": ", ".join(types),
                        "Shop Latitude": shop_lat,
                        "Shop Longitude": shop_lon,
                        "Google Maps Link": f"https://www.google.com/maps?q={shop_lat},{shop_lon}",
                    }
                )

        return pd.DataFrame(all_shops)

    # -------------------------
    # Remove duplicate shops
    # -------------------------

    def deduplicate(df):

        if df.empty:
            return df

        df["lat_round"] = df["Shop Latitude"].round(5)
        df["lon_round"] = df["Shop Longitude"].round(5)

        df = df.drop_duplicates(subset=["lat_round", "lon_round"])

        return df.drop(columns=["lat_round", "lon_round"])

    # -------------------------
    # Identify nearest customer
    # -------------------------

    def mark_existing_customers(shops, customers):

        if shops.empty:
            return shops

        nearby_customer_codes = []
        nearby_customer_names = []
        nearby_customer_lat = []
        nearby_customer_lon = []
        distance_to_nearby_customer = []
        is_customer_flags = []

        for _, shop in shops.iterrows():

            shop_lat = shop["Shop Latitude"]
            shop_lon = shop["Shop Longitude"]

            flag = "No"
            min_dist = None

            nearest_code = None
            nearest_name = None
            nearest_lat = None
            nearest_lon = None

            for _, cust in customers.iterrows():

                cust_lat = cust["Latitude"]
                cust_lon = cust["Longitude"]

                dist = haversine_m(shop_lat, shop_lon, cust_lat, cust_lon)

                if dist <= 200:
                    flag = "Yes"

                if min_dist is None or dist < min_dist:

                    min_dist = dist
                    nearest_code = cust.get("customercode", "")
                    nearest_name = cust.get("customername", "")
                    nearest_lat = cust_lat
                    nearest_lon = cust_lon

            nearby_customer_codes.append(nearest_code)
            nearby_customer_names.append(nearest_name)
            nearby_customer_lat.append(nearest_lat)
            nearby_customer_lon.append(nearest_lon)

            distance_to_nearby_customer.append(round(min_dist, 2) if min_dist else None)

            is_customer_flags.append(flag)

        shops["Nearby Customer Code"] = nearby_customer_codes
        shops["Nearby Customer Name"] = nearby_customer_names
        shops["Nearby Customer Latitude"] = nearby_customer_lat
        shops["Nearby Customer Longitude"] = nearby_customer_lon
        shops["Distance to Nearby Customer (m)"] = distance_to_nearby_customer
        shops["Is Customer"] = is_customer_flags

        return shops

    # -------------------------
    # Run full workflow
    # -------------------------

    prospects_df = find_prospects(api_key, CustomerList_df)

    if not prospects_df.empty:

        prospects_df = deduplicate(prospects_df)

        prospects_df = mark_existing_customers(
            prospects_df, CustomerList_df
        )

    # -------------------------
    # Final Column Order
    # -------------------------

    final_columns = [
        "Shop Name",
        "Address",
        "Category",
        "Shop Latitude",
        "Shop Longitude",
        "Google Maps Link",
        "Nearby Customer Code",
        "Nearby Customer Name",
        "Nearby Customer Latitude",
        "Nearby Customer Longitude",
        "Distance to Nearby Customer (m)",
        "Is Customer",
    ]

    prospects_df = prospects_df[final_columns]

    # -------------------------
    # Display Results
    # -------------------------

    st.success(f"Found {len(prospects_df)} prospects!")

    st.dataframe(prospects_df)

    # -------------------------
    # Excel Download
    # -------------------------

    output = BytesIO()

    prospects_df.to_excel(output, index=False)

    st.download_button(
        label="Download Prospects Excel",
        data=output,
        file_name="Prospects.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )