from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nama_lengkap = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    foto_profil = Column(Text, nullable=True)
    google_sub = Column(String, nullable=True)
    facebook_id = Column(String, nullable=True)
    role = Column(String, default="user")
    referral_code = Column(String, unique=True, nullable=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)

class DestinasiModel(Base):
    __tablename__ = "destinasi"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    kategori = Column(String)
    
    # --- 3 KOLOM BARU YANG SEBELUMNYA HILANG ---
    deskripsi_pendek = Column(String)
    deskripsi_panjang = Column(Text)
    image = Column(String)
    # ------------------------------------------
    
    # Jarak dan ketinggian bisa dibiarkan atau dihapus jika sudah tidak dipakai
    jarak = Column(String, nullable=True) 
    ketinggian = Column(String, nullable=True)

class UlasanModel(Base):
    __tablename__ = "ulasan"
    id = Column(Integer, primary_key=True, index=True)
    destinasi_id = Column(Integer, ForeignKey("destinasi.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1 - 5
    ulasan = Column(Text, nullable=True)
    foto = Column(Text, nullable=True)
    balasan = Column(Text, nullable=True)
    balasan_at = Column(DateTime, nullable=True)
    balasan_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('destinasi_id', 'user_id', name='uq_destinasi_user_ulasan'),
    )

    user = relationship("UserModel", backref="ulasan_list")
    destinasi = relationship("DestinasiModel", backref="ulasan_list")

class PaketModel(Base):
    __tablename__ = "paket"
    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String, index=True)
    harga = Column(Integer)
    fasilitas = Column(Text)

class KulinerModel(Base):
    __tablename__ = "kuliner"
    id = Column(Integer, primary_key=True, index=True)
    kedai = Column(String, index=True)
    kategori = Column(String, index=True)
    nama_menu = Column(String)
    deskripsi = Column(String, nullable=True)
    harga = Column(Integer)

class LayananUmumModel(Base):
    __tablename__ = "layanan_umum"
    id = Column(Integer, primary_key=True, index=True)
    nama_layanan = Column(String)
    kontak = Column(String)
    deskripsi = Column(Text, nullable=True)

class VoucherModel(Base):
    __tablename__ = "voucher"
    id          = Column(Integer, primary_key=True, index=True)
    kode        = Column(String, unique=True, index=True, nullable=False)
    tipe        = Column(String, nullable=False)   # "persen" | "nominal"
    nilai       = Column(Integer, nullable=False)  # 10 (persen) atau 20000 (nominal)
    maks_diskon = Column(Integer, nullable=True)   # cap diskon untuk tipe persen
    kuota       = Column(Integer, default=100)
    terpakai    = Column(Integer, default=0)
    aktif       = Column(Integer, default=1)       # 1=aktif, 0=nonaktif
    created_at  = Column(DateTime, default=datetime.utcnow)

class BookingModel(Base):
    __tablename__ = "booking"
    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paket_id       = Column(Integer, ForeignKey("paket.id"), nullable=False)
    tanggal_mulai  = Column(String, nullable=False)   # YYYY-MM-DD
    tanggal_akhir  = Column(String, nullable=True)    # null untuk Gold/Silver
    jumlah_orang   = Column(Integer, nullable=False)
    malam_tambahan = Column(Integer, default=0)
    voucher_id     = Column(Integer, ForeignKey("voucher.id"), nullable=True)
    subtotal       = Column(Integer, nullable=False)
    diskon         = Column(Integer, default=0)
    total_harga    = Column(Integer, nullable=False)
    status         = Column(String, default="PENDING")  # PENDING|PAID|REDEEMED|CANCELLED|EXPIRED
    order_id       = Column(String, nullable=True)
    ticket_code    = Column(String, unique=True, index=True, nullable=True)
    redeemed_at    = Column(DateTime, nullable=True)
    redeemed_by    = Column(String, nullable=True)
    expires_at     = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    user    = relationship("UserModel", backref="bookings")
    paket   = relationship("PaketModel", backref="bookings")
    voucher = relationship("VoucherModel", backref="bookings")

class PesanModel(Base):
    __tablename__ = "pesan"
    id = Column(Integer, primary_key=True, index=True)
    nama = Column(String, nullable=False)
    email = Column(String, nullable=False)
    isi_pesan = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ReferralConfigModel(Base):
    __tablename__ = "referral_config"
    id                    = Column(Integer, primary_key=True)
    reward_referee_type   = Column(String, default="persen")
    reward_referee_nilai  = Column(Integer, default=10)
    reward_referrer_type  = Column(String, default="persen")
    reward_referrer_nilai = Column(Integer, default=10)
    max_penggunaan        = Column(Integer, default=0)