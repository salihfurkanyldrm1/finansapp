import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, db
import tempfile
import hashlib
import json

# =============================
# 🔧 Firebase Bağlantısı (TOML uyumlu hale getirildi)
# =============================
if not firebase_admin._apps:
    # Firebase verisini dict olarak al
    firebase_data = dict(st.secrets["firebase"])

    # JSON olarak geçici dosyaya yaz
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(firebase_data, f)
        f.flush()
        cred = credentials.Certificate(f.name)

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://finansapp-47c29-default-rtdb.europe-west1.firebasedatabase.app/"
    })

# =============================
# 🔐 Basit Kullanıcı Doğrulama Yardımcıları
# =============================
def hash_password(password: str, username: str) -> str:
    return hashlib.sha256((password + username).encode("utf-8")).hexdigest()

def get_cred_ref(username: str):
    return db.reference(f"kullanici_creds/{username}")

def signup_user(username: str, password: str) -> (bool, str):
    cred_ref = get_cred_ref(username)
    if cred_ref.get() is not None:
        return False, "Bu kullanıcı adı zaten alınmış. Farklı bir kullanıcı adı seçin."
    hashed = hash_password(password, username)
    cred_ref.set({"password_hash": hashed, "created_at": datetime.now().isoformat()})
    return True, "Hesap başarıyla oluşturuldu. Giriş yapabilirsiniz."

def signin_user(username: str, password: str) -> (bool, str):
    cred_ref = get_cred_ref(username)
    data = cred_ref.get()
    if data is None:
        return False, "Kullanıcı bulunamadı. Önce kayıt olun."
    hashed = hash_password(password, username)
    if hashed != data.get("password_hash"):
        return False, "Şifre hatalı."
    return True, "Giriş başarılı."

# =============================
# 🧾 Oturum Yönetimi
# =============================
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user" not in st.session_state:
    st.session_state["user"] = None
if "auth_message" not in st.session_state:
    st.session_state["auth_message"] = ""

# =============================
# 🔐 Giriş / Kayıt Arayüzü
# =============================
st.title("💸 Kişisel Finans Takip Uygulaması")
st.write("Her kullanıcı kendi verilerini görür, tüm kayıtlar bulutta saklanır ☁️")

if not st.session_state["logged_in"]:
    st.subheader("Giriş Yap / Kayıt Ol")
    col1, col2 = st.columns(2)
    with col1:
        kullanici_input = st.text_input("Kullanıcı adı:", key="login_user")
    with col2:
        sifre_input = st.text_input("Şifre:", type="password", key="login_pass")

    signup_checkbox = st.checkbox("Yeni hesap oluşturmak istiyorum", key="signup_option")

    if st.button("Giriş") or st.button("Tamamla"):
        if not kullanici_input or not sifre_input:
            st.warning("Kullanıcı adı ve şifre girin.")
        else:
            if signup_checkbox:
                ok, msg = signup_user(kullanici_input.strip(), sifre_input)
                st.session_state["auth_message"] = msg
                if ok:
                    st.success(msg)
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = kullanici_input.strip()
                    st.experimental_rerun()
                else:
                    st.error(msg)
            else:
                ok, msg = signin_user(kullanici_input.strip(), sifre_input)
                st.session_state["auth_message"] = msg
                if ok:
                    st.success(msg)
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = kullanici_input.strip()
                    st.experimental_rerun()
                else:
                    st.error(msg)

    if st.session_state["auth_message"]:
        st.info(st.session_state["auth_message"])

    st.stop()

# =============================
# Oturum açılmış: devam
# =============================
kullanici = st.session_state["user"]
st.sidebar.markdown(f"**Giriş yapan:** {kullanici}")
if st.sidebar.button("Çıkış Yap"):
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.experimental_rerun()

# =============================
# 🔁 Kullanıcı verisi referansı
# =============================
user_ref = db.reference(f"kullanicilar/{kullanici}")

# =============================
# 📊 Veri Yükleme
# =============================
veri = user_ref.get()
df = pd.DataFrame(veri) if veri else pd.DataFrame(columns=["Tarih", "Tür", "Kategori", "Tutar", "Gider Türü"])

# =============================
# 📝 Yeni Kayıt Ekleme
# =============================
st.header("📝 Yeni Kayıt Ekle")

tur = st.radio("Tür seçin:", ["Gelir", "Gider"], horizontal=True)

if tur == "Gelir":
    kategori = st.selectbox("Kategori seçin:", ["Maaş", "Ek Gelir", "Yatırım", "Diğer"])
    gider_turu = "-"
else:
    kategori = st.selectbox("Kategori seçin:", ["Market", "Fatura", "Kişisel Bakım","Kredi","Ulaşım", "Eğitim", "Sağlık", "Cafe/Restaurant", "Diğer"])
    gider_turu = st.radio("Gider türü seçin:", ["İhtiyaç", "İstek"])

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
    st.rerun()

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
        st.rerun()

# =============================
# 📈 Anlık Analiz
# =============================
st.header("📈 Anlık Finans Analizi")
if not df.empty:
    df["Tutar"] = pd.to_numeric(df["Tutar"], errors="coerce").fillna(0)
    toplam_gelir = df[df["Tür"]=="Gelir"]["Tutar"].sum()
    toplam_gider = df[df["Tür"]=="Gider"]["Tutar"].sum()
    bakiye = toplam_gelir - toplam_gider

    # Düzeltilmiş değişken isimleri
    ihtiyac_gider = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="İhtiyaç")]["Tutar"].sum()
    istek_gider = df[(df["Tür"]=="Gider") & (df["Gider Türü"]=="İstek")]["Tutar"].sum()

    st.metric("Toplam Gelir", f"{toplam_gelir:.2f} ₺")
    st.metric("Toplam Gider", f"{toplam_gider:.2f} ₺")
    st.metric("Kalan Bakiye", f"{bakiye:.2f} ₺")

    st.write("İhtiyaç ve İstek Gider Dağılımı:")
    gider_turleri = {"İhtiyaç": ihtiyac_gider, "İstek": istek_gider}

    if toplam_gider > 0:
        plt.figure(figsize=(5,5))
        plt.pie(gider_turleri.values(), labels=gider_turleri.keys(), autopct="%1.1f%%")
        st.pyplot(plt)
        plt.close()
    else:
        st.info("Henüz gider kaydı yok. Pie chart için veri bekleniyor.")

    # Son 30 günlük gelir/gider grafiği
    df["Tarih"] = pd.to_datetime(df["Tarih"])
    son_30gun = datetime.now() - timedelta(days=30)
    son_kayitlar = df[df["Tarih"] >= son_30gun]
    gunluk_toplam = son_kayitlar.groupby(["Tarih","Tür"])["Tutar"].sum().unstack().fillna(0)
    st.write("Son 30 Günlük Gelir/Gider Grafiği:")
    st.line_chart(gunluk_toplam)
else:
    st.info("Analiz için yeterli veri bulunamadı.")
