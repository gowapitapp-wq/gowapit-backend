import os
from datetime import datetime, timedelta, timezone
import uuid
import jwt
import requests
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
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
                image="Makam Ki Jumprit.jpeg"
            ),
            models.DestinasiModel(
                name="Hutan Pinus Umbul Jumprit", 
                kategori="Alam", 
                deskripsi_pendek="Kawasan hutan asri di kaki Gunung Sindoro yang sejuk dengan jajaran pinus menjulang tinggi.", 
                deskripsi_panjang="Terhampar indah di kaki Gunung Sindoro dengan jajaran pohon pinus yang menjulang tinggi kokoh. Menyuguhkan panorama alam yang asri, berudara sejuk, dan menyegarkan pikiran.", 
                image="Hutan Pinus.jpeg"
            ),
            models.DestinasiModel(
                name="Mata Air Umbul Jumprit", 
                kategori="Alam", 
                deskripsi_pendek="Sumber mata air abadi yang jernih, disucikan, dan menjadi hulu Sungai Progo.", 
                deskripsi_panjang="Sumber mata air abadi yang disucikan dan bernilai spiritual kuat. Airnya sangat jernih kebiruan, tidak pernah kering meski kemarau, dan menjadi hulu penting bagi Sungai Progo.", 
                image="Mata Air.jpeg"
            ),
            models.DestinasiModel(
                name="Interaksi dengan Monyet", 
                kategori="Satwa", 
                deskripsi_pendek="Pengalaman tak terlupakan berinteraksi langsung dengan kawanan kera ekor panjang yang ramah.", 
                deskripsi_panjang="Nikmati keseruan berinteraksi langsung dengan kawanan kera ekor panjang yang ramah. Kehadiran satwa eksotis ini menjadi daya tarik unik yang melengkapi petualangan Anda di hutan pinus.", 
                image="Interaksi dengan Monyet.jpg"
            ),
            models.DestinasiModel(
                name="Flying Fox Dewasa", 
                kategori="Wahana", 
                deskripsi_pendek="Wahana luncur gantung penantang adrenalin dengan pemandangan indah Hutan Pinus Wapit dari ketinggian.", 
                deskripsi_panjang="Pacu adrenalin Anda dengan meluncur di wahana Flying Fox! Rasakan sensasi mendebarkan yang membakar semangat sembari menikmati keindahan hijau Hutan Pinus Wapit dari ketinggian.", 
                image="Flying Fox.jpeg"
            ),
            models.DestinasiModel(
                name="Flying Fox Anak", 
                kategori="Wahana", 
                deskripsi_pendek="Area meluncur yang aman untuk melatih keberanian dan kemandirian si kecil.", 
                deskripsi_panjang="Wahana meluncur yang dirancang khusus dan aman untuk anak-anak. Pilihan sempurna untuk liburan keluarga yang berkesan sekaligus melatih keberanian serta kemandirian si kecil.", 
                image="Flying Fox Anak.jpeg"
            ),
            models.DestinasiModel(
                name="High Rope", 
                kategori="Wahana", 
                deskripsi_pendek="Uji keberanian dan keseimbangan di atas jembatan gantung tinggi yang memacu adrenalin.", 
                deskripsi_panjang="Uji mental, keseimbangan, dan ketangkasan Anda di wahana tali tinggi. Berjalan di atas jembatan gantung ketinggian akan memberikan sensasi liburan menantang yang memuaskan.", 
                image="High Rope.jpg"
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
    
    db.close()

@app.get("/")
def read_root():
    return {"status": "success", "message": "Selamat datang di GoWapit API!"}

@app.get("/api/destinasi")
def get_destinasi(db: Session = Depends(get_db)):
    wisata = db.query(models.DestinasiModel).all()
    return {"status": "success", "data": wisata}

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
            "email": user.email
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
            google_sub=google_sub
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
            "email": user.email
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

class UpdateProfileRequest(BaseModel):
    nama_lengkap: str = None
    foto_profil: str = None

@app.get("/api/users/me")
def get_user_profile(current_user: models.UserModel = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "nama_lengkap": current_user.nama_lengkap,
        "foto_profil": current_user.foto_profil or ""
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
    return {"status": "success", "data": data_paket}

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

# --- KONFIGURASI MIDTRANS & ENDPOINT CHECKOUT ---
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