from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from typing import Optional, List
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

df = pd.read_csv("unoosa_registry.csv")

@app.get("/api/objects")
def get_objects(
    search: Optional[str] = None,
    country: Optional[str] = None,
    function: Optional[str] = None,
    apogee_min: Optional[float] = None,
    apogee_max: Optional[float] = None,
    perigee_min: Optional[float] = None,
    perigee_max: Optional[float] = None,
    inclination_min: Optional[float] = None,
    inclination_max: Optional[float] = None,
    skip: int = 0,
    limit: int = 100,
):
    result = df.copy()
    
    print(f"DEBUG: country={country}, function={function}, search={search}")
    
    if search and search.strip():
        result = result[
            result["Registration Number"].str.contains(search, case=False, na=False) |
            result["Object Name"].str.contains(search, case=False, na=False)
        ]
    
    if country and country.strip():
        print(f"DEBUG: Filtering by country: '{country.strip()}'")
        print(f"DEBUG: Available countries: {result['Country of Origin'].unique()[:5]}")
        result = result[result["Country of Origin"].str.strip() == country.strip()]
        print(f"DEBUG: After country filter: {len(result)} records")
    
    if function and function.strip():
        result = result[result["Function"].str.strip() == function.strip()]
    
    if apogee_min is not None:
        result = result[(result["Apogee (km)"].isna()) | (result["Apogee (km)"] >= apogee_min)]
    
    if apogee_max is not None:
        result = result[(result["Apogee (km)"].isna()) | (result["Apogee (km)"] <= apogee_max)]
    
    if perigee_min is not None:
        result = result[(result["Perigee (km)"].isna()) | (result["Perigee (km)"] >= perigee_min)]
    
    if perigee_max is not None:
        result = result[(result["Perigee (km)"].isna()) | (result["Perigee (km)"] <= perigee_max)]
    
    if inclination_min is not None:
        result = result[(result["Inclination (degrees)"].isna()) | (result["Inclination (degrees)"] >= inclination_min)]
    
    if inclination_max is not None:
        result = result[(result["Inclination (degrees)"].isna()) | (result["Inclination (degrees)"] <= inclination_max)]
    
    total = len(result)
    
    records = result.iloc[skip:skip+limit].to_dict(orient="records")
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": records
    }

@app.get("/api/filters")
def get_filters():
    filters_data = {
        "countries": sorted(list(set([str(x).strip() for x in df["Country of Origin"].unique() if pd.notna(x)]))),
        "functions": sorted(list(set([str(x).strip() for x in df["Function"].unique() if pd.notna(x)]))),
    }
    
    apogee_vals = df[df["Apogee (km)"].notna()]["Apogee (km)"]
    if len(apogee_vals) > 0:
        filters_data["apogee_range"] = [float(apogee_vals.min()), float(apogee_vals.max())]
    else:
        filters_data["apogee_range"] = [0, 1000]
    
    perigee_vals = df[df["Perigee (km)"].notna()]["Perigee (km)"]
    if len(perigee_vals) > 0:
        filters_data["perigee_range"] = [float(perigee_vals.min()), float(perigee_vals.max())]
    else:
        filters_data["perigee_range"] = [0, 1000]
    
    inclination_vals = df[df["Inclination (degrees)"].notna()]["Inclination (degrees)"]
    if len(inclination_vals) > 0:
        filters_data["inclination_range"] = [float(inclination_vals.min()), float(inclination_vals.max())]
    else:
        filters_data["inclination_range"] = [0, 180]
    
    return filters_data

@app.get("/api/objects/{registration_number}")
def get_object(registration_number: str):
    obj = df[df["Registration Number"] == registration_number]
    if len(obj) == 0:
        return {"error": "Not found"}
    return obj.iloc[0].to_dict()
