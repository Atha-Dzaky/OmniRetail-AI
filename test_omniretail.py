import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/graph/query"

# 5 Test Cases yang akan kita tembakkan ke backend
test_cases = [
    {
        "name": "Tes 1: Multi-Table Join & Grouped Bar Chart",
        "query": "Tampilkan 5 produk dengan stok paling sedikit di tabel products, lalu bandingkan dengan total quantity penjualan produk-produk tersebut di tabel sales_transactions. Buatkan grafik batang yang berdampingan (grouped bar chart)."
    },
    {
        "name": "Tes 2: Time Series & Line Chart",
        "query": "Bagaimana tren total penjualan (total_amount) platform Amazon dari bulan Maret sampai Mei 2022? Buatkan grafik garis (line chart) agar mudah dilihat trennya."
    },
    {
        "name": "Tes 3: Persentase & Pie Chart",
        "query": "Hitung persentase distribusi kuantitas penjualan berdasarkan kategori ukuran (Size) untuk platform International. Buatkan grafik pie chart."
    },
    {
        "name": "Tes 4: Out of Context (Jebakan)",
        "query": "Buatkan grafik makanan favorit kucing di bulan Mei."
    },
    {
        "name": "Tes 5: Cross-Table Analysis (Pendapatan vs Biaya)",
        "query": "Hitung total pendapatan (total_amount) dari platform Amazon dan total biaya (amount) dari tabel expenses. Lalu, buatkan grafik batang yang membandingkan total pendapatan dan total biaya tersebut."
    }
]

def run_tests():
    print("=" * 60)
    print("🚀 MEMULAI AUTOMATED TESTING UNTUK OMNIRETAIL AI (GEMINI) 🚀")
    print("=" * 60)

    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n⏳ [{i}/{len(test_cases)}] Menjalankan: {test['name']}")
        print(f"   Query: {test['query'][:60]}...")
        
        start_time = time.time()
        
        try:
            # Kirim request ke backend FastAPI
            response = requests.post(
                BASE_URL, 
                json={"query": test["query"]},
                timeout=120  # Timeout 2 menit karena LLM butuh mikir
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                final_response = result.get('final_response', '')
                chart_path = result.get('chart_path', '')

                # Tes 4 khusus: harusnya kembalikan pesan "tidak ada data"
                if i == 4:
                    if "maaf" in final_response.lower() or "tidak" in final_response.lower():
                        print(f"   ✅ STATUS: SUCCESS — Correctly rejected out-of-context query")
                    else:
                        print(f"   ⚠️  STATUS: UNEXPECTED — Seharusnya ditolak tapi malah diproses")
                else:
                    print(f"   ✅ STATUS: SUCCESS (200 OK)")
                    print(f"   📊 Chart Path: {chart_path if chart_path else 'Tidak Ada'}")

                print(f"   ⏱️  Waktu Eksekusi: {elapsed_time:.2f} detik")
                print(f"   💬 Final Response: {final_response[:120]}...")
                passed += 1
            else:
                print(f"   ❌ STATUS: FAILED ({response.status_code})")
                print(f"   Error: {response.text[:200]}")
                failed += 1
                
        except requests.exceptions.Timeout:
            elapsed_time = time.time() - start_time
            print(f"   ⏰ TIMEOUT: Backend butuh waktu lebih dari 120 detik! ({elapsed_time:.0f}s)")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {str(e)}")
            failed += 1
            
        print("-" * 60)
        
        # Jeda antar test agar tidak kena rate limit API
        if i < len(test_cases):
            print(f"   ⏸️  Jeda 3 detik sebelum tes berikutnya...")
            time.sleep(3)

    print(f"\n{'=' * 60}")
    print(f"📋 HASIL AKHIR: {passed} Passed / {failed} Failed / {len(test_cases)} Total")
    print(f"🎉 TESTING SELESAI! Cek folder 'charts/' untuk melihat grafik yang berhasil dibuat.")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    run_tests()
