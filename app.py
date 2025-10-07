import streamlit as st
import pandas as pd
import os

# ================== AYARLAR ==================
# Streamlit Cloud'da kalıcı veri için Google Sheets kullanabilirsiniz.
# Bunun için "App secrets" bölümüne ekleyin:
#   gcp_service_account_json = {...JSON içeriği...}
#   sheets_name = "buzdolabi_stok"
# Eğer Sheets ayarlamazsanız, uygulama geçici bellekte çalışır.

st.set_page_config(page_title="🧊 Buzdolabı Stok", layout="centered")


# ---------- Yardımcı Fonksiyonlar ----------
def _ensure_df_schema(df: pd.DataFrame) -> pd.DataFrame:
    if "Ürün" not in df.columns:
        df["Ürün"] = ""
    if "Miktar" not in df.columns:
        df["Miktar"] = 0
    df["Ürün"] = df["Ürün"].astype(str)
    df["Miktar"] = pd.to_numeric(df["Miktar"], errors="coerce").fillna(0).astype(int)
    df = df[df["Ürün"].str.strip() != ""]
    df = df.drop_duplicates(subset=["Ürün"], keep="last")
    return df.sort_values("Ürün").reset_index(drop=True)


def default_data():
    return pd.DataFrame([
        {"Ürün": "Süt", "Miktar": 1},
        {"Ürün": "Yumurta", "Miktar": 12},
        {"Ürün": "Tereyağı", "Miktar": 1},
        {"Ürün": "Peynir", "Miktar": 1},
        {"Ürün": "Sebzeler", "Miktar": 5},
        {"Ürün": "Yoğurt", "Miktar": 2},
        {"Ürün": "Meyve suyu", "Miktar": 1},
        {"Ürün": "Meyve", "Miktar": 4},
    ])


# ---------- Google Sheets Backend ----------
def _read_from_sheets() -> pd.DataFrame:
    try:
        import json, gspread
        from oauth2client.service_account import ServiceAccountCredentials

        creds_json = st.secrets["gcp_service_account_json"]
        sheets_name = st.secrets["sheets_name"]

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
        client = gspread.authorize(creds)
        ws = client.open(sheets_name).sheet1
        recs = ws.get_all_records()
        df = pd.DataFrame(recs)
        return _ensure_df_schema(df if not df.empty else default_data())
    except Exception as e:
        st.sidebar.warning("Sheets okunamadı, varsayılan veriye geçiliyor.\n" + str(e))
        return default_data()


