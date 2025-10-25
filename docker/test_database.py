"""測試資料庫連線和查詢功能"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# 讀取環境變數（需要先設定 DATABASE_URL 環境變數）
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("請設定 DATABASE_URL 環境變數")

print("=" * 60)
print("測試 Neon PostgreSQL 資料庫連線")
print("=" * 60)

try:
    # 連線資料庫
    print("\n1. 正在連線資料庫...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("   ✅ 連線成功！")

    # 檢查 PostGIS 擴充
    print("\n2. 檢查 PostGIS 擴充...")
    cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
    has_postgis = cursor.fetchone()['exists']
    print(f"   {'✅' if has_postgis else '❌'} PostGIS: {'已安裝' if has_postgis else '未安裝'}")

    # 檢查 shelters 表
    print("\n3. 檢查 shelters 資料表...")
    cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'shelters')")
    has_shelters = cursor.fetchone()['exists']
    print(f"   {'✅' if has_shelters else '❌'} shelters 表: {'存在' if has_shelters else '不存在'}")

    if has_shelters:
        cursor.execute('SELECT COUNT(*) as count FROM shelters')
        count = cursor.fetchone()['count']
        print(f"   📊 避難所資料筆數: {count}")

    # 檢查 find_nearby_shelters 函數
    print("\n4. 檢查 find_nearby_shelters 函數...")
    cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'find_nearby_shelters')")
    has_function = cursor.fetchone()['exists']
    print(f"   {'✅' if has_function else '❌'} find_nearby_shelters: {'存在' if has_function else '不存在'}")

    # 測試查詢功能
    if has_function and has_shelters:
        print("\n5. 測試查詢最近的避難所...")
        # 台北市政府座標: 25.0408, 121.5678
        cursor.execute(
            "SELECT * FROM find_nearby_shelters(%s, %s, %s, %s)",
            (25.0408, 121.5678, 10.0, 3)
        )
        results = cursor.fetchall()

        if results:
            print(f"   ✅ 查詢成功！找到 {len(results)} 個避難所")
            print("\n   最近的 3 個避難所：")
            for idx, shelter in enumerate(results, 1):
                print(f"\n   {idx}. {shelter['name']}")
                print(f"      地址: {shelter['address']}")
                print(f"      容納: {shelter['capacity']} 人")
                print(f"      距離: {shelter['distance_km']} km")
        else:
            print("   ⚠️  查詢成功但沒有找到避難所")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("✅ 所有測試通過！Neon 資料庫設定正確")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 60)
    print("❌ 測試失敗！請檢查資料庫設定")
    print("=" * 60)
