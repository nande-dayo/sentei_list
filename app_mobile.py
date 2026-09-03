import math
import pandas as pd
import streamlit as st
from streamlit_mic_recorder import speech_to_text

# スマホ向けに画面幅を調整
st.set_page_config(
    page_title="選定療養計算（スマホ版）",
    layout="centered",  # スマホ向けに中央寄せ
    initial_sidebar_state="collapsed",  # サイドバーを初期状態でたたむ
)

st.title("💊 選定療養 負担額計算")


# データ読み込み
@st.cache_data
def load_data(file_path):
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="shift_jis")
    return df


def goshagochoin_points(amount_jpy):
    points = math.floor((amount_jpy + 4.9999) / 10)
    return max(0, points)


CSV_FILE = "sentei_list.csv"

try:
    df = load_data(CSV_FILE)

    # スマホ向け：条件設定を入力フォーム内に集約
    with st.expander("⚙️ 設定・条件の変更", expanded=False):
        ratio = st.radio(
            "自己負担率",
            [0.3, 0.2, 0.1],
            format_func=lambda x: f"{int(x * 10)}割",
            index=0,
            horizontal=True,
        )
    
    # 入力エリア
    search_kw = st.text_input("🔍 医薬品名を入力（例: レミニール）", value="")
    if search_kw:
        filtered_df = df[
            df["品名"].str.contains(search_kw, case=False, na=False)
        ]
    else:
        filtered_df = df.head(50)

    if filtered_df.empty:
        st.warning("該当する医薬品が見つかりませんでした。")
    else:
        selected_name = st.selectbox(
            "該当医薬品を選択", options=filtered_df["品名"].tolist()
        )

        col_qty, col_days = st.columns(2)
        with col_qty:
            daily_qty = st.number_input(
                "1日量（錠・g）", min_value=0.1, value=1.0, step=0.5
            )
        with col_days:
            days = st.number_input("処方日数", min_value=1, value=14, step=1)

        # マスタ抽出＆数値変換
        target_row = df[df["品名"] == selected_name].iloc[0]

        def parse_num(val):
            return (
                float(str(val).replace(",", "")) if pd.notna(val) else 0.0
            )

        price_seihatsu = parse_num(target_row["薬価"])
        price_kohatsu_max = parse_num(target_row["後発医薬品最高価格"])
        diff_half = parse_num(
            target_row["長期収載品と後発医薬品の価格差の２分の１"]
        )
        price_calc_base = parse_num(
            target_row["保険外併用療養費の算出に用いる価格"]
        )

        # --- 計算処理 ---
        # 【A】特別料金
        point_a_daily = goshagochoin_points(diff_half * daily_qty)
        point_a_total = point_a_daily * days
        fee_a_taxed = math.floor(point_a_total * 10 * 1.1)

        # 【B・C】保険分
        point_b_daily = goshagochoin_points(price_calc_base * daily_qty)
        point_b_total = point_b_daily * days
        fee_b_total = point_b_total * 10
        fee_c_patient = int(round(fee_b_total * ratio, -1))
        fee_d_insurance = fee_b_total - fee_c_patient

        # 【E】先発総額
        fee_e_total = fee_a_taxed + fee_c_patient

        # 後発品比較
        point_kohatsu_daily = goshagochoin_points(
            price_kohatsu_max * daily_qty
        )
        point_kohatsu_total = point_kohatsu_daily * days
        fee_kohatsu_patient = int(
            round((point_kohatsu_total * 10) * ratio, -1)
        )
        diff_final = fee_e_total - fee_kohatsu_patient

        st.markdown("---")

        # ★ スマホ用：タブ切り替え（要約 vs 厚生局明細）
        tab_summary, tab_detail = st.tabs(
            ["📱 結果要約（患者説明）", "📄 計算明細（厚生局様式）"]
        )

        with tab_summary:
            st.warning(
                f"⚠️ 先発品を選択時の追加負担\n# **+{diff_final:,} 円**"
            )

            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.error(
                    f"🔴 **先発品 窓口負担**\n### **{fee_e_total:,} 円**\n(特別料金: {fee_a_taxed}円込)"
                )
            with col_res2:
                st.success(
                    f"🟢 **後発品 窓口負担**\n### **{fee_kohatsu_patient:,} 円**\n(保険適用分のみ)"
                )

        with tab_detail:
            st.caption(f"対象品名: **{selected_name}**")
            st.markdown("#### **【A】特別の料金**")
            st.write(
                f"- 1日分: `{diff_half:.2f}円【a】 × {daily_qty} = {diff_half*daily_qty:.2f}円` ➔ **{point_a_daily}点**"
            )
            st.write(
                f"- 金額(税込10%): `{point_a_total}点 × 10円 × 1.1 =` **{fee_a_taxed:,}円**"
            )

            st.markdown("#### **【B】選定療養を除く保険対象費用**")
            st.write(
                f"- 1日分: `{price_calc_base:.2f}円【b】 × {daily_qty} = {price_calc_base*daily_qty:.2f}円` ➔ **{point_b_daily}点**"
            )
            st.write(
                f"- 総点数・総額: `{point_b_total}点` ➔ **{fee_b_total:,}円**"
            )

            st.markdown("#### **【C・D・E】患者負担**")
            st.write(
                f"- 【C】保険自己負担: `{fee_b_total:,}円 × {int(ratio*10)}割 =` **{fee_c_patient:,}円**"
            )
            st.write(
                f"- 【D】保険給付分: `{fee_b_total:,}円 × {int((1-ratio)*10)}割 =` **{fee_d_insurance:,}円**"
            )
            st.write(
                f"- 【E】先発品窓口合計(A+C): **{fee_e_total:,}円**"
            )

except FileNotFoundError:
    st.error(f"ファイル '{CSV_FILE}' が見つかりません。")
except Exception as e:
    st.error(f"エラーが発生しました: {e}")