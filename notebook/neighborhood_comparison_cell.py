"""
Neighborhood Comparison Tool
Compare noise profiles of two NYC neighborhoods side-by-side with year slider.
"""

import pandas as pd
import plotly.express as px
import json
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

# ==========================================
# 1. Load Neighborhoods GeoJSON
# ==========================================
print("Loading neighborhoods geojson...")
with open("NYC_Neighborhoods.geojson", "r") as f:
    nta_geojson = json.load(f)

# Build spatial index for fast point-in-polygon
nta_geoms = [shape(f["geometry"]) for f in nta_geojson["features"]]
nta_names_list = [f["properties"]["NTAName"] for f in nta_geojson["features"]]
tree = STRtree(nta_geoms)


def find_neighborhood(lat, lon):
    """Map lat/lon to neighborhood name using spatial join"""
    point = Point(lon, lat)
    idx = tree.nearest(point)
    if isinstance(idx, (int,)):
        return nta_names_list[idx] if nta_geoms[idx].contains(point) else None
    for i in idx:
        if nta_geoms[i].contains(point):
            return nta_names_list[i]
    return None


# ==========================================
# 2. Load 311 Data and Create Era Column
# ==========================================
print("Loading 311 noise complaints...")
df = pd.read_csv(
    "../data/processed/311_noise_cleaned.csv", parse_dates=["Created Date"]
)
df["Year"] = df["Created Date"].dt.year


# Create Era column
def covid_era(d):
    if d < pd.Timestamp("2020-03-01"):
        return "Pre-COVID"
    elif d < pd.Timestamp("2021-07-01"):
        return "Lockdown"
    else:
        return "Post-COVID"


df["Era"] = df["Created Date"].map(covid_era)

# ==========================================
# 3. Perform Spatial Join
# ==========================================
print("Mapping coordinates to neighborhoods (this may take a minute)...")
sample_size = min(100000, len(df))
if len(df) > sample_size:
    df_sample = df.sample(sample_size, random_state=42)
else:
    df_sample = df

df_sample["Neighborhood"] = df_sample.apply(
    lambda r: find_neighborhood(r["Latitude"], r["Longitude"]), axis=1
)
df_mapped = df_sample.dropna(subset=["Neighborhood"]).copy()
print(f"Successfully mapped {len(df_mapped)} complaints to neighborhoods")

# ==========================================
# 4. Aggregate Data by Neighborhood, Year, Era
# ==========================================
agg = (
    df_mapped.groupby(["Neighborhood", "Year", "Era"]).size().reset_index(name="Count")
)

neighborhoods = sorted(agg["Neighborhood"].unique())
years = sorted(agg["Year"].unique())
eras = ["Pre-COVID", "Lockdown", "Post-COVID"]

print(f"Found {len(neighborhoods)} neighborhoods")
print(f"Years: {years[0]} to {years[-1]}")

# ==========================================
# 5. Set Up Comparison
# ==========================================
# Find Times Square and a quiet Queens neighborhood
times_sq = [
    n for n in neighborhoods if "Times" in n or "Theater" in n or "Midtown" in n
]
queens_nb = [n for n in neighborhoods if "Forest" in n or "Hills" in n]

n1 = times_sq[0] if times_sq else neighborhoods[0]
n2 = (
    queens_nb[0]
    if queens_nb
    else (neighborhoods[1] if len(neighborhoods) > 1 else neighborhoods[0])
)

print(f"Comparing: {n1} vs {n2}")

# ==========================================
# 6. Create Interactive Comparison with Year Slider
# ==========================================
comp_df = agg[agg["Neighborhood"].isin([n1, n2])].copy()
comp_df["Neighborhood"] = pd.Categorical(comp_df["Neighborhood"], categories=[n1, n2])

fig = px.bar(
    comp_df,
    x="Era",
    y="Count",
    color="Era",
    animation_frame="Year",
    facet_col="Neighborhood",
    barmode="group",
    title=f"Noise Complaints: {n1} vs {n2}",
    color_discrete_map={
        "Pre-COVID": "#4c78a8",
        "Lockdown": "#f58518",
        "Post-COVID": "#54a24b",
    },
    height=550,
    width=1100,
    category_orders={"Era": ["Pre-COVID", "Lockdown", "Post-COVID"]},
)

# Update layout
fig.update_layout(
    showlegend=False,
    xaxis_title="Era",
    xaxis2_title="Era",
    yaxis_title="Complaints",
    margin=dict(t=80, b=50, l=50, r=50),
)

# Customize the year slider
fig.layout.sliders[0].currentvalue.prefix = "Year: "
fig.layout.sliders[0].pad.t = 30

# Save to HTML
fig.write_html("../website/neighborhood_comparison.html")
print("Saved interactive plot to ../website/neighborhood_comparison.html")
fig.show()
