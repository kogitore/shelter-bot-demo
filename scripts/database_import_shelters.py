import asyncio
from datetime import datetime
import pandas as pd
import psycopg
import os
import requests
from math import ceil
import time
import re
from dotenv import load_dotenv

load_dotenv()
# -----------------------------------------------
# 1. 建立資料庫
# -----------------------------------------------

async def create_table():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 環境變數未設定")

    create_table_query = """
    CREATE EXTENSION IF NOT EXISTS postgis;

    CREATE TABLE IF NOT EXISTS shelters (
    id SERIAL PRIMARY KEY,
    shelter_code VARCHAR(20) UNIQUE,
    name TEXT NOT NULL,
    city TEXT,
    district TEXT,
    address TEXT,
    capacity INT,
    area_m2 NUMERIC,
    disasters TEXT[],           
    relief_station BOOLEAN,
    barrier_free BOOLEAN,
    indoor BOOLEAN,
    outdoor BOOLEAN,
    service_area TEXT,
    memo TEXT,
    geom GEOGRAPHY(POINT, 4326),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
    );
    """

    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        async with conn.cursor() as cur:
            await cur.execute(create_table_query)
            await conn.commit()
            print("shelters table created successfully")

# -----------------------------------------------
# 2. 台北市避難所 API 抓取(含快取)
#    GET https://data.taipei/api/v1/dataset/4c92dbd4-d259-495a-8390-52628119a4dd?scope=resourceAquire&limit=1000&offset=0
#    目前只有401筆資料
# -----------------------------------------------

DATA_PATH = os.path.join(os.path.dirname(__file__), "documents", "taipei_shelters.csv")
API_URL = "https://data.taipei/api/v1/dataset/4c92dbd4-d259-495a-8390-52628119a4dd"
API_PARAMS = {
    "scope": "resourceAquire",
    "resource_id": "4c92dbd4-d259-495a-8390-52628119a4dd",
    "limit": 1000,
    "offset": 0
}

def fetch_remote_data(limit=10):
    params = API_PARAMS.copy()
    params["limit"] = limit
    resp = requests.get(API_URL, params=params, timeout=15)
    data = resp.json()
    return data.get("result", {}).get("results", [])

def get_latest_import_date(records):
    dates = []
    for r in records:
        try:
            d = r.get("_importdate", {}).get("date")
            if d:
                dates.append(datetime.fromisoformat(d))
        except Exception:
            continue
    return max(dates) if dates else None

def check_update_needed():
    """檢查資料是否需要更新"""
    if not os.path.exists(DATA_PATH):
        print("📂 找不到本地 CSV，開始下載...")
        return True

    df_local = pd.read_csv(DATA_PATH)
    local_latest = pd.to_datetime(df_local["_importdate"]).max()

    online_records = fetch_remote_data(limit=10)
    remote_latest = get_latest_import_date(online_records)

    if remote_latest and remote_latest > local_latest:
        print(f"發現新版本：遠端 {remote_latest} > 本地 {local_latest}")
        return True
    else:
        print(f"資料已是最新 ({local_latest})，不需更新。")
        return False

def save_to_csv(records):
    """儲存資料到 CSV"""
    df = pd.DataFrame(records)
    df["_importdate"] = df["_importdate"].apply(lambda x: x.get("date") if isinstance(x, dict) else x)
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"💾 已儲存 {len(df)} 筆資料到 {DATA_PATH}")

def load_cached_data():
    """讀取本地 CSV"""
    if not os.path.exists(DATA_PATH):
        return []
    df = pd.read_csv(DATA_PATH)
    return df.to_dict(orient="records")

def fetch_taipei_shelters():
    """獲取台北市避難所資料（自動快取更新）"""
    if check_update_needed():
        print("📡 從 API 下載最新資料中...")
        records = fetch_remote_data(limit=1000)
        save_to_csv(records)
        return records
    else:
        print("📄 使用本地快取資料。")
        return load_cached_data()


# -----------------------------------------------
# 3. OpenStreetMap Geocoding (Nominatim)
# -----------------------------------------------

