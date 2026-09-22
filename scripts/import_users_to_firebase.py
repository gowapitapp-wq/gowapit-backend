#!/usr/bin/env python3
"""
Skrip Migrasi User Lama ke Firebase Authentication (Spark Tier)
----------------------------------------------------------------
Aturan selektif per baris:
1. Pure email/password (tanpa google_sub, tanpa facebook_id):
   -> Diimpor passwordless dengan email_verified=True.
2. User google_sub:
   -> DILEWATKAN (Google login di aplikasi akan membuat akun Google-linked;
      backend /api/auth/firebase otomatis menautkan ke baris lama via email_verified=true).
3. User facebook_id:
   -> Diimpor passwordless (provider FB sudah dinonaktifkan; user dapat gunakan "Lupa Password").
4. Akun seed admin (admin@gowapit.com) & petugas (petugas@gowapit.com):
   -> Diimpor passwordless lalu di-update password sementara via auth.update_user(...)
      dari env ADMIN_TEMP_PASSWORD / PETUGAS_TEMP_PASSWORD (panjang >= 6 karakter).
      Password tidak pernah dicetak ke log dan env di-unset setelah selesai.
5. Skip baris yang sudah memiliki firebase_uid (idempoten).
6. Baris tanpa email / email kosong dilewati dan dilaporkan.

Penggunaan:
  python scripts/import_users_to_firebase.py --dry-run
  python scripts/import_users_to_firebase.py
"""

import os
import sys
import argparse
import uuid
import json
from typing import List, Dict, Any, Optional

# Tambahkan direktori parent ke sys.path agar models & database bisa diimpor
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import models
from database import SessionLocal, engine

try:
    import firebase_admin
    from firebase_admin import auth, credentials
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


def init_firebase_admin(dry_run: bool = False) -> bool:
    """Inisialisasi Firebase Admin SDK dari FIREBASE_SERVICE_ACCOUNT_JSON atau kredensial default."""
    if not FIREBASE_AVAILABLE:
        if dry_run:
            print("[INFO] firebase_admin belum terpasang/terinisialisasi, tetapi melanjutkan dalam mode --dry-run.")
            return False
        raise RuntimeError("Modul firebase-admin tidak ditemukan. Silakan pasang via pip install firebase-admin.")

    if firebase_admin._apps:
        return True

    sa_env = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_env:
        try:
            if os.path.isfile(sa_env):
                cred = credentials.Certificate(sa_env)
            else:
                sa_dict = json.loads(sa_env)
                cred = credentials.Certificate(sa_dict)
            firebase_admin.initialize_app(cred)
            print("[INFO] Firebase Admin SDK berhasil diinisialisasi menggunakan Service Account.")
            return True
        except Exception as e:
            if dry_run:
                print(f"[WARN] Gagal inisialisasi Firebase ({e}), mode dry-run tetap dilanjutkan.")
                return False
            raise RuntimeError(f"Gagal memuat FIREBASE_SERVICE_ACCOUNT_JSON: {e}")
    else:
        try:
            firebase_admin.initialize_app()
            print("[INFO] Firebase Admin SDK diinisialisasi dengan Default Credentials.")
            return True
        except Exception as e:
            if dry_run:
                print(f"[WARN] FIREBASE_SERVICE_ACCOUNT_JSON tidak ditemukan ({e}), mode dry-run tetap dilanjutkan.")
                return False
            raise RuntimeError("Environment variable FIREBASE_SERVICE_ACCOUNT_JSON wajib diisi untuk mode live import.")


