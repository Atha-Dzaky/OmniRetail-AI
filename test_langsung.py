import os
from dotenv import load_dotenv

# Paksa baca file .env
load_dotenv(override=True)

print("1. Cek Environment Variables:")
db_url = os.getenv("DATABASE_URL")
google_key = os.getenv("GOOGLE_API_KEY")

print(f"   - DATABASE_URL: {db_url}")
# Cek apakah Google API Key benar-benar terisi dan bukan karakter aneh
print(f"   - GOOGLE_API_KEY: {google_key[:10] if google_key else 'KOSONG!!!'}...") 

print("\n2. Mencoba memanggil LangGraph secara langsung...")
try:
    from app.graph import create_omniretail_graph
    
    # Inisialisasi graph
    graph_app = create_omniretail_graph().compile()
    
    # Tes dengan pertanyaan sederhana
    query = "Sebutkan 5 produk dengan stok terbanyak."
    print(f"   Menjalankan query: {query}")
    
    result = graph_app.invoke({"user_query": query})
    
    print("\n✅ HASIL SUKSES:")
    print(f"   SQL Result: {result.get('sql_result', 'Tidak ada')}")
    print(f"   Chart Path: {result.get('chart_path', 'Tidak ada')}")
    print(f"   Response: {result.get('final_response', 'Tidak ada')}")

except Exception as e:
    print("\n❌ ERROR DITEMUKAN!")
    import traceback
    traceback.print_exc() # Ini akan memunculkan error aslinya!