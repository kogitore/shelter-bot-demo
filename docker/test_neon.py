"""測試 Neon 資料庫連線"""
import os
import psycopg2

# 從環境變數讀取資料庫連線字串
db_url = os.getenv('DATABASE_URL', 'postgresql://user:password@host:5432/database?sslmode=require')

try:
    print("正在連線 Neon 資料庫...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # 檢查 PostGIS 擴充
    cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'postgis')")
    has_postgis = cursor.fetchone()[0]
    print(f'PostGIS 擴充: {"✅ 已安裝" if has_postgis else "❌ 未安裝"}')

    # 檢查 shelters 表
    cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'shelters')")
    has_shelters = cursor.fetchone()[0]
    print(f'shelters 表: {"✅ 存在" if has_shelters else "❌ 不存在"}')

    # 檢查 find_nearby_shelters 函數
    cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'find_nearby_shelters')")
    has_function = cursor.fetchone()[0]
    print(f'find_nearby_shelters 函數: {"✅ 存在" if has_function else "❌ 不存在"}')

    if has_shelters:
        # 檢查資料筆數
        cursor.execute('SELECT COUNT(*) FROM shelters')
        count = cursor.fetchone()[0]
        print(f'避難所資料筆數: {count}')

        # 測試查詢功能
        if has_function and count > 0:
            print("\n測試 find_nearby_shelters 函數...")
            # 台北市政府座標
            cursor.execute("SELECT * FROM find_nearby_shelters(25.0408, 121.5678, 10, 3)")
            results = cursor.fetchall()
            print(f"查詢結果: 找到 {len(results)} 個避難所")
            if results:
                print(f"最近的避難所: {results[0][1]}")  # name 欄位

    cursor.close()
    conn.close()
    print('\n✅ Neon 資料庫連線成功！')

except Exception as e:
    print(f'❌ 錯誤: {e}')
    import traceback
    traceback.print_exc()