def run_migration(dry_run: bool = False, batch_size: int = 1000):
    print("=" * 70)
    print(f" Memulai Migrasi User ke Firebase Auth {'(MODE DRY-RUN)' if dry_run else '(MODE LIVE)'}")
    print("=" * 70)

    fb_ready = init_firebase_admin(dry_run=dry_run)

    db = SessionLocal()
    try:
        users = db.query(models.UserModel).order_by(models.UserModel.id.asc()).all()
        total_scanned = len(users)
        print(f"[SCAN] Ditemukan {total_scanned} total user di database lokal.\n")

        skipped_already_migrated = []
        skipped_google_users = []
        skipped_no_email = []
        to_import = []  # list of dict: {"user": u, "uid": str, "email": str, "category": str}

        for u in users:
            # 1. Cek apakah sudah bermigrasi
            if u.firebase_uid and u.firebase_uid.strip():
                skipped_already_migrated.append((u.id, u.email, u.firebase_uid))
                continue

            # 2. Cek email valid
            if not u.email or not u.email.strip():
                skipped_no_email.append((u.id, u.nama_lengkap))
                continue

            email_norm = u.email.strip().lower()

            # 3. Cek user Google (dilewatkan untuk auto-link)
            if u.google_sub and u.google_sub.strip():
                skipped_google_users.append((u.id, email_norm, u.nama_lengkap))
                continue

            # 4. Akun yang akan diimpor (Pure Email atau Facebook)
            category = "Seed Admin" if email_norm == "admin@gowapit.com" else (
                "Seed Petugas" if email_norm == "petugas@gowapit.com" else (
                    "Facebook User" if u.facebook_id else "Pure Email/Password"
                )
            )

            # Generate random UID unik
            generated_uid = f"gowapit_{u.id}_{uuid.uuid4().hex[:12]}"
            to_import.append({
                "user": u,
                "uid": generated_uid,
                "email": email_norm,
                "display_name": u.nama_lengkap or "Pengguna GoWapit",
                "category": category,
            })

        # --- LAPORAN ANALISIS SELEKSI ---
        print("-" * 70)
        print(" LAPORAN ANALISIS SELEKSI PENGGUNA:")
        print(f"  • Sudah memiliki firebase_uid (Dilewati) : {len(skipped_already_migrated)}")
        print(f"  • Akun Google / google_sub (Dilewati)    : {len(skipped_google_users)}")
        print(f"  • Akun tanpa email valid (Dilewati)      : {len(skipped_no_email)}")
        print(f"  • Siap diimpor ke Firebase Auth          : {len(to_import)}")
        print("-" * 70)

        if skipped_google_users:
            print("\n[DAFTAR AKUN GOOGLE DILEWATKAN (Akan ditautkan otomatis saat login Google)]:")
            for uid_db, em, nm in skipped_google_users:
                print(f"  - ID: {uid_db:<4} | Email: {em:<35} | Nama: {nm}")

        if skipped_no_email:
            print("\n[PERINGATAN] AKUN TANPA EMAIL (Tidak dapat diimpor ke Firebase Auth):")
            for uid_db, nm in skipped_no_email:
                print(f"  - ID: {uid_db:<4} | Nama: {nm}")

        if not to_import:
            print("\n[SELESAI] Tidak ada pengguna baru yang perlu diimpor.")
            return

        print(f"\n[DAFTAR PENGGUNA AKAN DIIMPOR ({len(to_import)} Akun)]:")
        for idx, item in enumerate(to_import, 1):
            print(f"  {idx:>2}. ID: {item['user'].id:<4} | Email: {item['email']:<32} | Kategori: {item['category']:<18} | UID: {item['uid']}")

        # --- PROSES IMPORT PER BATCH (<= 1000) ---
        if dry_run:
            print("\n[DRY-RUN] Simulasi batching:")
            for i in range(0, len(to_import), batch_size):
                chunk = to_import[i:i + batch_size]
                print(f"  • Batch {i // batch_size + 1}: {len(chunk)} akun siap dikirim ke auth.import_users()")
            print("\n[DRY-RUN] Tidak ada perubahan data yang disimpan ke database ataupun Firebase.")
            return

        # LIVE IMPORT
        if not fb_ready:
            raise RuntimeError("Firebase Admin SDK belum siap untuk mode Live Import.")

        total_success = 0
        total_failed = 0
        imported_uids_map = {}  # email -> uid

        for i in range(0, len(to_import), batch_size):
            chunk = to_import[i:i + batch_size]
            print(f"\n[IMPORT] Memproses Batch {i // batch_size + 1} ({len(chunk)} akun)...")

            user_import_records = [
                auth.UserImportRecord(
                    uid=item["uid"],
                    email=item["email"],
                    display_name=item["display_name"],
                    email_verified=True
                )
                for item in chunk
            ]

            try:
                result = auth.import_users(user_import_records)
                error_indices = {err.index: err.reason for err in result.errors} if result.errors else {}

                for idx, item in enumerate(chunk):
                    if idx in error_indices:
                        print(f"  [GAGAL] User ID {item['user'].id} ({item['email']}): {error_indices[idx]}")
                        total_failed += 1
                    else:
                        # Backfill users.firebase_uid hanya untuk yang berhasil
                        item["user"].firebase_uid = item["uid"]
                        imported_uids_map[item["email"]] = item["uid"]
                        total_success += 1

                db.commit()
                print(f"  [SUKSES] Batch {i // batch_size + 1} selesai: {len(chunk) - len(error_indices)} berhasil, {len(error_indices)} gagal.")
            except Exception as e:
                db.rollback()
                print(f"  [ERROR] Gagal memproses batch {i // batch_size + 1}: {e}")
                raise

        # --- UPDATE TEMPORARY PASSWORD UNTUK SEED ADMIN / PETUGAS ---
        print("\n" + "-" * 70)
        print(" MEMERIKSA PASSWORD SEMENTARA AKUN SEED:")
        admin_temp_pwd = os.environ.get("ADMIN_TEMP_PASSWORD")
        petugas_temp_pwd = os.environ.get("PETUGAS_TEMP_PASSWORD")

        # Admin Seed
        admin_uid = imported_uids_map.get("admin@gowapit.com")
        if not admin_uid:
            admin_u = db.query(models.UserModel).filter(models.UserModel.email == "admin@gowapit.com").first()
            admin_uid = admin_u.firebase_uid if admin_u else None

        if admin_uid:
            if admin_temp_pwd:
                if len(admin_temp_pwd) >= 6:
                    auth.update_user(admin_uid, password=admin_temp_pwd)
                    print("  [OK] Password sementara untuk admin@gowapit.com berhasil diatur.")
                else:
                    print("  [WARN] ADMIN_TEMP_PASSWORD terlalu pendek (minimal 6 karakter). Dilewati.")
            else:
                print("  [INFO] ADMIN_TEMP_PASSWORD tidak diset. Password admin tetap passwordless / gunakan Reset Password.")

        # Petugas Seed
        petugas_uid = imported_uids_map.get("petugas@gowapit.com")
        if not petugas_uid:
            petugas_u = db.query(models.UserModel).filter(models.UserModel.email == "petugas@gowapit.com").first()
            petugas_uid = petugas_u.firebase_uid if petugas_u else None

        if petugas_uid:
            if petugas_temp_pwd:
                if len(petugas_temp_pwd) >= 6:
                    auth.update_user(petugas_uid, password=petugas_temp_pwd)
                    print("  [OK] Password sementara untuk petugas@gowapit.com berhasil diatur.")
                else:
                    print("  [WARN] PETUGAS_TEMP_PASSWORD terlalu pendek (minimal 6 karakter). Dilewati.")
            else:
                print("  [INFO] PETUGAS_TEMP_PASSWORD tidak diset. Password petugas tetap passwordless / gunakan Reset Password.")

        # Unset env vars dari memori untuk keamanan
        os.environ.pop("ADMIN_TEMP_PASSWORD", None)
        os.environ.pop("PETUGAS_TEMP_PASSWORD", None)

        print("-" * 70)
        print(f"\n[HASIL AKHIR MIGRASI]:")
        print(f"  • Total Diproses : {len(to_import)}")
        print(f"  • Berhasil       : {total_success}")
        print(f"  • Gagal          : {total_failed}")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrasi user lama GoWapit ke Firebase Authentication")
    parser.add_argument("--dry-run", action="store_true", help="Jalankan simulasi tanpa mengubah DB atau Firebase Auth")
    parser.add_argument("--batch-size", type=int, default=1000, help="Jumlah record per batch import (maks 1000)")
    args = parser.parse_args()

    run_migration(dry_run=args.dry_run, batch_size=args.batch_size)
