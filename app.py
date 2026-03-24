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
    # Hardcoded Google API Key
    # -------------------------
    api_key = st.secrets["GOOGLE_API_KEY"]  # Replace with your actual key

    st.info("Processing prospects... This may take a few moments.")

    # -------------------------
    # Haversine distance function
    # -------------------------
    def haversine_m(lat1, lon1, lat2, lon2):
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c * 1000  # meters

    # -------------------------
    # Google Places Nearby Search
    # -------------------------
    def get_nearby_shops(api_key, lat, lon, radius=5000):
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lon}",
            "radius": radius,
            "keyword": "supermarket|grocery|store|market|hypermarket",
            "key": api_key
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            st.error(f"Google API error: {response.status_code}")
            return []
        return response.json().get("results", [])

    # -------------------------
    # Find Prospects
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
                dist_customer_m = haversine_m(lat, lon, shop_lat, shop_lon)
                all_shops.append({
                    "Customer Code": row.get("customercode",""),
                    "Customer Name": row.get("customername",""),
                    "Customer Latitude": lat,
                    "Customer Longitude": lon,
                    "Shop Name": name,
                    "Address": address,
                    "Category": ", ".join(types),
                    "Distance from Customer (m)": round(dist_customer_m,2),
                    "Distance from Customer (km)": round(dist_customer_m/1000,2),
                    "Shop Latitude": shop_lat,
                    "Shop Longitude": shop_lon,
                    "Google Maps Link": f"https://www.google.com/maps?q={shop_lat},{shop_lon}"
                })
        return pd.DataFrame(all_shops)

    # -------------------------
    # Deduplicate shops
    # -------------------------
    def deduplicate(df):
        if df.empty:
            return df
        df["lat_round"] = df["Shop Latitude"].round(4)
        df["lon_round"] = df["Shop Longitude"].round(4)
        df = df.drop_duplicates(subset=["lat_round","lon_round"])
        return df.drop(columns=["lat_round","lon_round"])

    # -------------------------
    # Mark existing customers (within 200m)
    # -------------------------
    def mark_existing_customers(shops, customers):
        if shops.empty:
            return shops
        nearby_customer_codes = []
        nearby_customer_names = []
        distance_to_nearby_customer = []
        is_customer_flags = []

        for _, shop in shops.iterrows():
            shop_coord = (shop["Shop Latitude"], shop["Shop Longitude"])
            flag = "No"
            min_dist_to_any_customer = None
            nearest_code = None
            nearest_name = None
            for _, cust in customers.iterrows():
                cust_coord = (cust["Latitude"], cust["Longitude"])
                dist = haversine_m(shop_coord[0], shop_coord[1], cust_coord[0], cust_coord[1])
                if dist <= 200:
                    flag = "Yes"
                if min_dist_to_any_customer is None or dist < min_dist_to_any_customer:
                    min_dist_to_any_customer = dist
                    nearest_code = cust.get("customercode","")
                    nearest_name = cust.get("customername","")
            nearby_customer_codes.append(nearest_code)
            nearby_customer_names.append(nearest_name)
            distance_to_nearby_customer.append(round(min_dist_to_any_customer,2) if min_dist_to_any_customer else None)
            is_customer_flags.append(flag)

        shops["Nearby Customer Code"] = nearby_customer_codes
        shops["Nearby Customer Name"] = nearby_customer_names
        shops["Distance to Nearby Customer (m)"] = distance_to_nearby_customer
        shops["Is Customer"] = is_customer_flags
        return shops

    # -------------------------
    # Run full workflow
    # -------------------------
    prospects_df = find_prospects(api_key, CustomerList_df)
    if not prospects_df.empty:
        prospects_df = deduplicate(prospects_df)
        prospects_df = mark_existing_customers(prospects_df, CustomerList_df)

    # -------------------------
    # Show results
    # -------------------------
    st.success(f"Found {len(prospects_df)} prospects!")
    st.dataframe(prospects_df)

    # -------------------------
    # Excel download
    # -------------------------
    output = BytesIO()
    prospects_df.to_excel(output, index=False)
    st.download_button(
        label="Download Prospects Excel",
        data=output,
        file_name="Prospects.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )