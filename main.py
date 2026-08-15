import os
from datetime import datetime, timedelta, timezone, date as date_type
from typing import Optional
import uuid
import jwt
import requests
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import midtransclient
import models
from database import engine, SessionLocal

import bcrypt

# --- SETUP HASHING PASSWORD ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or not isinstance(hashed_password, str):
        return False
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
        try:
            pwd_bytes = plain_password.encode('utf-8')
            if len(pwd_bytes) > 72:
                pwd_bytes = pwd_bytes[:72]
            return bcrypt.checkpw(pwd_bytes, hashed_password.encode('utf-8'))
        except Exception:
            return plain_password == hashed_password
    if plain_password == hashed_password:
        return True
    try:
        from passlib.hash import pbkdf2_sha256
        if hashed_password.startswith("$pbkdf2"):
            return pbkdf2_sha256.verify(plain_password, hashed_password)
    except Exception:
        pass
    return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

# --- SETUP JWT SECRET (Kunci Rahasia) ---
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "RAHASIA_WAPIT_KITA")
ALGORITHM = "HS256"
security = HTTPBearer() # Skema keamanan untuk membaca token "Bearer" dari Flutter

models.Base.metadata.create_all(bind=engine)

# Auto Migration Kolom Database (Kompatibel SQLite & Postgres)
def run_db_migrations():
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN foto_profil TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN google_sub TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN facebook_id TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE booking ADD COLUMN ticket_code TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE booking ADD COLUMN redeemed_at DATETIME"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE booking ADD COLUMN redeemed_by TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("ALTER TABLE ulasan ADD COLUMN foto TEXT"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("UPDATE booking SET ticket_code = order_id WHERE ticket_code IS NULL AND order_id IS NOT NULL"))
            conn.commit()
    except Exception:
        pass
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            # Migrasi path gambar destinasi ke path assets lengkap
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/MakamKiJumprit.jpeg' WHERE name LIKE '%Makam Ki Jumprit%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/HutanPinus.jpeg' WHERE name LIKE '%Hutan Pinus%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/MataAirSuci.jpeg' WHERE name LIKE '%Mata Air%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/InteraksiDenganMonyet.jpg' WHERE name LIKE '%Monyet%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/FlyingFox.jpeg' WHERE name LIKE '%Flying Fox Dewasa%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/FlyingFoxAnak.jpeg' WHERE name LIKE '%Flying Fox Anak%'"))
            conn.execute(text("UPDATE destinasi SET image = 'assets/images/HighRope.jpg' WHERE name LIKE '%High Rope%'"))
            
            # Tambahkan destinasi Tari Wedok Tegowanuh jika belum ada
            result = conn.execute(text("SELECT count(*) FROM destinasi WHERE name LIKE '%Tari Wedok%'")).scalar()
            if not result or result == 0:
                conn.execute(text(
                    "INSERT INTO destinasi (name, kategori, deskripsi_pendek, deskripsi_panjang, image) "
                    "VALUES ('Tari Wedok Tegowanuh', 'Budaya', "
                    "'Tari Wedok Tegowanuh merupakan tarian khas Kaloran, Temanggung, yang rutin ditampilkan di Wisata Wapit.', "
                    "'Tari Wedok Tegowanuh merupakan tarian khas Kaloran, Temanggung, yang rutin ditampilkan di Wisata Wapit (Wisata Alam Umbul Jumprit) sebagai upaya melestarikan warisan budaya sekaligus menarik minat wisatawan.', "
                    "'assets/images/Tari.jpeg')"
                ))
            else:
                conn.execute(text("UPDATE destinasi SET image = 'assets/images/Tari.jpeg' WHERE name LIKE '%Tari Wedok%'"))
            conn.commit()
    except Exception:
        pass

run_db_migrations()

app = FastAPI(title="GoWapit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def seeder_awal():
    db = SessionLocal()
    
    # 1. Seeder Destinasi
    if db.query(models.DestinasiModel).count() == 0:
        db.add_all([
            models.DestinasiModel(
                name="Makam Ki Jumprit", 
                kategori="Sejarah", 
                deskripsi_pendek="Destinasi ziarah tenang penjelajah sejarah dan budaya lokal di area mata air utama.", 
                deskripsi_panjang="Destinasi ziarah bersejarah yang tenang di dekat mata air utama. Ramai dikunjungi peziarah untuk mendoakan leluhur sekaligus memperdalam wawasan sejarah dan budaya lokal.", 
                image="assets/images/MakamKiJumprit.jpeg"
            ),
            models.DestinasiModel(
                name="Hutan Pinus Umbul Jumprit", 
                kategori="Alam", 
                deskripsi_pendek="Kawasan hutan asri di kaki Gunung Sindoro yang sejuk dengan jajaran pinus menjulang tinggi.", 
                deskripsi_panjang="Terhampar indah di kaki Gunung Sindoro dengan jajaran pohon pinus yang menjulang tinggi kokoh. Menyuguhkan panorama alam yang asri, berudara sejuk, dan menyegarkan pikiran.", 
                image="assets/images/HutanPinus.jpeg"
            ),
            models.DestinasiModel(
                name="Mata Air Umbul Jumprit", 
                kategori="Alam", 
                deskripsi_pendek="Sumber mata air abadi yang jernih, disucikan, dan menjadi hulu Sungai Progo.", 
                deskripsi_panjang="Sumber mata air abadi yang disucikan dan bernilai spiritual kuat. Airnya sangat jernih kebiruan, tidak pernah kering meski kemarau, dan menjadi hulu penting bagi Sungai Progo.", 
                image="assets/images/MataAirSuci.jpeg"
            ),
            models.DestinasiModel(
                name="Interaksi dengan Monyet", 
                kategori="Satwa", 
                deskripsi_pendek="Pengalaman tak terlupakan berinteraksi langsung dengan kawanan kera ekor panjang yang ramah.", 
                deskripsi_panjang="Nikmati keseruan berinteraksi langsung dengan kawanan kera ekor panjang yang ramah. Kehadiran satwa eksotis ini menjadi daya tarik unik yang melengkapi petualangan Anda di hutan pinus.", 
                image="assets/images/InteraksiDenganMonyet.jpg"
            ),
            models.DestinasiModel(
                name="Flying Fox Dewasa", 
                kategori="Wahana", 
                deskripsi_pendek="Wahana luncur gantung penantang adrenalin dengan pemandangan indah Hutan Pinus Wapit dari ketinggian.", 
                deskripsi_panjang="Pacu adrenalin Anda dengan meluncur di wahana Flying Fox! Rasakan sensasi mendebarkan yang membakar semangat sembari menikmati keindahan hijau Hutan Pinus Wapit dari ketinggian.", 
                image="assets/images/FlyingFox.jpeg"
            ),
            models.DestinasiModel(
                name="Flying Fox Anak", 
                kategori="Wahana", 
                deskripsi_pendek="Area meluncur yang aman untuk melatih keberanian dan kemandirian si kecil.", 
                deskripsi_panjang="Wahana meluncur yang dirancang khusus dan aman untuk anak-anak. Pilihan sempurna untuk liburan keluarga yang berkesan sekaligus melatih keberanian serta kemandirian si kecil.", 
                image="assets/images/FlyingFoxAnak.jpeg"
            ),
            models.DestinasiModel(
                name="High Rope", 
                kategori="Wahana", 
                deskripsi_pendek="Uji keberanian dan keseimbangan di atas jembatan gantung tinggi yang memacu adrenalin.", 
                deskripsi_panjang="Uji mental, keseimbangan, dan ketangkasan Anda di wahana tali tinggi. Berjalan di atas jembatan gantung ketinggian akan memberikan sensasi liburan menantang yang memuaskan.", 
                image="assets/images/HighRope.jpg"
            ),
            models.DestinasiModel(
                name="Tari Wedok Tegowanuh", 
                kategori="Budaya", 
                deskripsi_pendek="Tari Wedok Tegowanuh merupakan tarian khas Kaloran, Temanggung, yang rutin ditampilkan di Wisata Wapit.", 
                deskripsi_panjang="Tari Wedok Tegowanuh merupakan tarian khas Kaloran, Temanggung, yang rutin ditampilkan di Wisata Wapit (Wisata Alam Umbul Jumprit) sebagai upaya melestarikan warisan budaya sekaligus menarik minat wisatawan.", 
                image="assets/images/Tari.jpeg"
            ),
        ])
        db.commit()

    # 2. Seeder Paket Wisata
    if db.query(models.PaketModel).count() == 0:
        db.add_all([
            models.PaketModel(nama="Platinum", harga=300000, fasilitas="Wisata: Hutan Pinus, Mata Air Suci, Makam Ki Jumprit, Interaksi dengan monyet\nTiket Parkir\nCamping 2 Orang\nWahana: Flying Fox, Flying Fox Kids, High Rope, Archery\nTiket Masuk Cafe Coffe Chocolatte"),
            models.PaketModel(nama="Gold", harga=100000, fasilitas="Wisata: Hutan Pinus, Mata Air Suci, Interaksi dengan Monyet\nTiket Parkir\nWahana: Flying Fox, Flying Fox Kids, High Rope\nTiket masuk Cafe Coffe Chocolatte"),
            models.PaketModel(nama="Silver", harga=87000, fasilitas="Wisata: Hutan Pinus\nTiket Parkir\nWahana: High Rope\nTiket Masuk Cafe Coffe Chocolatte"),
        ])
        db.commit()

    # 2b. Seeder Voucher (idempoten per kode)
    kode_ada = {v.kode for v in db.query(models.VoucherModel).all()}
    voucher_baru = []
    if "WAPIT10" not in kode_ada:
        voucher_baru.append(models.VoucherModel(
            kode="WAPIT10", tipe="persen", nilai=10, maks_diskon=20000, kuota=999
        ))
    if "HEMAT20K" not in kode_ada:
        voucher_baru.append(models.VoucherModel(
            kode="HEMAT20K", tipe="nominal", nilai=20000, kuota=999
        ))
    if voucher_baru:
        db.add_all(voucher_baru)
        db.commit()

    # 3. Seeder Layanan Umum
    if db.query(models.LayananUmumModel).count() == 0:
        db.add_all([
            models.LayananUmumModel(nama_layanan="Pemadam Kebakaran", kontak="(0293)4901790"),
            models.LayananUmumModel(nama_layanan="Ambulance", kontak="(0293)491119"),
            models.LayananUmumModel(nama_layanan="Polres Temanggung", kontak="(0293)491110"),
        ])
        db.commit()

    # 4. Seeder Kuliner (Gabungan Chocolatte & Kedai Hutan)
    if db.query(models.KulinerModel).count() == 0:
        # Data Coffe Chocolatte
        menu_chocolatte = [
            {"kategori": "Coffe", "nama": "Cappucino", "harga": 15000},
            {"kategori": "Coffe", "nama": "Maccachino", "harga": 15000},
            {"kategori": "Coffe", "nama": "Latte", "harga": 15000},
            {"kategori": "Coffe", "nama": "Kopi Susu Aren", "harga": 15000},
            {"kategori": "Coffe", "nama": "Sanger", "harga": 15000},
            {"kategori": "Coffe", "nama": "Coffe Beer", "harga": 20000},
            {"kategori": "Coffe", "nama": "Coffe Peanut", "harga": 15000},
            {"kategori": "Coffe", "nama": "Butter", "harga": 15000},
            {"kategori": "Coffe", "nama": "Coffe Oreo", "harga": 15000},
            {"kategori": "Coffe", "nama": "Es Kopi", "harga": 15000},
            {"kategori": "Coffe", "nama": "Machiato", "harga": 15000},
            {"kategori": "Coffe", "nama": "Vanilla Latte", "harga": 15000},
            {"kategori": "Coffe", "nama": "Casscarasu", "harga": 15000},
            {"kategori": "Coklat", "nama": "Hot Chocolate", "harga": 15000},
            {"kategori": "Coklat", "nama": "Choco Latte", "harga": 15000},
            {"kategori": "Coklat", "nama": "Choco Cheese", "harga": 15000},
            {"kategori": "Coklat", "nama": "Choco Shake", "harga": 15000},
            {"kategori": "Wappit Mie", "nama": "Mie Njeplak", "deskripsi": "Mie dengan bubuk cabe", "harga": 15000},
            {"kategori": "Wappit Mie", "nama": "Mie Entah Marah", "deskripsi": "Mie goreng pedas level 123", "harga": 15000},
            {"kategori": "Wappit Mie", "nama": "Mie Goreng Ori", "deskripsi": "Mie goreng original", "harga": 8000},
            {"kategori": "Wappit Mie", "nama": "Mie goreng isi", "deskripsi": "Mie goreng isi telur/sosis", "harga": 10000},
            {"kategori": "Wappit Mie", "nama": "Mie Ori Seblak Keplak", "deskripsi": "Mie rebus dengan bubuk cabe", "harga": 15000},
            {"kategori": "Wappit Mie", "nama": "Mie Ramen", "deskripsi": "Mie rebus dengan topping ramen", "harga": 15000},
            {"kategori": "Wappit Mie", "nama": "Mie Rebus Ori", "deskripsi": "Mie rebus original", "harga": 8000},
            {"kategori": "Wappit Mie", "nama": "Mie Rebus Isi", "deskripsi": "Mie rebus isi telur/sosis", "harga": 10000},
            {"kategori": "Wappit RabahGos", "nama": "SONUT (SOsis NUggeT)", "harga": 15000},
            {"kategori": "Wappit RabahGos", "nama": "SOBAKS (SOsis BAKSo)", "harga": 15000},
            {"kategori": "Wappit RabahGos", "nama": "WAPPIT MIX (Sosis nugget bakso)", "harga": 20000},
            {"kategori": "Kentang", "nama": "Original", "deskripsi": "Kentang goreng", "harga": 12000},
            {"kategori": "Kentang", "nama": "Cheese and Meat", "deskripsi": "Kentang goreng dengan daging dan saus keju", "harga": 17000},
        ]
        
        menu_kedaihutan = [
            {"kategori": "Coffe", "nama": "Robusta Tubruk", "harga": 8000},
            {"kategori": "Coffe", "nama": "Robusta Americano", "harga": 13000},
            {"kategori": "Coffe", "nama": "Robusta Expresso", "harga": 15000},
            {"kategori": "Coffe", "nama": "Robusta V60", "harga": 15000},
            {"kategori": "Coffe", "nama": "Robusta Vietnamdrip", "harga": 20000},
            {"kategori": "Coffe", "nama": "Robusta Mopakot", "harga": 20000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed Tubruk", "harga": 13000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed Americano", "harga": 15000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed Expresso", "harga": 18000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed V60", "harga": 20000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed Vietnamdrip", "harga": 25000},
            {"kategori": "Coffe", "nama": "Arabika Fullwashed Mopakot", "harga": 25000},
            {"kategori": "Coffe", "nama": "Arabika Natural Tubruk", "harga": 15000},
            {"kategori": "Coffe", "nama": "Arabika Natural Americano", "harga": 18000},
            {"kategori": "Coffe", "nama": "Arabika Natural Expresso", "harga": 20000},
            {"kategori": "Coffe", "nama": "Arabika Natural V60", "harga": 25000},
            {"kategori": "Coffe", "nama": "Arabika Natural Vietnamdrip", "harga": 28000},
            {"kategori": "Coffe", "nama": "Arabika Natural Mopakot", "harga": 28000},
            {"kategori": "Coffe", "nama": "Luwak Tubruk", "harga": 25000},
            {"kategori": "Coffe", "nama": "Luwak Americano", "harga": 28000},
            {"kategori": "Coffe", "nama": "Luwak Expresso", "harga": 30000},
            {"kategori": "Coffe", "nama": "Luwak V60", "harga": 30000},
            {"kategori": "Coffe", "nama": "Luwak Vietnamdrip", "harga": 30000},
            {"kategori": "Coffe", "nama": "Luwak Mopakot", "harga": 30000},
            {"kategori": "Coffe", "nama": "Blend Tubruk", "harga": 10000},
            {"kategori": "Coffe", "nama": "Blend Americano", "harga": 13000},
            {"kategori": "Coffe", "nama": "Blend Expresso", "harga": 15000},
            {"kategori": "Coffe", "nama": "Blend V60", "harga": 20000},
            {"kategori": "Coffe", "nama": "Blend Vietnamdrip", "harga": 20000},
            {"kategori": "Coffe", "nama": "Blend Mopakot", "harga": 20000},
            {"kategori": "Tambahan", "nama": "+ Ice", "harga": 2000},
        ]

        for m in menu_chocolatte:
            db.add(models.KulinerModel(kedai="Cafe Coffe Chocolatte", kategori=m["kategori"], nama_menu=m["nama"], deskripsi=m.get("deskripsi", ""), harga=m["harga"]))
        for m in menu_kedaihutan:
            db.add(models.KulinerModel(kedai="Kedai Hutan", kategori=m["kategori"], nama_menu=m["nama"], deskripsi=m.get("deskripsi", ""), harga=m["harga"]))
            
        db.commit()

    # 4. Seeder Akun Default Petugas Loket
    petugas = db.query(models.UserModel).filter(models.UserModel.email == "petugas@gowapit.com").first()
    if not petugas:
        hashed_pwd = get_password_hash("petugas123")
        petugas = models.UserModel(
            nama_lengkap="Petugas Loket Wapit",
            email="petugas@gowapit.com",
            password=hashed_pwd,
            role="petugas"
        )
        db.add(petugas)
        db.commit()
    else:
        if petugas.role != "petugas":
            petugas.role = "petugas"
            db.commit()
    
    db.close()

@app.get("/")
def read_root():
    return {"status": "success", "message": "Selamat datang di GoWapit API!"}

@app.get("/api/destinasi")
def get_destinasi(db: Session = Depends(get_db)):
    wisata = db.query(models.DestinasiModel).all()
    stats = db.query(
        models.UlasanModel.destinasi_id,
        func.avg(models.UlasanModel.rating).label("avg_rating"),
        func.count(models.UlasanModel.id).label("total_ulasan")
    ).group_by(models.UlasanModel.destinasi_id).all()
    
    stats_map = {
        s.destinasi_id: {
            "rating": round(float(s.avg_rating), 1) if s.avg_rating else 0.0,
            "jumlah_ulasan": int(s.total_ulasan) if s.total_ulasan else 0
        }
        for s in stats
    }

    data = []
    for w in wisata:
        st = stats_map.get(w.id, {"rating": 0.0, "jumlah_ulasan": 0})
        data.append({
            "id": w.id,
            "name": w.name,
            "kategori": w.kategori,
            "deskripsi_pendek": w.deskripsi_pendek,
            "deskripsi_panjang": w.deskripsi_panjang,
            "image": w.image,
            "jarak": w.jarak,
            "ketinggian": w.ketinggian,
            "rating": st["rating"],
            "jumlah_ulasan": st["jumlah_ulasan"]
        })
    return {"status": "success", "data": data}

@app.post("/api/register")
def register_user(user_data: dict, db: Session = Depends(get_db)):
    if not user_data.get("email") or not user_data.get("password") or not user_data.get("nama_lengkap"):
        raise HTTPException(status_code=400, detail="Semua field wajib diisi!")

    user_exists = db.query(models.UserModel).filter(models.UserModel.email == user_data["email"]).first()
    if user_exists:
        raise HTTPException(status_code=400, detail="Email sudah digunakan!")

    hashed_pwd = get_password_hash(user_data["password"])
    baru = models.UserModel(
        nama_lengkap=user_data["nama_lengkap"],
        email=user_data["email"],
        password=hashed_pwd
    )
    db.add(baru)
    db.commit()
    db.refresh(baru)
    return {"status": "success", "message": "Akun berhasil dibuat!", "user_id": baru.id}

@app.post("/api/login")
def login_user(login_data: dict, db: Session = Depends(get_db)):
    if not login_data.get("email") or not login_data.get("password"):
        raise HTTPException(status_code=400, detail="Email dan password wajib diisi!")

    user = db.query(models.UserModel).filter(models.UserModel.email == login_data["email"]).first()
    
    if not user or not verify_password(login_data["password"], user.password):
        raise HTTPException(status_code=400, detail="Email atau password salah!")
    
    # 1. Buat masa berlaku token (aktif 7 hari)
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    
    # 2. Bungkus email user dan waktu expired ke dalam token
    to_encode = {"sub": user.email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # 3. Kirim kembali access_token ke Flutter
    return {
        "status": "success", 
        "message": "Login berhasil!", 
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nama_lengkap": user.nama_lengkap,
            "email": user.email,
            "role": user.role or "user"
        }
    }

@app.post("/api/auth/google")
def google_auth(data: dict, db: Session = Depends(get_db)):
    id_token = data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Token ID Google wajib diisi!")

    try:
        resp = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}", timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Token Google tidak valid atau sudah kedaluwarsa!")
        token_info = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memverifikasi token Google: {str(e)}")

    if "error_description" in token_info:
        raise HTTPException(status_code=400, detail="Token Google tidak valid!")

    google_sub = token_info.get("sub")
    email = token_info.get("email")

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Data profil Google tidak lengkap (email/sub hilang).")

    nama_lengkap = token_info.get("name") or email.split("@")[0]

    # 1. Cari user berdasarkan google_sub
    user = db.query(models.UserModel).filter(models.UserModel.google_sub == google_sub).first()

    # 2. Jika belum ada, cari berdasarkan email lalu tautkan google_sub
    if not user:
        user = db.query(models.UserModel).filter(models.UserModel.email == email).first()
        if user:
            user.google_sub = google_sub
            db.commit()
            db.refresh(user)

    # 3. Jika tetap belum ada, buat user baru
    if not user:
        random_pwd = get_password_hash(uuid.uuid4().hex)
        user = models.UserModel(
            nama_lengkap=nama_lengkap,
            email=email,
            password=random_pwd,
            google_sub=google_sub,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": user.email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "status": "success",
        "message": "Login Google berhasil!",
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nama_lengkap": user.nama_lengkap,
            "email": user.email,
            "role": user.role or "user"
        }
    }

