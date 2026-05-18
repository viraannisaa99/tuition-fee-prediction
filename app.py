import base64
from html import escape
from io import BytesIO
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "best_model_bundle.joblib"
DATA_PATH = BASE_DIR / "dataset_v1.csv"
LOGO_PATH = BASE_DIR / "LOGO RESMI PCR.svg"
STYLE_PATH = BASE_DIR / "app_styles.css"
TARGET_COL = "is_terlambat"

RISK_INFO = {
    "low": {"class": "risk-low", "label": "Rendah"},
    "medium": {"class": "risk-medium", "label": "Sedang"},
    "high": {"class": "risk-high", "label": "Tinggi"},
}

NUMERIC_COLS = [
    "bulan_jatuh_tempo",
    "angkatan",
    "jumlah_saudara",
    "prev_tagihan_count",
    "prev_late_count",
    "prev_cicilan_count",
    "nominal_tagihan",
    "nominal_harus_bayar",
    "kode_prodi",
]

EDA_CATEGORICAL_FIELDS = [
    "jenis_pembayaran",
    "statusmhs_periode",
    "nama_prodi",
    "tahun_ajaran",
    "penghasilan_ortu_label",
]

EDA_CORRELATION_FIELDS = [
    "nominal_tagihan",
    "nominal_harus_bayar",
    "jumlah_saudara",
    "prev_tagihan_count",
    "prev_late_count",
    "prev_late_ratio",
    "prev_cicilan_count",
    "prev_cicilan_ratio",
    TARGET_COL,
]

FORM_BASE_FIELDS = [
    "jenis_pembayaran",
    "nama_prodi",
    "statusmhs_periode",
    "nominal_tagihan",
    "nominal_harus_bayar",
    "penghasilan_ortu_label",
    "bulan_jatuh_tempo",
    "kps_status",
    "jumlah_saudara",
    "semester_tagihan",
    "jenis_semester",
    "jalur_masuk",
    "subjalur_masuk",
    "jenis_kelamin",
    "pendidikan_ayah_label",
    "pendidikan_ibu_label",
    "pekerjaan_ayah",
    "pekerjaan_ibu",
    "angkatan",
]

FORM_HISTORY_FIELDS = {
    "prev_tagihan_count": "count",
    "prev_late_count": "late",
    "prev_cicilan_count": "cicilan",
}

FORM_NUMERIC_CASTS = {
    "nominal_tagihan": float,
    "nominal_harus_bayar": float,
    "bulan_jatuh_tempo": lambda value: int(float(value)),
    "jumlah_saudara": float,
    "angkatan": int,
}

def rupiah_input(field: str, values: dict, key: str, label: str) -> float:
    text = st.text_input(
        label,
        value=f"{float(values[field]):,.0f}".replace(",", "."),
        key=f"{key}_{field}",
    )

    digits = "".join(char for char in str(text) if char.isdigit())
    return float(digits) if digits else 0.0

def num_input(field: str, values: dict, key: str, label: str) -> int:
    return int(
        st.number_input(
            label,
            min_value=0,
            value=int(values[field]),
            step=1,
            key=f"{key}_{field}",
        )
    )

# Load dataset dan bundle model yang dipakai di seluruh app.
@st.cache_data
def load_data():
    bundle = joblib.load(MODEL_PATH)
    
    df = pd.read_csv(
        DATA_PATH,
        sep=";",
        parse_dates=["tanggal_jatuh_tempo"],
        dtype={TARGET_COL: "int64"},
    ).sort_values("tanggal_jatuh_tempo").reset_index(drop=True)

    students = (
        df[["mahasiswa", "nama_prodi"]]
        .drop_duplicates()
        .sort_values(["mahasiswa", "nama_prodi"])
        .reset_index(drop=True)
    )

    return {
        "df": df,
        "students": students,
        "best_model_name": bundle["best_model_name"],
        "features": bundle["feature_cols"],
        "num_cols": bundle["num_cols"],
        "cat_cols": bundle["cat_cols"],
        "model": bundle["model"],
        "defaults": bundle["defaults"],
        "options": bundle["options"],
        "prodi_lookup": bundle["prodi_lookup"],
        "notebook_artifacts": bundle["notebook_artifacts"],
    }

