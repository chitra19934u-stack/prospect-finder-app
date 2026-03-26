import streamlit as st
import pandas as pd
import requests
import math
import time
from io import BytesIO

st.set_page_config(page_title="Prospect Finder", layout="wide")
st.title("Prospect Finder App")

uploaded_file = st.file_uploader("Upload Customer Excel File", type=["xlsx"])

if uploaded_file:

    CustomerList_df = pd.read_excel(uploaded_file)
    st.success(f"{len(CustomerList_df)} customers uploaded")

    api_key = st.secrets["GOOGLE_API_KEY"]

# -----------------------------
# Distance calculation
# -----------------------------

    def haversine_m(lat1, lon1, lat2, lon2):

        R = 6371

        dlat = math.radians(lat2-lat1)
        dlon = math.radians(lon2-lon1)

        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
        c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))

        return R*c*1000

# -----------------------------
# Google Places search
# -----------------------------

    def get_nearby_shops(lat, lon):

        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

        params = {
            "location":f"{lat},{lon}",
            "radius":5000,
            "keyword":"supermarket|grocery|store|market|hypermarket",
            "key":api_key
        }

        results=[]
        response=requests.get(url,params=params).json()

        results.extend(response.get("results",[]))

        while "next_page_token" in response:

            time.sleep(2)

            params={
                "pagetoken":response["next_page_token"],
                "key":api_key
            }

            response=requests.get(url,params=params).json()
            results.extend(response.get("results",[]))

        return results

# -----------------------------
# Grid search
# -----------------------------

    def generate_grid(lat,lon,step=0.02):

        grid=[]

        for i in range(-2,3):
            for j in range(-2,3):

                grid.append((lat+i*step,lon+j*step))

        return grid

# -----------------------------
# Prospect finder
# -----------------------------

    def find_prospects(df):

        all_shops=[]

        for _,row in df.iterrows():

            try:
                lat=float(row["Latitude"])
                lon=float(row["Longitude"])
            except:
                continue

            grid_points=generate_grid(lat,lon)

            for g_lat,g_lon in grid_points:

                shops=get_nearby_shops(g_lat,g_lon)

                for shop in shops:

                    name=shop.get("name","")
                    address=shop.get("vicinity","")
                    types=[t.lower() for t in shop.get("types",[])]

                    shop_lat=shop["geometry"]["location"]["lat"]
                    shop_lon=shop["geometry"]["location"]["lng"]

                    all_shops.append({

                        "Shop Name":name,
                        "Address":address,
                        "Category":", ".join(types),
                        "Shop Latitude":shop_lat,
                        "Shop Longitude":shop_lon,
                        "Google Maps Link":f"https://www.google.com/maps?q={shop_lat},{shop_lon}"

                    })

        return pd.DataFrame(all_shops)

# -----------------------------
# Remove duplicates
# -----------------------------

    def deduplicate(df):

        df["lat_round"]=df["Shop Latitude"].round(5)
        df["lon_round"]=df["Shop Longitude"].round(5)

        df=df.drop_duplicates(subset=["lat_round","lon_round"])

        return df.drop(columns=["lat_round","lon_round"])

# -----------------------------
# Find nearest customer
# -----------------------------

    def mark_existing_customers(shops,customers):

        near_code=[]
        near_name=[]
        near_lat=[]
        near_lon=[]
        dist_list=[]
        flag_list=[]

        for _,shop in shops.iterrows():

            shop_lat=shop["Shop Latitude"]
            shop_lon=shop["Shop Longitude"]

            min_dist=None
            flag="No"

            code=None
            name=None
            lat=None
            lon=None

            for _,cust in customers.iterrows():

                cust_lat=cust["Latitude"]
                cust_lon=cust["Longitude"]

                dist=haversine_m(shop_lat,shop_lon,cust_lat,cust_lon)

                if dist<=200:
                    flag="Yes"

                if min_dist is None or dist<min_dist:

                    min_dist=dist
                    code=cust.get("customercode","")
                    name=cust.get("customername","")
                    lat=cust_lat
                    lon=cust_lon

            near_code.append(code)
            near_name.append(name)
            near_lat.append(lat)
            near_lon.append(lon)
            dist_list.append(round(min_dist,2))
            flag_list.append(flag)

        shops["Nearby Customer Code"]=near_code
        shops["Nearby Customer Name"]=near_name
        shops["Nearby Customer Latitude"]=near_lat
        shops["Nearby Customer Longitude"]=near_lon
        shops["Distance to Nearby Customer (m)"]=dist_list
        shops["Is Customer"]=flag_list

        return shops

# -----------------------------
# Arabic detection
# -----------------------------

    def contains_arabic(text):

        for char in text:
            if '\u0600' <= char <= '\u06FF':
                return True
        return False

# -----------------------------
# Translate Arabic
# -----------------------------

    def translate_arabic(text):

        url="https://translation.googleapis.com/language/translate/v2"

        params={
            "q":text,
            "target":"en",
            "key":api_key
        }

        response=requests.post(url,data=params)

        if response.status_code==200:

            translated=response.json()["data"]["translations"][0]["translatedText"]
            return translated

        return text

# -----------------------------
# Process shop names
# -----------------------------

    def process_shop_names(df):

        names=[]

        for name in df["Shop Name"]:

            if contains_arabic(name):

                translated=translate_arabic(name)
                final=f"{name} ({translated})"

            else:
                final=name

            names.append(final)

        df["Shop Name"]=names

        return df

# -----------------------------
# Remove unwanted businesses
# -----------------------------

    exclude_keywords=[

        "fruit","vegetable","butcher","meat","chicken","poultry",
        "dates",
        "lulu","nesto","carrefour",
        "baskin","coffee","cafe","costa","dunkin","tim hortons",
        "gas","petrol","station",
        "garage","repair",
        "hospital","clinic"
    ]

    def remove_unwanted(df):

        mask=[]

        for name in df["Shop Name"].str.lower():

            remove=any(word in name for word in exclude_keywords)
            mask.append(not remove)

        return df[mask]

# -----------------------------
# Run full workflow
# -----------------------------

    st.info("Searching outlets...")

    prospects_df=find_prospects(CustomerList_df)

    prospects_df=deduplicate(prospects_df)

    prospects_df=mark_existing_customers(prospects_df,CustomerList_df)

    prospects_df=prospects_df[prospects_df["Is Customer"]=="No"]

    prospects_df=process_shop_names(prospects_df)

    prospects_df=remove_unwanted(prospects_df)

# -----------------------------
# Final column order
# -----------------------------

    final_cols=[

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
        "Is Customer"

    ]

    prospects_df=prospects_df[final_cols]

# -----------------------------
# Display
# -----------------------------

    st.success(f"{len(prospects_df)} prospects found")

    st.dataframe(prospects_df)

# -----------------------------
# Map
# -----------------------------

    map_df=prospects_df.rename(
        columns={
            "Shop Latitude":"lat",
            "Shop Longitude":"lon"
        }
    )

    st.map(map_df)

# -----------------------------
# Download Excel
# -----------------------------

    output=BytesIO()

    prospects_df.to_excel(output,index=False)

    st.download_button(
        label="Download Prospects Excel",
        data=output,
        file_name="Prospects.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )