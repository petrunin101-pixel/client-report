
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from pathlib import Path

st.set_page_config(page_title="Client Traffic & Sales Report", layout="wide")

st.title("📊 Клиентский отчёт: трафик, воронка, ROAS")

# --- Data loading helpers ---
@st.cache_data
def load_ods(path: str, sheet: int | str = 0) -> pd.DataFrame:
    return pd.read_excel(path, engine="odf", sheet_name=sheet)

@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def read_data(uploaded_file: BytesIO | None) -> pd.DataFrame:
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix == ".ods":
            df_raw = pd.read_excel(uploaded_file, engine="odf", sheet_name=0)
        elif suffix == ".csv":
            df_raw = pd.read_csv(uploaded_file)
        elif suffix in (".xlsx", ".xls"):
            df_raw = pd.read_excel(uploaded_file, sheet_name=0)
        else:
            st.error("Поддерживаются файлы: .ods, .xlsx, .xls, .csv")
            st.stop()
    else:
        # fallback: ожидаем файл в репозитории
        # data/report.ods или data/report.csv
        if Path("data/report.ods").exists():
            df_raw = load_ods("data/report.ods", 0)
        elif Path("data/report.csv").exists():
            df_raw = load_csv("data/report.csv")
        else:
            st.warning("Загрузите файл (.ods/.xlsx/.csv) с таблицей (как в вашем примере).")
            st.stop()
    return df_raw

uploaded = st.file_uploader("Загрузите файл данных (.ods/.xlsx/.csv). Если не загрузить — будет использован файл из папки data/", type=["ods","xlsx","xls","csv"])
df_raw = read_data(uploaded)

# --- Extract columns exactly like in your ODS layout ---
# A: Месяц; B: Google клики; C: Google CPC; D: Google Затраты; E: Google Показы
# F: eBay клики; G: eBay Показы; H: eBay Покупки; I: eBay Затраты
# J: Добавление в корзину; K: Покупки; L: Ценность покупок
# M: SEO клики; N: SEO показы; O: SEO позиция

# guard on header row: row 0 is headers, start from row 1
months = df_raw.iloc[1:, 0].reset_index(drop=True).astype(str)

def num(col_idx):
    return pd.to_numeric(df_raw.iloc[1:, col_idx].reset_index(drop=True), errors="coerce")

g_clicks = num(1)
g_cpc    = num(2)
g_cost   = num(3)
g_impr   = num(4)

eb_clicks = num(5)
eb_impr   = num(6)
eb_orders = num(7)
eb_cost   = num(8)

cart_adds = num(9)
orders    = num(10)
revenue   = num(11)

seo_clicks = num(12)
seo_impr   = num(13)
seo_pos    = num(14)

# Combined frame
df = pd.DataFrame({
    "Месяц": months,
    "Google_Клики": g_clicks,
    "Google_CPC": g_cpc,
    "Google_Затраты": g_cost,
    "Google_Показы": g_impr,
    "eBay_Клики": eb_clicks,
    "eBay_Показы": eb_impr,
    "eBay_Покупки": eb_orders,
    "eBay_Затраты": eb_cost,
    "Добавления_в_корзину": cart_adds,
    "Сайт_Покупки": orders,
    "Ценность_покупок": revenue,
    "SEO_Клики": seo_clicks,
    "SEO_Показы": seo_impr,
    "SEO_Позиция": seo_pos
})

# Derived metrics
df["Все_клики"] = df[["Google_Клики","eBay_Клики","SEO_Клики"]].sum(axis=1, skipna=True)

# CTR
df["CTR_Google"] = (df["Google_Клики"]/df["Google_Показы"]*100)
df["CTR_eBay"]   = (df["eBay_Клики"]/df["eBay_Показы"]*100)
df["CTR_SEO"]    = (df["SEO_Клики"]/df["SEO_Показы"]*100)

# CR
df["CR_Корзина"] = (df["Добавления_в_корзину"]/df["Все_клики"]*100)
df["CR_Покупка"] = (df["Сайт_Покупки"]/df["Все_клики"]*100)
df["CR_Оплата_от_корзины"] = (df["Сайт_Покупки"]/df["Добавления_в_корзину"]*100)

# ROAS/CPA (Google)
df["ROAS_Google_%"] = (df["Ценность_покупок"]/df["Google_Затраты"]*100)
df["CPA_Google"] = (df["Google_Затраты"]/df["Сайт_Покупки"])
# ROAS/CPA (eBay) — если есть затраты и покупки
df["ROAS_eBay_%"] = (df["Ценность_покупок"]/df["eBay_Затраты"]*100)
df["CPA_eBay"]    = (df["eBay_Затраты"]/df["eBay_Покупки"])

# --- Layout ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Клики по источникам",
    "Воронки",
    "CTR / CR",
    "ROAS / CPA",
    "Заказы и выручка"
])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Google — клики по месяцам")
        fig, ax = plt.subplots(figsize=(7,4))
        ax.plot(df["Месяц"], df["Google_Клики"], marker="o")
        ax.set_ylabel("Клики")
        ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig)
    with col2:
        st.subheader("eBay и SEO — клики по месяцам")
        fig, ax = plt.subplots(figsize=(7,4))
        ax.plot(df["Месяц"], df["eBay_Клики"], marker="o", label="eBay")
        ax.plot(df["Месяц"], df["SEO_Клики"], marker="o", label="SEO")
        ax.legend()
        ax.set_ylabel("Клики")
        ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig)