@app.post("/api/auth/facebook")
def facebook_auth(data: dict, db: Session = Depends(get_db)):
    access_token = data.get("access_token")
    facebook_id = data.get("facebook_id")
    email = data.get("email")
    nama_lengkap = data.get("nama_lengkap") or data.get("name")
    foto_profil = data.get("foto_profil") or data.get("picture")

    # Jika access_token diberikan dan bukan mock/test, coba verifikasi ke Facebook Graph API
    if access_token and not str(access_token).startswith("mock_") and not str(access_token).startswith("test_"):
        try:
            resp = requests.get(
                f"https://graph.facebook.com/me?fields=id,name,email,picture.type(large)&access_token={access_token}",
                timeout=10
            )
            if resp.status_code == 200:
                fb_info = resp.json()
                facebook_id = fb_info.get("id") or facebook_id
                nama_lengkap = fb_info.get("name") or nama_lengkap
                email = fb_info.get("email") or email
                if not foto_profil and fb_info.get("picture", {}).get("data", {}).get("url"):
                    foto_profil = fb_info["picture"]["data"]["url"]
            elif not facebook_id:
                raise HTTPException(status_code=400, detail="Token Facebook tidak valid atau sudah kedaluwarsa!")
        except HTTPException:
            raise
        except Exception as e:
            if not facebook_id:
                raise HTTPException(status_code=400, detail=f"Gagal memverifikasi token Facebook: {str(e)}")

    if not facebook_id and not email:
        raise HTTPException(status_code=400, detail="ID Facebook atau Email wajib disertakan.")

    # Jika email tidak tersedia dari Facebook, gunakan fallback email berbasis Facebook ID
    if not email:
        email = f"fb_{facebook_id}@facebook.gowapit.id"
    if not nama_lengkap:
        nama_lengkap = "Pengguna Facebook"

    # 1. Cari user berdasarkan facebook_id
    user = None
    if facebook_id:
        user = db.query(models.UserModel).filter(models.UserModel.facebook_id == str(facebook_id)).first()

    # 2. Jika belum ketemu, cari berdasarkan email lalu tautkan facebook_id
    if not user and email:
        user = db.query(models.UserModel).filter(models.UserModel.email == email).first()
        if user:
            if facebook_id:
                user.facebook_id = str(facebook_id)
            if foto_profil and not user.foto_profil:
                user.foto_profil = foto_profil
            db.commit()
            db.refresh(user)

    # 3. Jika tetap belum ada, buat user baru
    if not user:
        random_pwd = get_password_hash(uuid.uuid4().hex)
        user = models.UserModel(
            nama_lengkap=nama_lengkap,
            email=email,
            password=random_pwd,
            facebook_id=str(facebook_id) if facebook_id else None,
            foto_profil=foto_profil,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": user.email, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "status": "success",
        "message": "Login Facebook berhasil!",
        "access_token": encoded_jwt,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nama_lengkap": user.nama_lengkap,
            "email": user.email,
            "foto_profil": user.foto_profil,
            "role": user.role or "user"
        }
    }