def chart_theme() -> dict:
    background_color = st.get_option("theme.backgroundColor") or "#ffffff"

    try:
        theme = getattr(st.context, "theme", None)
        theme_type = getattr(theme, "type", None)
        dark_mode = theme_type == "dark" if theme_type in {"light", "dark"} else None
    except Exception:
        dark_mode = None

    if dark_mode is None:
        value = background_color.lstrip("#")
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))
        luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
        dark_mode = luminance < 0.5

    background = "#0e1117" if dark_mode else "#ffffff"
    text = "#f8fafc" if dark_mode else "#18212f"

    def rgba(value: str, alpha: float) -> tuple[float, float, float, float]:
        value = value.lstrip("#")
        if len(value) == 3:
            value = "".join(char * 2 for char in value)
        red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))
        return (red, green, blue, alpha)

    return {
        "background": background,
        "text": text,
        "muted": rgba(text, 0.82 if dark_mode else 0.72),
        "grid": rgba(text, 0.14 if dark_mode else 0.12),
        "bar_bg": rgba(text, 0.16 if dark_mode else 0.06),
        "wedge_edge": rgba(background, 0.94),
        "annotation": "#f8fafc",
    }

def axis_style(ax, grid_axis: str = "y"):
    palette = chart_theme()
    ax.set_facecolor("none")
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.tick_params(colors=palette["muted"], labelsize=10)
    ax.xaxis.label.set_color(palette["muted"])
    ax.yaxis.label.set_color(palette["muted"])
    ax.title.set_color(palette["text"])
    ax.grid(axis=grid_axis, color=palette["grid"], linewidth=0.8, alpha=1.0)
    ax.set_axisbelow(True)

# Pie chart distribusi status pembayaran.
def pie_chart(counts: pd.Series):
    palette = chart_theme()
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=140, facecolor="none")
    fig.patch.set_alpha(0)

    wedges, _, _ = ax.pie(
        counts.values,
        labels=None,
        colors=["#22c55e", "#fb7185"],
        startangle=120,
        counterclock=False,
        autopct=lambda pct: f"{pct:.1f}%" if pct >= 5 else "",
        pctdistance=0.68,
        radius=0.9,
        wedgeprops={"edgecolor": palette["wedge_edge"], "linewidth": 1.6},
        textprops={"color": palette["annotation"], "fontsize": 8, "fontweight": "bold"},
    )
    ax.legend(
        wedges,
        counts.index.tolist(),
        loc="center left",
        bbox_to_anchor=(0.9, 0.5),
        frameon=False,
        fontsize=8,
        labelcolor=palette["muted"],
        borderaxespad=0,
    )
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buffer = BytesIO()
    fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    st.image(buffer, width=520)

# Bar chart horizontal untuk rasio keterlambatan per kategori.
def bar_ratio(data: pd.DataFrame, label_col: str, color: str = "#2563eb", height: float | None = None):
    if data.empty:
        st.info("Data belum cukup untuk menampilkan chart ini.")
        return

    palette = chart_theme()
    plot_df = data.sort_values("rasio_terlambat_pct").copy()
    plot_df[label_col] = plot_df[label_col].astype(str)
    max_value = plot_df["rasio_terlambat_pct"].max()
    chart_height = height or max(3.4, min(5.8, len(plot_df) * 0.45))

    fig, ax = plt.subplots(figsize=(7.3, chart_height), facecolor="none")
    fig.patch.set_alpha(0)

    y_pos = np.arange(len(plot_df))
    ax.barh(y_pos, max_value * 1.02, color=palette["bar_bg"], height=0.74)
    bars = ax.barh(y_pos, plot_df["rasio_terlambat_pct"], color=color, height=0.56)

    ax.set_yticks(y_pos, plot_df[label_col])
    ax.set_xlabel("Rasio terlambat (%)")
    ax.set_xlim(0, max(5, max_value * 1.18))
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.bar_label(
        bars,
        labels=plot_df["rasio_terlambat_pct"].map(lambda value: f"{value:.1f}%"),
        padding=6,
        fontsize=10,
        color=palette["text"],
    )

    axis_style(ax, grid_axis="x")
    fig.tight_layout()
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

