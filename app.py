import streamlit as st
import pandas as pd
import re
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# =====================================================
# 【1】调用 GSC API 检测 URL 状态
# =====================================================
def inspect_url(sa_file_dict, site_url, url):
    """调用 Google Search Console API 检测 URL 状态"""
    SCOPES = ['https://www.googleapis.com/auth/webmasters']
    creds = service_account.Credentials.from_service_account_info(
        sa_file_dict, scopes=SCOPES)
    service = build('searchconsole', 'v1', credentials=creds)

    try:
        request = {
            'inspectionUrl': url,
            'siteUrl': site_url
        }
        response = service.urlInspection().index().inspect(body=request).execute()
        status = response['inspectionResult']['indexStatusResult']['coverageState']
        return status
    except Exception as e:
        return f"Error: {e}"

# =====================================================
# 【2】智能上传文件读取 + 自动识别 URL 列
# =====================================================
def load_url_file(file):
    """自动读取 Excel / CSV / TXT，并识别 URL 列，支持断点续跑"""
    filename = file.name.lower()

    # 读取
    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        df = pd.read_excel(file)
    elif filename.endswith(".csv"):
        df = pd.read_csv(file, encoding="utf-8-sig")
    elif filename.endswith(".txt"):
        df = pd.read_csv(file, header=None, names=["url"], encoding="utf-8-sig")
    else:
        st.error("❌ 文件类型不支持，请上传 CSV / TXT / XLSX")
        return None

    # 清洗列名
    df.columns = df.columns.str.strip().str.lower()

    # 找 URL 列
    url_col = None
    for col in df.columns:
        sample_values = df[col].dropna().astype(str).head(10).tolist()
        if any(re.match(r'^https?://', v.strip()) for v in sample_values):
            url_col = col
            break

    if url_col is None:
        st.error("❌ 未检测到 URL 列，请检查文件内容")
        return None

    # 统一格式
    if "status" in df.columns:
        df = df[[url_col, "status"]].rename(columns={url_col: "url"})
    else:
        df = df[[url_col]].rename(columns={url_col: "url"})

    return df

# =====================================================
# 【3】Streamlit 应用主体
# =====================================================
st.set_page_config(page_title="GSC URL 批量检测工具", layout="wide")
st.title("🚀 GSC URL Inspection 批量检测工具（云端无冲突修正版）")

if "results" not in st.session_state:
    st.session_state.results = []

# 上传 Google Service Account JSON
uploaded_json = st.file_uploader("📂 上传 Google Service Account JSON 文件", type=["json"])

# 上传 URL 文件
uploaded_file = st.file_uploader("📂 上传 URL 列表 / 上次进度文件（CSV/TXT/XLSX）", type=["csv", "txt", "xlsx"])

# 输入 GSC 属性网址
site_url = st.text_input("🌐 GSC 属性网址（与 GSC 中完全一致）", "https://www.example.com/")

# =====================================================
# 【4】开始检测按钮
# =====================================================
if st.button("🚀 开始检测"):
    if uploaded_json and uploaded_file and site_url:
        # 读取 JSON 为字典
        try:
            sa_dict = pd.read_json(uploaded_json, typ='series').to_dict()
        except Exception:
            st.error("❌ JSON 文件格式错误，请确认上传的是 Google Service Account 凭证")
            st.stop()

        # 读取 URL 列表
        df_input = load_url_file(uploaded_file)
        if df_input is None:
            st.stop()

        # 判断断点续跑
        if "status" in df_input.columns:
            done_count = df_input["status"].notna().sum()
            st.info(f"🔄 检测到已有 {done_count} 条结果，将跳过这些 URL")
            urls_to_check = df_input[df_input["status"].isna()]["url"].tolist()
            st.session_state.results = df_input[df_input["status"].notna()].to_dict("records")
        else:
            urls_to_check = df_input["url"].tolist()

        total_urls = len(urls_to_check)
        st.write(f"📌 本次需检测 {total_urls} 条 URL")

        if total_urls == 0:
            st.warning("没有需要检测的 URL，可能文件中全部已完成")
            st.stop()

        # 循环前先提供一个实时下载按钮（随时导出当前 results）
        st.download_button(
            label="⬇ 下载当前进度 CSV（可断点续跑）",
            data=pd.DataFrame(st.session_state.results).to_csv(index=False).encode('utf-8'),
            file_name="gsc_results_partial.csv",
            mime="text/csv",
            key="partial_before_loop"
        )

        # 进度条 + 状态显示
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 循环检测
        for idx, url in enumerate(urls_to_check):
            status = inspect_url(sa_dict, site_url, url)
            st.session_state.results.append({
                "url": url,
                "status": status
            })

            progress_bar.progress((idx + 1) / total_urls)
            status_text.text(f"{idx+1}/{total_urls} 已完成: {url} → {status}")

        # 检测完成后输出最终下载按钮
        st.success("✅ 检测完成！")
        final_df = pd.DataFrame(st.session_state.results)
        st.download_button(
            label="⬇ 下载最终完整结果 CSV",
            data=final_df.to_csv(index=False).encode('utf-8'),
            file_name=f'gsc_results_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            mime='text/csv',
            key="final_download"
        )

    else:
        st.error("❌ 请上传 JSON 凭证文件、URL 文件，并输入 GSC 属性网址")