# Fungsi/middleware untuk memvalidasi token JWT
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token tidak valid")
    except Exception:
        raise HTTPException(status_code=401, detail="Token tidak valid atau kedaluwarsa")
    
    user = db.query(models.UserModel).filter(models.UserModel.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User tidak ditemukan")
    return user

# Helper untuk token opsional pada endpoint publik (misal GET ulasan)
def get_optional_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.UserModel]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        return db.query(models.UserModel).filter(models.UserModel.email == email).first()
    except Exception:
        return None

class UlasanRequest(BaseModel):
    rating: int
    ulasan: Optional[str] = ""
    foto: Optional[str] = None

# --- ENDPOINTS ULASAN DESTINASI ---
@app.get("/api/destinasi/{destinasi_id}/ulasan")
def get_ulasan_destinasi(
    destinasi_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    destinasi = db.query(models.DestinasiModel).filter(models.DestinasiModel.id == destinasi_id).first()
    if not destinasi:
        raise HTTPException(status_code=404, detail="Destinasi tidak ditemukan")

    curr_user = get_optional_current_user(request, db)
    curr_user_id = curr_user.id if curr_user else None

    ulasan_list = db.query(models.UlasanModel).filter(
        models.UlasanModel.destinasi_id == destinasi_id
    ).order_by(models.UlasanModel.created_at.desc()).all()

    data = []
    for u in ulasan_list:
        data.append({
            "id": u.id,
            "destinasi_id": u.destinasi_id,
            "user_id": u.user_id,
            "nama_user": u.user.nama_lengkap if u.user else "Anonim",
            "foto_profil": u.user.foto_profil if u.user else None,
            "rating": u.rating,
            "ulasan": u.ulasan or "",
            "foto": u.foto or None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
            "milik_saya": (curr_user_id is not None and u.user_id == curr_user_id)
        })
    return {"status": "success", "data": data}

@app.post("/api/destinasi/{destinasi_id}/ulasan")
def create_or_update_ulasan(
    destinasi_id: int,
    ulasan_in: UlasanRequest,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if ulasan_in.rating < 1 or ulasan_in.rating > 5:
        raise HTTPException(status_code=400, detail="Rating harus bernilai antara 1 dan 5")

    destinasi = db.query(models.DestinasiModel).filter(models.DestinasiModel.id == destinasi_id).first()
    if not destinasi:
        raise HTTPException(status_code=404, detail="Destinasi tidak ditemukan")

    existing = db.query(models.UlasanModel).filter(
        models.UlasanModel.destinasi_id == destinasi_id,
        models.UlasanModel.user_id == current_user.id
    ).first()

    if existing:
        existing.rating = ulasan_in.rating
        existing.ulasan = ulasan_in.ulasan
        existing.foto = ulasan_in.foto
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {
            "status": "success",
            "message": "Ulasan berhasil diperbarui!",
            "data": {
                "id": existing.id,
                "destinasi_id": existing.destinasi_id,
                "rating": existing.rating,
                "ulasan": existing.ulasan,
                "foto": existing.foto,
                "created_at": existing.created_at.isoformat() if existing.created_at else None,
                "updated_at": existing.updated_at.isoformat() if existing.updated_at else None
            }
        }
    else:
        baru = models.UlasanModel(
            destinasi_id=destinasi_id,
            user_id=current_user.id,
            rating=ulasan_in.rating,
            ulasan=ulasan_in.ulasan,
            foto=ulasan_in.foto
        )
        db.add(baru)
        db.commit()
        db.refresh(baru)
        return {
            "status": "success",
            "message": "Ulasan berhasil ditambahkan!",
            "data": {
                "id": baru.id,
                "destinasi_id": baru.destinasi_id,
                "rating": baru.rating,
                "ulasan": baru.ulasan,
                "foto": baru.foto,
                "created_at": baru.created_at.isoformat() if baru.created_at else None,
                "updated_at": baru.updated_at.isoformat() if baru.updated_at else None
            }
        }

@app.put("/api/destinasi/{destinasi_id}/ulasan")
def update_ulasan(
    destinasi_id: int,
    ulasan_in: UlasanRequest,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if ulasan_in.rating < 1 or ulasan_in.rating > 5:
        raise HTTPException(status_code=400, detail="Rating harus bernilai antara 1 dan 5")

    existing = db.query(models.UlasanModel).filter(
        models.UlasanModel.destinasi_id == destinasi_id,
        models.UlasanModel.user_id == current_user.id
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Ulasan Anda tidak ditemukan")

    existing.rating = ulasan_in.rating
    existing.ulasan = ulasan_in.ulasan
    existing.foto = ulasan_in.foto
    existing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(existing)
    return {
        "status": "success",
        "message": "Ulasan berhasil diperbarui!",
        "data": {
            "id": existing.id,
            "destinasi_id": existing.destinasi_id,
            "rating": existing.rating,
            "ulasan": existing.ulasan,
            "foto": existing.foto
        }
    }

@app.delete("/api/destinasi/{destinasi_id}/ulasan")
def delete_ulasan(
    destinasi_id: int,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(models.UlasanModel).filter(
        models.UlasanModel.destinasi_id == destinasi_id,
        models.UlasanModel.user_id == current_user.id
    ).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Ulasan Anda tidak ditemukan")

    db.delete(existing)
    db.commit()
    return {"status": "success", "message": "Ulasan berhasil dihapus!"}

class UpdateProfileRequest(BaseModel):
    nama_lengkap: str = None
    foto_profil: str = None

@app.get("/api/users/me")
def get_user_profile(current_user: models.UserModel = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "nama_lengkap": current_user.nama_lengkap,
        "foto_profil": current_user.foto_profil or "",
        "role": current_user.role or "user"
    }

@app.put("/api/users/me")
def update_user_profile(
    update_data: UpdateProfileRequest, 
    current_user: models.UserModel = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if update_data.nama_lengkap:
        current_user.nama_lengkap = update_data.nama_lengkap
    if update_data.foto_profil is not None:
        current_user.foto_profil = update_data.foto_profil
    
    db.commit()
    db.refresh(current_user)
    
    return {
        "status": "success",
        "message": "Profil berhasil diperbarui!",
        "user": {
            "email": current_user.email,
            "nama_lengkap": current_user.nama_lengkap,
            "foto_profil": current_user.foto_profil or ""
        }
    }

@app.get("/api/paket")
def get_paket(db: Session = Depends(get_db)):
    data_paket = db.query(models.PaketModel).all()
    result = []
    for p in data_paket:
        result.append({
            "id": p.id,
            "nama": p.nama,
            "harga": p.harga,
            "fasilitas": p.fasilitas
        })
    return {"status": "success", "data": result}

@app.get("/api/kuliner")
def get_kuliner(kedai: str = None, db: Session = Depends(get_db)):
    query = db.query(models.KulinerModel)
    if kedai:
        query = query.filter(models.KulinerModel.kedai == kedai)
    data_kuliner = query.all()
    return {"status": "success", "data": data_kuliner}

@app.get("/api/layanan-umum")
def get_layanan(db: Session = Depends(get_db)):
    data_layanan = db.query(models.LayananUmumModel).all()
    return {"status": "success", "data": data_layanan}

# --- KONFIGURASI MIDTRANS ---
MIDTRANS_SERVER_KEY = os.getenv("MIDTRANS_SERVER_KEY", "SB-Mid-server-kunci-sementara")
snap = midtransclient.Snap(
    is_production=False,
    server_key=MIDTRANS_SERVER_KEY
)

class CustomerDetail(BaseModel):
    first_name: str
    email: str

class CheckoutRequest(BaseModel):
    order_id: str
    gross_amount: int
    customer_details: CustomerDetail

@app.post("/api/checkout")
def checkout(request_data: CheckoutRequest):
    try:
        param = {
            "transaction_details": {
                "order_id": request_data.order_id,
                "gross_amount": request_data.gross_amount
            },
            "customer_details": {
                "first_name": request_data.customer_details.first_name,
                "email": request_data.customer_details.email
            },
        }
        transaction = snap.create_transaction(param)
        return {"status": "success", "redirect_url": transaction['redirect_url']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# HELPER SLOT
# ============================================================
KAPASITAS_PER_PAKET = 100

def _tanggal_dalam_range(mulai_str: str, akhir_str: str):
    """Kembalikan list YYYY-MM-DD dari mulai (inclusive) sampai akhir (inclusive)."""
    try:
        mulai = datetime.strptime(mulai_str, "%Y-%m-%d").date()
        akhir = datetime.strptime(akhir_str, "%Y-%m-%d").date()
    except ValueError:
        return []
    hasil = []
    cur = mulai
    while cur <= akhir:
        hasil.append(cur.isoformat())
        cur += timedelta(days=1)
    return hasil

def _hitung_slot(paket_id: int, tanggal_str: str, db: Session) -> int:
    """Hitung sisa slot untuk paket di tanggal tertentu.
    Booking EXPIRED (PENDING + expires_at lewat) diabaikan secara lazy.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Booking yang berjalan valid: PAID, atau PENDING yang belum expired
    bookings = db.query(models.BookingModel).filter(
        models.BookingModel.paket_id == paket_id,
        models.BookingModel.status.in_(["PAID", "PENDING"])
    ).all()
    terpakai = 0
    for b in bookings:
        # Skip PENDING yang sudah expired
        if b.status == "PENDING" and b.expires_at and b.expires_at < now:
            continue
        # Cek apakah tanggal masuk range booking ini
        if b.tanggal_akhir:
            hari_list = _tanggal_dalam_range(b.tanggal_mulai, b.tanggal_akhir)
        else:
            hari_list = [b.tanggal_mulai]
        if tanggal_str in hari_list:
            terpakai += b.jumlah_orang
    return max(0, KAPASITAS_PER_PAKET - terpakai)

# ============================================================
# ENDPOINTS SLOT
# ============================================================
@app.get("/api/paket/{paket_id}/slot")
def get_slot_paket(
    paket_id: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    db: Session = Depends(get_db)
):
    paket = db.query(models.PaketModel).filter(models.PaketModel.id == paket_id).first()
    if not paket:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")

    hari_ini = datetime.now(timezone.utc).date()
    try:
        mulai = datetime.strptime(start, "%Y-%m-%d").date() if start else hari_ini
        akhir = datetime.strptime(end, "%Y-%m-%d").date() if end else (hari_ini + timedelta(days=59))
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal tidak valid, gunakan YYYY-MM-DD")

    # Maksimal 90 hari ke depan agar tidak terlalu berat
    if (akhir - mulai).days > 90:
        akhir = mulai + timedelta(days=89)

    hasil = {}
    cur = mulai
    while cur <= akhir:
        hasil[cur.isoformat()] = _hitung_slot(paket_id, cur.isoformat(), db)
        cur += timedelta(days=1)

    return {"status": "success", "paket_id": paket_id, "data": hasil}

# ============================================================
# ENDPOINTS VOUCHER
# ============================================================
@app.get("/api/voucher/{kode}")
def get_voucher(kode: str, subtotal: int = 0, db: Session = Depends(get_db)):
    voucher = db.query(models.VoucherModel).filter(
        models.VoucherModel.kode == kode.upper()
    ).first()
    if not voucher:
        raise HTTPException(status_code=404, detail="Kode voucher tidak ditemukan")
    if not voucher.aktif:
        raise HTTPException(status_code=400, detail="Voucher sudah tidak aktif")
    if voucher.kuota > 0 and voucher.terpakai >= voucher.kuota:
        raise HTTPException(status_code=400, detail="Kuota voucher sudah habis")

    if voucher.tipe == "persen":
        diskon = int(subtotal * voucher.nilai / 100)
        if voucher.maks_diskon:
            diskon = min(diskon, voucher.maks_diskon)
    else:  # nominal
        diskon = voucher.nilai

    diskon = min(diskon, subtotal)  # tidak bisa melebihi subtotal
    return {
        "status": "success",
        "data": {
            "id": voucher.id,
            "kode": voucher.kode,
            "tipe": voucher.tipe,
            "nilai": voucher.nilai,
            "maks_diskon": voucher.maks_diskon,
            "diskon": diskon,
            "total": subtotal - diskon
        }
    }

# ============================================================
# ENDPOINTS BOOKING
# ============================================================
HARGA_MALAM_TAMBAHAN = 150_000

class BookingRequest(BaseModel):
    paket_id: int
    jumlah_orang: int
    tanggal_mulai: str           # YYYY-MM-DD
    tanggal_akhir: Optional[str] = None
    voucher_kode: Optional[str] = None

class PayRequest(BaseModel):
    mode: str  # "simulasi" | "midtrans"

@app.post("/api/booking")
def buat_booking(
    req: BookingRequest,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # --- Validasi paket ---
    paket = db.query(models.PaketModel).filter(models.PaketModel.id == req.paket_id).first()
    if not paket:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan")

    if req.jumlah_orang < 1 or req.jumlah_orang > 20:
        raise HTTPException(status_code=400, detail="Jumlah orang harus antara 1 dan 20")

    # --- Validasi tanggal ---
    try:
        tgl_mulai = datetime.strptime(req.tanggal_mulai, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Format tanggal_mulai tidak valid")

    hari_ini = datetime.now(timezone.utc).date()
    if tgl_mulai < hari_ini:
        raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh di masa lalu")

    is_platinum = "platinum" in paket.nama.lower()

    if is_platinum:
        if not req.tanggal_akhir:
            raise HTTPException(status_code=400, detail="Paket Platinum wajib memilih tanggal akhir")
        try:
            tgl_akhir = datetime.strptime(req.tanggal_akhir, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Format tanggal_akhir tidak valid")
        if tgl_akhir <= tgl_mulai:
            raise HTTPException(status_code=400, detail="Paket Platinum: tanggal akhir harus setelah tanggal mulai")
        if (tgl_akhir - tgl_mulai).days < 1:
            raise HTTPException(status_code=400, detail="Paket Platinum minimal 1 malam (2 hari)")
        malam = (tgl_akhir - tgl_mulai).days
        malam_tambahan = max(0, malam - 1)
        hari_list = _tanggal_dalam_range(req.tanggal_mulai, req.tanggal_akhir)
    else:
        tgl_akhir = None
        malam_tambahan = 0
        hari_list = [req.tanggal_mulai]

    # --- Validasi slot setiap hari ---
    for hari in hari_list:
        sisa = _hitung_slot(req.paket_id, hari, db)
        if sisa < req.jumlah_orang:
            raise HTTPException(
                status_code=400,
                detail=f"Slot tidak cukup pada tanggal {hari}. Sisa: {sisa} orang."
            )

    # --- Hitung harga ---
    subtotal = paket.harga * req.jumlah_orang + malam_tambahan * HARGA_MALAM_TAMBAHAN
    diskon = 0
    voucher_id = None

    if req.voucher_kode:
        voucher = db.query(models.VoucherModel).filter(
            models.VoucherModel.kode == req.voucher_kode.upper()
        ).first()
        if not voucher or not voucher.aktif:
            raise HTTPException(status_code=400, detail="Kode voucher tidak valid atau tidak aktif")
        if voucher.kuota > 0 and voucher.terpakai >= voucher.kuota:
            raise HTTPException(status_code=400, detail="Kuota voucher habis")
        if voucher.tipe == "persen":
            diskon = int(subtotal * voucher.nilai / 100)
            if voucher.maks_diskon:
                diskon = min(diskon, voucher.maks_diskon)
        else:
            diskon = voucher.nilai
        diskon = min(diskon, subtotal)
        voucher.terpakai += 1
        voucher_id = voucher.id

    total_harga = subtotal - diskon
    order_id = f"WPT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{current_user.id}"
    ticket_code = f"WPT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)

    booking = models.BookingModel(
        user_id=current_user.id,
        paket_id=req.paket_id,
        tanggal_mulai=req.tanggal_mulai,
        tanggal_akhir=req.tanggal_akhir,
        jumlah_orang=req.jumlah_orang,
        malam_tambahan=malam_tambahan,
        voucher_id=voucher_id,
        subtotal=subtotal,
        diskon=diskon,
        total_harga=total_harga,
        status="PENDING",
        order_id=order_id,
        ticket_code=ticket_code,
        expires_at=expires_at
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return {
        "status": "success",
        "message": "Booking berhasil dibuat!",
        "data": {
            "id": booking.id,
            "paket_id": booking.paket_id,
            "nama_paket": paket.nama,
            "tanggal_mulai": booking.tanggal_mulai,
            "tanggal_akhir": booking.tanggal_akhir,
            "jumlah_orang": booking.jumlah_orang,
            "malam_tambahan": booking.malam_tambahan,
            "subtotal": booking.subtotal,
            "diskon": booking.diskon,
            "total_harga": booking.total_harga,
            "status": booking.status,
            "order_id": booking.order_id,
            "expires_at": booking.expires_at.isoformat() if booking.expires_at else None
        }
    }

@app.get("/api/booking")
def get_my_bookings(
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    bookings = db.query(models.BookingModel).filter(
        models.BookingModel.user_id == current_user.id,
        models.BookingModel.status == "PENDING"
    ).order_by(models.BookingModel.created_at.desc()).all()

    data = []
    for b in bookings:
        # Lazy expire
        if b.expires_at and b.expires_at < now:
            b.status = "EXPIRED"
            db.commit()
            continue
        data.append({
            "id": b.id,
            "paket_id": b.paket_id,
            "nama_paket": b.paket.nama if b.paket else "-",
            "harga_paket": b.paket.harga if b.paket else 0,
            "tanggal_mulai": b.tanggal_mulai,
            "tanggal_akhir": b.tanggal_akhir,
            "jumlah_orang": b.jumlah_orang,
            "malam_tambahan": b.malam_tambahan,
            "subtotal": b.subtotal,
            "diskon": b.diskon,
            "total_harga": b.total_harga,
            "status": b.status,
            "order_id": b.order_id,
            "expires_at": b.expires_at.isoformat() if b.expires_at else None
        })
    return {"status": "success", "data": data}

@app.delete("/api/booking/{booking_id}")
def cancel_booking(
    booking_id: int,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(models.BookingModel).filter(
        models.BookingModel.id == booking_id,
        models.BookingModel.user_id == current_user.id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.status != "PENDING":
        raise HTTPException(status_code=400, detail="Hanya booking PENDING yang bisa dibatalkan")

    # Kembalikan terpakai voucher jika ada
    if booking.voucher_id:
        voucher = db.query(models.VoucherModel).filter(models.VoucherModel.id == booking.voucher_id).first()
        if voucher and voucher.terpakai > 0:
            voucher.terpakai -= 1

    booking.status = "CANCELLED"
    db.commit()
    return {"status": "success", "message": "Booking berhasil dibatalkan"}

@app.post("/api/booking/{booking_id}/pay")
def pay_booking(
    booking_id: int,
    req: PayRequest,
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    booking = db.query(models.BookingModel).filter(
        models.BookingModel.id == booking_id,
        models.BookingModel.user_id == current_user.id
    ).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking tidak ditemukan")
    if booking.status != "PENDING":
        raise HTTPException(status_code=400, detail="Booking sudah tidak aktif")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if booking.expires_at and booking.expires_at < now:
        booking.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=400, detail="Booking sudah kedaluwarsa")

    if req.mode == "simulasi":
        booking.status = "PAID"
        db.commit()
        return {
            "status": "success",
            "message": "Pembayaran simulasi berhasil! E-Tiket aktif.",
            "data": {"booking_id": booking.id, "status": "PAID"}
        }
    elif req.mode == "midtrans":
        try:
            param = {
                "transaction_details": {
                    "order_id": booking.order_id,
                    "gross_amount": booking.total_harga
                },
                "customer_details": {
                    "first_name": current_user.nama_lengkap,
                    "email": current_user.email
                }
            }
            transaction = snap.create_transaction(param)
            # Anggap PAID setelah URL dibuat (sesuai constraint yang ada)
            booking.status = "PAID"
            db.commit()
            return {
                "status": "success",
                "redirect_url": transaction['redirect_url'],
                "data": {"booking_id": booking.id, "status": "PAID"}
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Mode tidak valid. Gunakan 'simulasi' atau 'midtrans'")

# ============================================================
# ENDPOINTS TIKET & SCANNER VERIFIKASI
# ============================================================
@app.get("/api/tickets/my")
def get_my_tickets(
    current_user: models.UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    bookings = db.query(models.BookingModel).filter(
        models.BookingModel.user_id == current_user.id,
        models.BookingModel.status.in_(["PAID", "REDEEMED"])
    ).order_by(models.BookingModel.created_at.desc()).all()

    data = []
    for b in bookings:
        # Jika ticket_code belum ada (data lama), isi otomatis
        if not b.ticket_code:
            b.ticket_code = b.order_id or f"WPT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            db.commit()

        is_redeemed = (b.status == "REDEEMED")
        data.append({
            "id": b.id,
            "order_id": b.order_id or f"WPT-BK-{b.id}",
            "ticket_code": b.ticket_code,
            "nama": b.paket.nama if b.paket else "Tiket Wisata",
            "kategori": "PAKET",
            "tanggal_pakai": f"{b.tanggal_mulai}" + (f" s/d {b.tanggal_akhir}" if b.tanggal_akhir else ""),
            "tanggal_mulai": b.tanggal_mulai,
            "tanggal_akhir": b.tanggal_akhir,
            "qty": b.jumlah_orang,
            "total_harga": f"Rp {b.total_harga:,}".replace(",", "."),
            "total_harga_raw": b.total_harga,
            "status": "Terpakai" if is_redeemed else "Aktif",
            "status_code": b.status,
            "redeemed_at": b.redeemed_at.isoformat() if b.redeemed_at else None,
            "redeemed_by": b.redeemed_by,
            "nama_pemesan": b.user.nama_lengkap if b.user else current_user.nama_lengkap,
            "email_pemesan": b.user.email if b.user else current_user.email,
        })
    return {"status": "success", "data": data}

class TicketScanRequest(BaseModel):
    ticket_code: str

@app.post("/api/tickets/validate")
def validate_ticket(
    req: TicketScanRequest,
    db: Session = Depends(get_db)
):
    code = req.ticket_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Kode tiket tidak boleh kosong")

    booking = db.query(models.BookingModel).filter(
        (models.BookingModel.ticket_code == code) | (models.BookingModel.order_id == code)
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Kode tiket tidak ditemukan / tidak terdaftar!")

    if booking.status not in ["PAID", "REDEEMED"]:
        raise HTTPException(status_code=400, detail=f"Tiket berstatus {booking.status}, belum dibayar atau sudah dibatalkan")

    is_redeemed = (booking.status == "REDEEMED")
    return {
        "status": "success",
        "valid": not is_redeemed,
        "is_redeemed": is_redeemed,
        "message": "Tiket SUDAH DIGUNAKAN sebelumnya!" if is_redeemed else "Tiket VALID & siap ditukarkan",
        "data": {
            "id": booking.id,
            "order_id": booking.order_id,
            "ticket_code": booking.ticket_code or booking.order_id,
            "nama_paket": booking.paket.nama if booking.paket else "Paket Wisata",
            "nama_pemesan": booking.user.nama_lengkap if booking.user else "-",
            "email_pemesan": booking.user.email if booking.user else "-",
            "jumlah_orang": booking.jumlah_orang,
            "tanggal_pakai": f"{booking.tanggal_mulai}" + (f" s/d {booking.tanggal_akhir}" if booking.tanggal_akhir else ""),
            "status": "Terpakai" if is_redeemed else "Aktif",
            "redeemed_at": booking.redeemed_at.strftime("%d-%m-%Y %H:%M WIB") if booking.redeemed_at else None,
            "redeemed_by": booking.redeemed_by,
        }
    }

@app.post("/api/tickets/redeem")
def redeem_ticket(
    req: TicketScanRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    code = req.ticket_code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Kode tiket tidak boleh kosong")

    booking = db.query(models.BookingModel).filter(
        (models.BookingModel.ticket_code == code) | (models.BookingModel.order_id == code)
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Kode tiket tidak ditemukan!")

    if booking.status == "REDEEMED":
        tgl_redeem = booking.redeemed_at.strftime("%d-%m-%Y %H:%M WIB") if booking.redeemed_at else "sebelumnya"
        raise HTTPException(
            status_code=400, 
            detail=f"Tiket SUDAH DIGUNAKAN pada {tgl_redeem} oleh {booking.redeemed_by or 'Petugas'}!"
        )

    if booking.status != "PAID":
        raise HTTPException(status_code=400, detail=f"Tiket tidak dapat digunakan karena status: {booking.status}")

    # Ambil nama petugas jika mengirim Bearer token
    staff_user = get_optional_current_user(request, db)
    staff_name = staff_user.nama_lengkap if staff_user else "Petugas Loket Wapit"

    # Ubah status jadi REDEEMED
    booking.status = "REDEEMED"
    booking.redeemed_at = datetime.utcnow()
    booking.redeemed_by = staff_name
    db.commit()
    db.refresh(booking)

    return {
        "status": "success",
        "message": "Tiket BERHASIL diverifikasi & ditukarkan!",
        "data": {
            "id": booking.id,
            "order_id": booking.order_id,
            "ticket_code": booking.ticket_code or booking.order_id,
            "nama_paket": booking.paket.nama if booking.paket else "Paket Wisata",
            "nama_pemesan": booking.user.nama_lengkap if booking.user else "-",
            "jumlah_orang": booking.jumlah_orang,
            "tanggal_pakai": f"{booking.tanggal_mulai}" + (f" s/d {booking.tanggal_akhir}" if booking.tanggal_akhir else ""),
            "status": "Terpakai",
            "redeemed_at": booking.redeemed_at.strftime("%d-%m-%Y %H:%M WIB"),
            "redeemed_by": booking.redeemed_by,
        }
    }