with tab2:
    st.subheader("Воронка Google+SEO (логарифмическая шкала)")
    gseo_shows = (df["Google_Показы"].sum(skipna=True) + df["SEO_Показы"].sum(skipna=True))
    gseo_clicks = (df["Google_Клики"].sum(skipna=True) + df["SEO_Клики"].sum(skipna=True))
    gseo_cart = df["Добавления_в_корзину"].sum(skipna=True)
    gseo_orders = df["Сайт_Покупки"].sum(skipna=True)

    stages_g = ["Показы","Клики","Корзина","Покупки"]
    values_g = [gseo_shows, gseo_clicks, gseo_cart, gseo_orders]
    conv_g = [100]
    conv_g += [round(gseo_clicks/gseo_shows*100,2) if gseo_shows else 0]
    conv_g += [round(gseo_cart/gseo_clicks*100,2) if gseo_clicks else 0]
    conv_g += [round(gseo_orders/gseo_cart*100,2) if gseo_cart else 0]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.barh(stages_g[::-1], values_g[::-1])
    ax.set_xscale("log")
    for i,(val,pct) in enumerate(zip(values_g[::-1], conv_g[::-1])):
        ax.text(val*1.1 if val>0 else 1, i, f"{int(val)} ({pct}%)", va="center")
    st.pyplot(fig)

    st.subheader("Воронка eBay (логарифмическая шкала)")
    ebay_shows = df["eBay_Показы"].sum(skipna=True)
    ebay_clicks = df["eBay_Клики"].sum(skipna=True)
    ebay_orders = df["eBay_Покупки"].sum(skipna=True)

    stages_e = ["Показы","Клики","Покупки"]
    values_e = [ebay_shows, ebay_clicks, ebay_orders]
    conv_e = [100]
    conv_e += [round(ebay_clicks/ebay_shows*100,2) if ebay_shows else 0]
    conv_e += [round(ebay_orders/ebay_clicks*100,2) if ebay_clicks else 0]

    fig, ax = plt.subplots(figsize=(10,4))
    ax.barh(stages_e[::-1], values_e[::-1], color="orange")
    ax.set_xscale("log")
    for i,(val,pct) in enumerate(zip(values_e[::-1], conv_e[::-1])):
        ax.text(val*1.1 if val>0 else 1, i, f"{int(val)} ({pct}%)", va="center")
    st.pyplot(fig)

with tab3:
    st.subheader("CTR по источникам (%)")
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df["Месяц"], df["CTR_Google"], marker="o", label="Google")
    ax.plot(df["Месяц"], df["CTR_eBay"], marker="o", label="eBay")
    ax.plot(df["Месяц"], df["CTR_SEO"], marker="o", label="SEO")
    ax.legend()
    ax.set_ylabel("CTR %")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

    st.subheader("CR сайта (%)")
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df["Месяц"], df["CR_Корзина"], marker="o", label="в корзину от кликов")
    ax.plot(df["Месяц"], df["CR_Покупка"], marker="o", label="покупка от кликов")
    ax.plot(df["Месяц"], df["CR_Оплата_от_корзины"], marker="o", label="покупка от корзины")
    ax.legend()
    ax.set_ylabel("CR %")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

with tab4:
    st.subheader("ROAS по Google Ads (%)")
    fig, ax = plt.subplots(figsize=(10,4))
    roas = df["ROAS_Google_%"]
    ax.plot(df["Месяц"], roas, marker="o", color="green", label="ROAS Google")
    mean_roas = roas.mean(skipna=True)
    ax.axhline(mean_roas, color="red", linestyle="--", label=f"Средний ROAS: {mean_roas:.1f}%")
    ax.axhline(100, color="gray", linestyle=":", label="100% — точка безубыточности")
    for x, y in zip(df["Месяц"], roas):
        if pd.notna(y):
            ax.text(x, y, f"{y:.1f}%", ha="center", va="bottom", fontsize=8)
    ax.legend()
    ax.set_ylabel("ROAS %")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

    st.subheader("CPA (стоимость заказа)")
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df["Месяц"], df["CPA_Google"], marker="o", label="CPA Google", linestyle="--")
    ax.plot(df["Месяц"], df["CPA_eBay"], marker="o", label="CPA eBay", linestyle="--")
    ax.legend()
    ax.set_ylabel("€ за заказ")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)

with tab5:
    st.subheader("Динамика заказов и выручки")
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df["Месяц"], df["Сайт_Покупки"], marker="o", label="Заказы (покупки)")
    ax2 = ax.twinx()
    ax2.plot(df["Месяц"], df["Ценность_покупок"], marker="o", color="green", label="Выручка (€)")
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("Заказы")
    ax2.set_ylabel("€")
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.93))
    st.pyplot(fig)

st.caption("Источник данных: tabular report (.ods/.xlsx/.csv). Графики — matplotlib.")