def geocode_address(row):
    """使用 OSM Nominatim 將台灣地址轉換成 (lat, lon)"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        city = row.get("縣市") or ""
        district = row.get("鄉鎮") or ""
        address = row.get("門牌地址") or ""

        # ---- 地址正規化處理 ----
        pattern = r"(.+?)([０-９0-9一二三四五六七八九十百千]+號)$"
        match = re.search(pattern, address)
        if match:
            road = match.group(1)
            number = match.group(2)
            formatted_address = f"{number}, {road.strip()}, {district}, {city}, Taiwan"
        else:
            formatted_address = f"{address}, {district}, {city}, Taiwan"

        # ---- 查詢 OSM ----
        params = {
            "q": formatted_address,
            "format": "json",
            "limit": 1,
            "countrycodes": "tw"
        }
        headers = {"User-Agent": "TaipeiShelterBot/1.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()

        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            print(f"✅ {formatted_address} → POINT({lon} {lat})")
            return lat, lon
        else:
            print(f"⚠️ Skip {formatted_address} — no coordinates found.")
            return None, None

    except Exception as e:
        formatted_address = row.get("門牌地址", "")
        print(f"⚠️ Geocode failed for {formatted_address}: {e}")
        return None, None

# ------------------------------------------------------
# 4. 批次查詢所有避難所座標並保存到 CSV
# ------------------------------------------------------

def geocode_and_save(records):
    """批次查詢所有避難所座標，間隔 0.5 秒避免被封鎖，並保存到 CSV"""
    enriched_records = []
    total_geocoded = 0
    
    for i, row in enumerate(records, 1):
        # 檢查是否已有座標資料
        if row.get("lat") and row.get("lon"):
            enriched_records.append(row)
            print(f"📍 {i}. {row.get('名稱')} → 使用已有座標 POINT({row.get('lon')} {row.get('lat')})")
        else:
            # 進行地理編碼
            lat, lon = geocode_address(row)
            if lat and lon:
                row["lat"] = lat
                row["lon"] = lon
                enriched_records.append(row)
                total_geocoded += 1
            time.sleep(0.5)  # 只有在實際查詢時才延遲
    
    print(f"\n✅ 成功取得 {len(enriched_records)} 筆座標（共 {len(records)} 筆，新查詢 {total_geocoded} 筆）")
    
    # 將包含座標的資料保存回 CSV
    if enriched_records:
        save_to_csv(enriched_records)
        print(f"💾 已更新 CSV 檔案，包含座標資訊")
    
    return enriched_records

def get_records_with_coordinates():
    """獲取包含座標的避難所資料"""
    # 檢查是否需要重新抓取 API 資料
    if check_update_needed():
        print("📡 從 API 下載最新資料中...")
        records = fetch_remote_data(limit=1000)
        # 進行地理編碼並保存
        return geocode_and_save(records)
    else:
        print("📄 使用本地快取資料。")
        cached_records = load_cached_data()
        
        # 檢查是否有資料完整性問題
        api_records = fetch_remote_data(limit=1000)
        api_count = len(api_records)
        cached_count = len(cached_records)
        
        if cached_count < api_count:
            print(f"⚠️ 快取資料不完整：本地 {cached_count} 筆 < 遠端 {api_count} 筆")
            print("📡 重新下載並處理完整資料...")
            return geocode_and_save(api_records)
        
        # 檢查快取資料中是否有缺少座標的記錄
        missing_coords = [r for r in cached_records if not (r.get("lat") and r.get("lon"))]
        if missing_coords:
            print(f"🔍 發現 {len(missing_coords)} 筆資料缺少座標，進行地理編碼...")
            return geocode_and_save(cached_records)
        else:
            print("✅ 所有資料都已包含座標")
            return cached_records

# --------------------------------------------------------
# 5. 匯入資料 (含 PostGIS)
# --------------------------------------------------------

async def insert_records(records):
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL 環境變數未設定")

    insert_query = """
        INSERT INTO shelters (
            shelter_code, name, city, district, address, capacity,
            area_m2, disasters, relief_station, barrier_free,
            indoor, outdoor, service_area, memo, geom
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                ST_GeogFromText(%s))
        ON CONFLICT (shelter_code) DO NOTHING;
    """

    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        async with conn.cursor() as cur:
            success_count = 0
            skip_count = 0
            
            for i, row in enumerate(records, start=1):
                try:
                    disasters = [name for name in ["水災", "震災", "土石流", "海嘯"]
                                if row.get(name) and row[name] != "N"]

                    lat = row.get("lat")
                    lon = row.get("lon")
                    geom_wkt = f"POINT({lon} {lat})" if lat and lon else None
                    if not geom_wkt:
                        print(f"⚠️ Skip {row.get('名稱')} — no coordinates.")
                        skip_count += 1
                        continue

                    # 處理容納人數，確保是數值
                    try:
                        capacity = int(row.get("容納人數") or 0)
                    except (ValueError, TypeError):
                        capacity = 0
                    
                    # 處理收容所面積，確保是數值
                    try:
                        area_str = str(row.get("收容所面積（平方公尺）") or "0")
                        # 移除可能的非數值文字
                        if "改建後重新評估" in area_str or area_str.strip() == "":
                            area_m2 = 0.0
                        else:
                            area_m2 = float(area_str)
                    except (ValueError, TypeError):
                        area_m2 = 0.0

                    await cur.execute(insert_query, (
                        row.get("收容所編號"),
                        row.get("名稱"),
                        row.get("縣市"),
                        row.get("鄉鎮"),
                        row.get("門牌地址"),
                        capacity,
                        area_m2,
                        disasters,
                        row.get("救濟支站") == "Y",
                        row.get("無障礙設施") == "Y",
                        row.get("室內") == "Y",
                        row.get("室外") == "Y",
                        row.get("服務里別"),
                        row.get("備考"),
                        geom_wkt
                    ))
                    print(f"✅ {i}. {row.get('名稱')} → {geom_wkt}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"⚠️ {i}. {row.get('名稱', 'Unknown')} - 插入失敗: {e}")
                    skip_count += 1
                    continue

            await conn.commit()
            print(f"🎯 成功匯入 {success_count} 筆資料，跳過 {skip_count} 筆（共 {len(records)} 筆）")

# --------------------------------------------------------
# 6. 主執行流程
# --------------------------------------------------------

if __name__ == "__main__":
    print("=== 開始執行避難所資料匯入程序 ===")
    
    try:
        # 1. 建立資料表
        print("\n步驟 1: 建立資料庫表格...")
        asyncio.run(create_table())
        
        # 2. 獲取台北市避難所資料（包含座標處理）
        print("\n步驟 2: 獲取台北市避難所資料並處理座標...")
        enriched_records = get_records_with_coordinates()
        
        if not enriched_records:
            print("❌ 沒有獲取到任何有效資料")
            exit(1)
            
        # 3. 將資料插入資料庫
        print(f"\n步驟 3: 將 {len(enriched_records)} 筆資料插入資料庫...")
        asyncio.run(insert_records(enriched_records))
        
        print("\n=== 程序執行完成 ===")
        
    except Exception as e:
        print(f"❌ 程序執行失敗: {e}")
        exit(1)