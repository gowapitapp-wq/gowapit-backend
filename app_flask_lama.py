from flask import Flask, jsonify
from flask_cors import CORS 

app = Flask(__name__)
CORS(app)

# Mock Data (Data sementara sebelum kita pakai Database sungguhan)
destinasi_wisata = [
    {
        "id": 1,
        "nama": "Makam Jumprit",
        "kategori": "Sejarah",
        "deskripsi": "Destinasi ziarah bersejarah yang tenang di dekat mata air utama...",
        "jarak": "1,5 KM",
        "ketinggian": "1800 mdpl"
    },
    {
        "id": 2,
        "nama": "Flying Fox",
        "kategori": "Wahana",
        "deskripsi": "Nikmati sensasi meluncur dari ketinggian melintasi pepohonan pinus.",
        "jarak": "500 M",
        "ketinggian": "1750 mdpl"
    },
    {
        "id": 3,
        "nama": "Hutan Pinus",
        "kategori": "Alam",
        "deskripsi": "Kesejukan alam di setiap langkah, cocok untuk trekking dan bersantai.",
        "jarak": "0 M",
        "ketinggian": "1700 mdpl"
    }
]

# Endpoint untuk halaman utama API
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Selamat datang di API GoWapit!"})

# Endpoint untuk mengambil data wisata
@app.route('/api/destinasi', methods=['GET'])
def get_destinasi():
    return jsonify({
        "status": "success",
        "data": destinasi_wisata
    })

if __name__ == '__main__':
    # debug=True agar server otomatis restart jika ada perubahan kode
    app.run(debug=True)