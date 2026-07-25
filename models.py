from sqlalchemy import Column, Integer, String, Text
from database import Base

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    nama_lengkap = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)

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