def _write_to_sheets(df: pd.DataFrame):
    try:
        import json, gspread
        from oauth2client.service_account import ServiceAccountCredentials

        creds_json = st.secrets["gcp_service_account_json"]
        sheets_name = st.secrets["sheets_name"]

        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
        client = gspread.authorize(creds)
        ws = client.open(sheets_name).sheet1
        ws.clear()
        ws.update([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.sidebar.error("Sheets'e yazılamadı: " + str(e))


def load_data() -> pd.DataFrame:
    if "gcp_service_account_json" in st.secrets and "sheets_name" in st.secrets:
        return _read_from_sheets()
    return default_data()


def save_data(df: pd.DataFrame):
    if "gcp_service_account_json" in st.secrets and "sheets_name" in st.secrets:
        _write_to_sheets(df)


# ---------- State Init ----------
if "df" not in st.session_state:
    st.session_state.df = load_data()


# ================== Uygulama Arayüzü ==================
st.title("🧊 Kalıcı ve Online Buzdolabı Stok Takip")
st.caption("Satır içi düzenleme • Hızlı +/− • Arama & Preset butonlar • Google Sheets destekli")

# --- Arama & Kategori ---
st.subheader("🔎 Arama & Filtre")
col1, col2 = st.columns([2, 1])
with col1:
    q = st.text_input("Ürün ara", placeholder="örnek: süt, yumurta...")
with col2:
    kat = st.selectbox("Kategori", ["Tümü", "Süt/İçecek", "Kahvaltı", "Sebze/Meyve", "Diğer"], index=0)

kategori_map = {
    "Süt": "Süt/İçecek", "Meyve suyu": "Süt/İçecek",
    "Yoğurt": "Kahvaltı", "Peynir": "Kahvaltı", "Yumurta": "Kahvaltı",
    "Tereyağı": "Kahvaltı", "Sebzeler": "Sebze/Meyve", "Meyve": "Sebze/Meyve"
}

df = st.session_state.df.copy()
df["Kategori"] = df["Ürün"].map(kategori_map).fillna("Diğer")
if q:
    df = df[df["Ürün"].str.contains(q, case=False, na=False)]
if kat != "Tümü":
    df = df[df["Kategori"] == kat]
st.write(f"Bulunan ürün sayısı: **{len(df)}**")

# --- Satır içi düzenleme ---
st.subheader("📋 Stok Tablosu")
edited = st.data_editor(
    df[["Ürün", "Miktar"]].reset_index(drop=True),
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True
)
if not edited.equals(df[["Ürün", "Miktar"]].reset_index(drop=True)):
    st.session_state.df = _ensure_df_schema(edited.copy())
    save_data(st.session_state.df)
    st.success("Kaydedildi.")

st.divider()
st.subheader("⚡ Hızlı Güncelle (+/-)")
step = st.number_input("Varsayılan artış adımı", min_value=1, value=5)
for _, r in st.session_state.df.iterrows():
    urun, miktar = r["Ürün"], int(r["Miktar"])
    c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
    with c1:
        st.write(f"**{urun}**: {miktar}")
    with c2:
        if st.button("-1", key=f"dec_{urun}"):
            st.session_state.df.loc[st.session_state.df["Ürün"] == urun, "Miktar"] = max(0, miktar - 1)
            save_data(st.session_state.df)
            st.rerun()
    with c3:
        if st.button("+1", key=f"inc_{urun}"):
            st.session_state.df.loc[st.session_state.df["Ürün"] == urun, "Miktar"] = miktar + 1
            save_data(st.session_state.df)
            st.rerun()
    with c4:
        if st.button(f"+{step}", key=f"step_{urun}"):
            st.session_state.df.loc[st.session_state.df["Ürün"] == urun, "Miktar"] = miktar + step
            save_data(st.session_state.df)
            st.rerun()

st.divider()
st.subheader("🧩 Hızlı Ekleme Butonları")
presets = [("Süt", 1), ("Yumurta", 10), ("Yoğurt", 1), ("Peynir", 1), ("Meyve", 3)]
cols = st.columns(5)
for i, (ad, mikt) in enumerate(presets):
    if cols[i].button(f"{ad} (+{mikt})"):
        df0 = st.session_state.df.copy()
        if ad in df0["Ürün"].values:
            df0.loc[df0["Ürün"] == ad, "Miktar"] = df0.loc[df0["Ürün"] == ad, "Miktar"].astype(int) + mikt
        else:
            df0 = pd.concat([df0, pd.DataFrame([{"Ürün": ad, "Miktar": mikt}])], ignore_index=True)
        st.session_state.df = _ensure_df_schema(df0)
        save_data(st.session_state.df)
        st.rerun()

st.divider()
st.subheader("➕ Yeni Ürün Ekle")
colA, colB, colC = st.columns([3, 1, 1])
with colA:
    yeni = st.text_input("Ürün adı")
with colB:
    miktar = st.number_input("Miktar", min_value=0, value=1, step=1)
with colC:
    if st.button("Ekle"):
        if yeni.strip() == "":
            st.error("Lütfen ürün adı girin")
        else:
            df0 = st.session_state.df.copy()
            adt = yeni.strip().title()
            if adt in df0["Ürün"].values:
                df0.loc[df0["Ürün"] == adt, "Miktar"] = df0.loc[df0["Ürün"] == adt, "Miktar"].astype(int) + miktar
            else:
                df0 = pd.concat([df0, pd.DataFrame([{"Ürün": adt, "Miktar": miktar}])], ignore_index=True)
            st.session_state.df = _ensure_df_schema(df0)
            save_data(st.session_state.df)
            st.success(f"{adt} eklendi/güncellendi")
            st.rerun()
