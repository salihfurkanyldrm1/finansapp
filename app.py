import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import tempfile
import json
import hashlib
import re

# =============================
# 🔧 Firebase Bağlantısı (secrets ile)
# =============================
if not firebase_admin._apps:
    firebase_json = st.secrets["firebase"]["key"]
    # Eğer secrets'ta \\n gibi kaçışlar varsa düzelt:
    firebase_json = firebase_json.replace("\\n", "\n")
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        f.write(firebase_json)
        f.flush()
        cred = credentials.Certificate(f.name)

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://finansapp-47c29-default-rtdb.europe-west1.firebasedatabase.app/"
    })

# =============================
# 👥 Basit kullanıcı adı + şifre auth (sidebar)
# =============================
def sanitize_username(u: str) -> str:
    # DB key olarak güvenli hale getir: boşlukları ve nokta gibi karakterleri alt çizgiye çevir
    u = u.strip()
    u = re.sub(r"[^\w\-]", "_", u)  # sadece harf/ sayı / altçizgi / tire bırak
    return u

if "user" not in st.session_state:
    st.session_state["user"] = None

with st.sidebar:
    st.header("Giriş / Kayıt")
    mode = st.radio("İşlem:", ["Giriş Yap", "Kayıt Ol"])
    input_username = st.text_input("Kullanıcı adı", placeholder="örnek: salih123")
    input_password = st.text_input("Şifre", type="password")
    if st.button("Devam"):
        if not input_username or not input_password:
            st.warning("Kullanıcı adı ve şifre girin.")
        else:
            username_key = sanitize_username(input_username)
            auth_ref = db.reference(f"auth/{username_key}")
            stored = auth_ref.get()
            hashed = hashlib.sha256(input_password.encode("utf-8")).hexdigest()

            if mode == "Kayıt Ol":
                if stored:
                    st.error("Bu kullanıcı adı zaten alınmış. Başka bir isim deneyin.")
                else:
                    # Yeni kullanıcı oluştur
                    auth_ref.set({"password": hashed})
                    st.success("Kayıt başarılı — giriş yapabilirsiniz.")
            else:  # Giriş Yap
                if not stored:
                    st.error("Böyle bir kullanıcı bulunamadı. Kayıt olun.")
                elif stored.get("password") != hashed:
                    st.error("Şifre hatalı.")
                else:
                    st.success("Giriş başarılı! Hoş geldin, " + input_username)
                    st.session_state["user"] = username_key

    if st.session_state["user"]:
        st.write(f"**Girişli:** {st.session_state['user']}")
        if st.button("Çıkış Yap"):
            st.session_state["user"] = None
            st.experimental_rerun()
    st.markdown("---")
    st.caption("Not: Kullanıcı adı yalnızca harf/sayı/_/- içerebilir; nokta/boşluklar '_' ile değiştirilecektir.")

# Eğer kullanıcı henüz giriş yapmadıysa ana UI'yi gösterme
if not st.session_state["user"]:
    st.info("Devam etmek için sidebar'dan giriş yapın veya kayıt olun.")
    st.stop()

# >= buradan itibaren kullanıcı girişli
kullanici = st.session_state["user"]
user_ref = db.reference(f"kullanicilar/{kullanici}")

# =============================
# 📊 Veri Yükleme
# =============================
veri = user_ref.get()
df = pd.DataFrame(veri) if veri else pd.DataFrame(columns=["Tarih", "Tür", "Kategori", "Tutar", "Gider Türü"])

# =============================
# 📝 Yeni Kayıt Ekleme
# =============================
st.title("💸 Kişisel Finans Takip Uygulaması")
st.write(f"Girişli kullanıcı: **{kullanici}**")

st.header("📝 Yeni Kayıt Ekle")
tur = st.radio("Tür seçin:", ["Gelir", "Gider"], horizontal=True)

if tur == "Gelir":
    kategori = st.selectbox("Kategori seçin:", ["Maaş", "Ek Gelir", "Yatırım", "Diğer"])
    gider_turu = "-" 
else:
    kategori = st.selectbox("Kategori seçin:", ["Market", "Fatura", "Kişisel Bakım", "Ulaşım", "Eğitim", "Sağlık", "Cafe/Restaurant", "Diğer"])
    gider_turu = st.radio("Gider türü seçin:", ["Zorunlu", "Keyfi"])

tutar = st.number_input("Tutar (₺)", min_value=0.0, step=10.0)

if st.button("💾 Kaydı Ekle"):
    yeni_kayit = {
        "Tarih": datetime.now().strftime("%Y-%m-%d"),
        "Tür": tur,
        "Kategori": kategori,
        "Tutar": tutar,
        "Gider Türü": gider_turu
    }
    kayitlar = df.to_dict(orient="records") if not df.empty else []
    kayitlar.append(yeni_kayit)
    user_ref.set(kayitlar)
    st.success("✅ Kayıt başarıyla eklendi!")
    st.experimental_rerun()

# =============================
# 📋 Kayıtları Göster
# =============================
st.header("📊 Kayıtlar")
if not df.empty:
    st.dataframe(df)
else:
    st.info("Henüz kayıt yok.")

# =============================
# 🗑️ Kayıt Silme
# =============================
st.subheader("🗑️ Kayıt Sil")
if not df.empty:
    secilen_index = st.selectbox("Silmek istediğiniz kayıt numarasını seçin:", df.index)
    if st.button("❌ Kaydı Sil"):
        df = df.drop(secilen_index).reset_index(drop=True)
        user_ref.set(df.to_dict(orient="records"))
        st.success("🧹 Kayıt başarıyla silindi!")
        st.experimental_rerun()

# =============================
# 📈 Anlık Analiz
# =============================
st.header("📈 Anlık Finans Analizi")
if not df.empty:
    df["Tutar"] = pd.to_numeric(df["Tutar"], errors="coerce").fillna(0)
    toplam_gelir = df[df["Tür"]=="Gelir"]["Tutar"].sum()
    toplam_gider = df[df["Tür"]=="Gider"]["Tutar"].sum()
    bakiye = toplam_gelir - toplam_gider

    zorunlu_gider = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="Zorunlu")]["Tutar"].sum()
    keyfi_gider = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="Keyfi")]["Tutar"].sum()

    st.metric("Toplam Gelir", f"{toplam_gelir:.2f} ₺")
    st.metric("Toplam Gider", f"{toplam_gider:.2f} ₺")
    st.metric("Kalan Bakiye", f"{bakiye:.2f} ₺")

    # Pie chart sadece gider varsa göster
    if toplam_gider > 0:
        gider_turleri = {"Zorunlu": zorunlu_gider, "Keyfi": keyfi_gider}
        plt.figure(figsize=(5,5))
        plt.pie(gider_turleri.values(), labels=gider_turleri.keys(), autopct="%1.1f%%")
        st.pyplot(plt)
    else:
        st.info("Henüz gider kaydı yok. Pie chart için veri bekleniyor.")

    # Son 30 günlük gelir/gider grafiği
    df["Tarih"] = pd.to_datetime(df["Tarih"])
    son_30gun = datetime.now() - timedelta(days=30)
    son_kayitlar = df[df["Tarih"] >= son_30gun]
    if not son_kayitlar.empty:
        gunluk_toplam = son_kayitlar.groupby(["Tarih","Tür"])["Tutar"].sum().unstack().fillna(0)
        st.write("Son 30 Günlük Gelir/Gider Grafiği:")
        st.line_chart(gunluk_toplam)
    else:
        st.info("Son 30 gün için yeterli veri yok.")
else:
    st.info("Analiz için yeterli veri bulunamadı.")