# Render KPI di dashboard.
def kpi_card(label: str, value: str, icon: str, class_name: str):
    st.markdown(
        f"""
        <div class="dashboard-kpi-card {class_name}">
            <div class="dashboard-kpi-top">
                <div class="dashboard-kpi-label">{label}</div>
                <div class="dashboard-kpi-icon">{icon}</div>
            </div>
            <div class="dashboard-kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Render sidebar
def sidebar(ref: dict) -> str:
    logo_src = ""
    if LOGO_PATH.exists():
        logo = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        logo_src = f"data:image/svg+xml;base64,{logo}"

    feature_count = len(ref["num_cols"]) + len(ref["cat_cols"])
    page = st.query_params.get("page", "Dashboard")
    if isinstance(page, (list, tuple)):
        page = page[0] if page else "Dashboard"
    page = page if page in {"Dashboard", "Prediksi Data"} else "Dashboard"

    active = {
        "Dashboard": " active" if page == "Dashboard" else "",
        "Prediksi Data": " active" if page == "Prediksi Data" else "",
    }

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-shell">
                <div class="sidebar-brand">
                    <div class="sidebar-title">Tuition Fee<br>Payment Prediction</div>
                    <img class="sidebar-logo" src="{logo_src}" alt="Logo Politeknik Caltex Riau">
                </div>
                <div class="sidebar-section-label">Menu</div>
                <div class="sidebar-menu">
                    <a class="sidebar-menu-link{active['Dashboard']}" href="?page=Dashboard" target="_self">
                        <span class="sidebar-menu-icon">&#9638;</span><span>Dashboard</span>
                    </a>
                    <a class="sidebar-menu-link{active['Prediksi Data']}" href="?page=Prediksi%20Data" target="_self">
                        <span class="sidebar-menu-icon">&#10003;</span><span>Prediksi Data</span>
                    </a>
                </div>
                <div class="sidebar-info">
                    <div class="sidebar-section-label">Informasi Model</div>
                    <div class="model-info-card">
                        <div class="model-info-row">
                            <span class="model-info-label">Algoritma</span>
                            <span class="model-info-value">{escape(str(ref["best_model_name"]))}</span>
                        </div>
                        <div class="model-info-row">
                            <span class="model-info-label">Fitur Model</span>
                            <span class="model-info-value">{feature_count}</span>
                        </div>
                    </div>
                </div>
                <div class="sidebar-footer">&copy; Vira Annisa - 25MTTK A.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return page

# Render dashboard: EDA
def dashboard(ref: dict):
    df = ref["df"]

    # Ambil artefak evaluasi model dari bundle notebook.
    artifacts = ref["notebook_artifacts"]
    best_model_name = str(artifacts["best_model_name"])
    comparison_df = artifacts["comparison_df"].copy()
    best_row = comparison_df.loc[comparison_df["model"].astype(str) == best_model_name].iloc[0]
    grouped_importance = artifacts["feature_importance_results"][best_model_name].copy()
    confusion_matrix = np.array(artifacts["conf_matrices"][best_model_name])
    report_df = (
        artifacts["report_by_model"][best_model_name]
        .reset_index(names="label")
        .rename(columns={"f1-score": "f1_score"})
        .copy()
    )
    palette = chart_theme()
    due_min = df["tanggal_jatuh_tempo"].min()
    due_max = df["tanggal_jatuh_tempo"].max()
    available_categorical_eda = [col for col in EDA_CATEGORICAL_FIELDS if col in df.columns]
    corr_features = [col for col in EDA_CORRELATION_FIELDS if col in df.columns]

    # Ringkasan utama dataset.
    st.title("Dashboard")
    st.caption("Ringkasan utama dataset, insight EDA, feature importance, dan evaluasi model dalam satu halaman.")

    cards = st.columns(5, gap="small")
    with cards[0]:
        kpi_card("Total Dataset", f"{int(len(df)):,}".replace(",", "."), "&#9638;", "kpi-blue")
    with cards[1]:
        kpi_card("Jumlah Mahasiswa", f"{int(df['mahasiswa'].nunique()):,}".replace(",", "."), "&#9673;", "kpi-cyan")
    with cards[2]:
        kpi_card("Rasio Keterlambatan", f"{df[TARGET_COL].mean():.2%}", "!", "kpi-red")
    with cards[3]:
        kpi_card("Total Cicilan", f"{int(df['prev_cicilan_count'].max()):,}".replace(",", "."), "&#8635;", "kpi-amber")
    with cards[4]:
        kpi_card("Range Data", f"{due_min:%Y}-{due_max:%Y}", "&#8981;", "kpi-slate")

    st.divider()

    # Visual EDA kategori dan distribusi target.
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Distribusi Status Pembayaran")
        counts = (
            df[TARGET_COL]
            .map({0: "Tepat Waktu", 1: "Terlambat"})
            .value_counts()
            .reindex(["Tepat Waktu", "Terlambat"], fill_value=0)
        )
        pie_chart(counts)

    with right:
        st.subheader("Proporsi Terlambat per Kategori")
        if not available_categorical_eda:
            st.info("Fitur kategorikal untuk EDA tidak tersedia.")
        else:
            default_index = (
                available_categorical_eda.index("penghasilan_ortu_label")
                if "penghasilan_ortu_label" in available_categorical_eda
                else 0
            )
            feature = st.selectbox(
                "Pilih kategori",
                available_categorical_eda,
                index=default_index,
                key="dashboard_categorical_eda",
            )
            top_categories = df[feature].value_counts().head(8).index
            rate_df = (
                df[df[feature].isin(top_categories)]
                .groupby(feature, dropna=False)[TARGET_COL]
                .mean()
                .mul(100)
                .reset_index(name="rasio_terlambat_pct")
                .sort_values("rasio_terlambat_pct", ascending=False)
            )
            bar_ratio(rate_df, feature, color="#60a5fa", height=max(3.4, len(rate_df) * 0.55))

    # Visual korelasi numerik dan feature importance model terbaik.
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Correlation Heatmap")
        if len(corr_features) < 2:
            st.info("Fitur numerik belum cukup untuk membuat heatmap korelasi.")
        else:
            corr_matrix = df[corr_features].corr(numeric_only=True)
            fig, ax = plt.subplots(figsize=(8.2, 5.4), facecolor="none")
            fig.patch.set_alpha(0)
            sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="Blues", square=True, ax=ax)
            ax.set_title("Korelasi Fitur Numerik", color=palette["text"], pad=12)
            ax.tick_params(axis="x", rotation=35, colors=palette["muted"])
            ax.tick_params(axis="y", rotation=0, colors=palette["muted"])
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

    with right:
        st.subheader(f"Feature Importance {best_model_name}")
        top_n = st.slider("Top N feature", 5, 15, 10, key="dashboard_feature_importance_top_n")
        chart_df = grouped_importance.head(top_n).sort_values("importance")
        fig, ax = plt.subplots(figsize=(7.2, max(3.8, top_n * 0.4)), facecolor="none")
        fig.patch.set_alpha(0)
        ax.barh(chart_df["feature_group"], chart_df["importance"], color="#2dd4bf", height=0.58)
        ax.set_xlabel("Importance")
        ax.set_ylabel("")
        axis_style(ax, grid_axis="x")
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.divider()
    
    # Ringkasan evaluasi model terbaik dan detail perbandingan model.
    st.subheader("Evaluasi Model")
    items = [
        ("Best Model", best_model_name, "&#9638;", "eval-indigo"),
        ("Accuracy", f"{best_row['accuracy']:.3f}", "&#9678;", "eval-cyan"),
        ("Precision", f"{best_row['precision']:.3f}", "&#9635;", "eval-blue"),
        ("Recall", f"{best_row['recall']:.3f}", "&#8635;", "eval-amber"),
        ("F1 Score", f"{best_row['f1']:.3f}", "&#10003;", "eval-emerald"),
        ("ROC AUC", f"{best_row['roc_auc']:.3f}", "&#9899;", "eval-rose"),
    ]
    cards = "".join(
        (
            f"<div class=\"eval-stat-card {class_name}\">"
            f"<div class=\"eval-stat-top\"><span class=\"eval-stat-label\">{escape(label)}</span>"
            f"<span class=\"eval-stat-icon\">{icon}</span></div>"
            f"<div class=\"eval-stat-value\">{escape(value)}</div>"
            "</div>"
        )
        for label, value, icon, class_name in items
    )
    st.markdown(f"<div class=\"eval-stat-grid\">{cards}</div>", unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.subheader("Perbandingan Model")
        for col in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
            comparison_df[col] = comparison_df[col].map(lambda value: "-" if pd.isna(value) else f"{value:.4f}")
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

        st.subheader("Confusion Matrix")
        fig, ax = plt.subplots(figsize=(1.8, 1.8), facecolor="none")
        fig.patch.set_alpha(0)

        sns.heatmap(
            confusion_matrix,
            annot=True,
            fmt="d",
            cmap="Blues",
            cbar=False,
            xticklabels=["Pred 0", "Pred 1"],
            yticklabels=["True 0", "True 1"],
            annot_kws={"size": 5},
            ax=ax,
        )

        ax.set_title(best_model_name, color="#f8fafc", pad=8, fontsize=12)
        ax.tick_params(axis="x", colors="#e2e8f0", labelsize=9)
        ax.tick_params(axis="y", colors="#e2e8f0", labelsize=9)

        ax.set_xlabel("")
        ax.set_ylabel("")

        fig.tight_layout(pad=0.5)

        st.pyplot(fig, use_container_width=False)
        plt.close(fig)
    with right:
        st.subheader("Classification Report")
        for col in ["precision", "recall", "f1_score", "support"]:
            report_df[col] = report_df[col].map(lambda value: f"{value:.4f}")

        st.dataframe(
            report_df,
            use_container_width=True,
            hide_index=True,
        )

# Siapkan nilai awal lalu render form simulasi dan kembalikan input user.
def prediction_form(options: dict, defaults: dict, hist: dict) -> tuple[bool, dict]:
    key = hist["key"]
    row = hist["latest"]
    values = defaults.copy()

    if row is not None:
        for col in FORM_BASE_FIELDS:
            if col in row and pd.notna(row[col]):
                values[col] = row[col]

    values = {field: values[field] for field in FORM_BASE_FIELDS}

    for field, caster in FORM_NUMERIC_CASTS.items():
        values[field] = caster(values[field])

    for field, hist_key in FORM_HISTORY_FIELDS.items():
        history_value = hist[hist_key]
        values[field] = int(history_value if history_value is not None else defaults[field])

    def opt(field: str, label: str):
        items = [str(item) for item in options[field]]
        value = str(values[field])
        if value not in items:
            items = [value] + items
        return st.selectbox(label, items, index=items.index(value), key=f"{key}_{field}")

    with st.form(f"prediction_form_{key}"):
        st.subheader("Form Simulasi Tagihan")

        c1, c2 = st.columns(2)
        with c1:
            jenis_pembayaran = opt("jenis_pembayaran", "Jenis Pembayaran")
        with c2:
            nama_prodi = opt("nama_prodi", "Program Studi")

        c1, c2 = st.columns(2)
        with c1:
            statusmhs_periode = opt("statusmhs_periode", "Status Mahasiswa")
        with c2:
            kps_status = opt("kps_status", "Penerima KPS/Bantuan")

        c1, c2 = st.columns(2)
        with c1:
            penghasilan_ortu_label = opt("penghasilan_ortu_label", "Penghasilan Orang Tua")
        with c2:
            bulan_jatuh_tempo = st.slider("Bulan Jatuh Tempo", 1, 12, int(values["bulan_jatuh_tempo"]),key=f"{key}_bulan_jatuh_tempo")

        c1, c2 = st.columns(2)
        with c1:
            nominal_tagihan = rupiah_input("nominal_tagihan", values, key, "Nominal Tagihan")
        with c2:
            nominal_harus_bayar = rupiah_input("nominal_harus_bayar", values, key, "Nominal Harus Bayar")


        st.markdown("##### Riwayat Pembayaran")

        c1, c2 = st.columns(2)
        with c1:
            prev_tagihan_count = num_input("prev_tagihan_count", values, key, "Jumlah Riwayat Tagihan")
        with c2:
            prev_late_count = num_input("prev_late_count", values, key, "Jumlah Riwayat Terlambat")

        prev_cicilan_count = num_input("prev_cicilan_count", values, key, "Jumlah Riwayat Cicilan")

        submitted = st.form_submit_button(
            "Prediksi Tagihan",
            use_container_width=True,
        )

    user_input = {
        **values,
        "jenis_pembayaran": jenis_pembayaran,
        "nama_prodi": nama_prodi,
        "statusmhs_periode": statusmhs_periode,
        "kps_status": kps_status,
        "penghasilan_ortu_label": penghasilan_ortu_label,
        "bulan_jatuh_tempo": bulan_jatuh_tempo,
        "nominal_tagihan": nominal_tagihan,
        "nominal_harus_bayar": nominal_harus_bayar,
        "prev_tagihan_count": int(prev_tagihan_count),
        "prev_late_count": int(prev_late_count),
        "prev_cicilan_count": int(prev_cicilan_count),
    }

    return submitted, user_input

# Susun satu baris input sesuai fitur yang dibutuhkan model.
def model_input(ref: dict, values: dict) -> pd.DataFrame:
    row = ref["defaults"].copy()
    row.update(values)

    if row["nama_prodi"] in ref["prodi_lookup"]:
        row["kode_prodi"] = float(ref["prodi_lookup"][row["nama_prodi"]])

    tagihan_count = int(row["prev_tagihan_count"])
    row["prev_late_count"] = min(int(row["prev_late_count"]), tagihan_count)
    row["prev_cicilan_count"] = min(int(row["prev_cicilan_count"]), tagihan_count)

    if tagihan_count:
        row["prev_late_ratio"] = row["prev_late_count"] / tagihan_count
        row["prev_cicilan_ratio"] = row["prev_cicilan_count"] / tagihan_count
    else:
        row["prev_late_ratio"] = 0.0
        row["prev_cicilan_ratio"] = 0.0

    for col in NUMERIC_COLS:
        row[col] = float(row[col])

    return pd.DataFrame([{col: row[col] for col in ref["features"]}])

# Card Prediksi
def prediction_card(label: int, prob: float):
    risk_key = "low" if prob <= 0.30 else "medium" if prob <= 0.60 else "high"
    risk = RISK_INFO[risk_key]
    status = "Terlambat" if label == 1 else "Tepat Waktu"
    icon = "&times;" if label == 1 else "&#10003;"

    st.markdown(
        f"""
        <div class="prediction-card {risk['class']}">
            <div class="prediction-main">
                <div class="prediction-icon">{icon}</div>
                <div>
                    <div class="prediction-status">{status}</div>
                    <div class="prediction-risk">Risiko {risk['label']}</div>
                </div>
            </div>
            <div class="prediction-main">
                <div>
                    <div class="prediction-probability">{prob:.2%}</div>
                    <div class="prediction-risk">Probabilitas terlambat</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Render halaman prediksi
def prediction_page(model, ref: dict):
    df = ref["df"]

    st.title("Prediksi Data")
    # st.caption("Pilih mahasiswa untuk prefill otomatis, atau kosongkan untuk simulasi manual.")

    # Pilih mahasiswa untuk memuat histori pembayaran sebelumnya.
    student_map = {f"{row['mahasiswa']} | {row['nama_prodi']}": row["mahasiswa"] for _, row in ref["students"].iterrows()}
    selected_label = st.selectbox(
        "Cari Mahasiswa",
        list(student_map.keys()),
        key="student_select",
        index=None,
        placeholder="Ketik nama atau prodi",
    )
    selected_student = student_map[selected_label] if selected_label else None
    if not selected_student:
        hist = {"rows": None, "latest": None, "count": None, "late": None, "cicilan": None, "ratio": None, "key": "manual"}
    else:
        rows = df[df["mahasiswa"] == selected_student].sort_values("tanggal_jatuh_tempo").copy()
        count = int(len(rows))
        late = int(rows[TARGET_COL].sum())
        hist = {
            "rows": rows,
            "latest": rows.iloc[-1].copy() if count else None,
            "count": count,
            "late": late,
            "cicilan": int(rows["prev_cicilan_count"].max()) if count else 0,
            "ratio": late / count if count else 0.0,
            "key": f"student_{selected_student.replace(' ', '_')}",
        }

    # Tampilkan ringkasan histori singkat di atas form.
    values = {
        "Jumlah Tagihan": hist["count"] if hist["count"] is not None else "-",
        "Jumlah Terlambat": hist["late"] if hist["late"] is not None else "-",
        "Rasio Terlambat": f"{hist['ratio']:.2%}" if hist["ratio"] is not None else "-",
        "Riwayat Cicilan": hist["cicilan"] if hist["cicilan"] is not None else "-",
    }
    items = "".join(
        "<div class=\"compact-metric\">"
        f"<div class=\"compact-metric-label\">{escape(str(label))}</div>"
        f"<div class=\"compact-metric-value\">{escape(str(value))}</div>"
        "</div>"
        for label, value in values.items()
    )
    st.markdown(f"<div class=\"compact-metrics\">{items}</div>", unsafe_allow_html=True)

    form_col, result_col = st.columns([1, 1], gap="small")

    # Form simulasi di kiri, hasil prediksi di kanan.
    with form_col:
        submitted, values = prediction_form(ref["options"], ref["defaults"], hist)

    with result_col:
        st.subheader("Hasil Prediksi")
        if not submitted:
            st.info("Isi form lalu klik Prediksi Tagihan.")
            return

        x = model_input(ref, values)
        label = int(model.predict(x)[0])
        prob = float(model.predict_proba(x)[0, 1])
        prediction_card(label, prob)

        # Tampilkan 5 riwayat pembayaran terakhir bila tersedia.
        if hist["rows"] is not None:
            with st.expander("Lihat 5 riwayat pembayaran terakhir"):
                history_df = hist["rows"].sort_values(
                    ["tanggal_jatuh_tempo", "tagihan_id"],
                    ascending=[False, False],
                ).head(5).copy()
                history_df["nominal_tagihan"] = history_df["nominal_tagihan"].map(
                    lambda value: f"Rp {float(value):,.0f}".replace(",", ".")
                )
                history_df["Status Aktual"] = history_df[TARGET_COL].map({0: "Tepat Waktu", 1: "Terlambat"})
                st.dataframe(
                    history_df[["jenis_pembayaran", "nominal_tagihan", "Status Aktual"]].rename(
                        columns={
                            "jenis_pembayaran": "Jenis Pembayaran",
                            "nominal_tagihan": "Nominal Tagihan",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

def main():
    st.set_page_config(
        page_title="Tuition Fee Delay Prediction",
        page_icon=":mortar_board:",
        layout="wide",
    )
    st.markdown(f"<style>{STYLE_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

    ref = load_data()
    page = sidebar(ref)

    if page == "Dashboard":
        dashboard(ref)
    else:
        prediction_page(ref["model"], ref)

if __name__ == "__main__":
    main()
