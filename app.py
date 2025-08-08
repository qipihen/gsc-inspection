import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ------------------------- 你的 GSC 检测函数 -------------------------
def inspect_url(sa_file, site_url, url):
    """调用 Google Search Console API 检测 URL 状态"""
    SCOPES = ['https://www.googleapis.com/auth/webmasters']
    creds = service_account.Credentials.from_service_account_info(
        sa_file, scopes=SCOPES)
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

# ------------------------- Streamlit 应用 -------------------------
st.set_page_config(page_title="GSC URL 批量检测工具（云端版）", layout="wide")
st.title("🚀 GSC URL Inspection 批量检测工具 (支持断点续跑)")

# 存储运行结果在 session_state
if "results" not in st.session_state:
    st.session_state.results = []

# 上传凭证
uploaded_json = st.file_uploader("📂 上传 Google Service Account JSON 密钥文件", type=["json"])

# 上传 URL 列表（CSV 或 TXT）
uploaded_csv = st.file_uploader("📂 上传 URL 列表 或 上次的进度文件", type=["csv", "txt"])

# 输入 GSC 属性
site_url = st.text_input("🌐 GSC 属性网址（必须与 GSC 一致）", "https://www.example.com/")

# 开始检测
if st.button("🚀 开始检测"):
    if uploaded_json and uploaded_csv and site_url:
        sa_dict = pd.read_json(uploaded_json, typ='series').to_dict()

        # 读取输入文件
        df_input = pd.read_csv(uploaded_csv, header=None)
        df_input.columns = ["url"] if df_input.shape[1] == 1 else df_input.columns

        # 如果有 status 列，说明是上次进度，过滤已完成的
        if "status" in df_input.columns:
            done_count = df_input["status"].notna().sum()
            st.info(f"检测到已有 {done_count} 条结果，将跳过这些 URL...")
            urls_to_check = df_input[df_input["status"].isna()]["url"].tolist()
            # 已完成的部分加载到 results
            st.session_state.results = df_input[df_input["status"].notna()].to_dict("records")
        else:
            urls_to_check = df_input["url"].tolist()

        total_urls = len(urls_to_check)
        st.write(f"共需检测 {total_urls} 条 URL")

        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, url in enumerate(urls_to_check):
            status = inspect_url(sa_dict, site_url, url)
            st.session_state.results.append({
                "url": url,
                "status": status
            })

            progress_bar.progress((idx + 1) / total_urls)
            status_text.text(f"{idx+1}/{total_urls} 已完成: {url} --> {status}")

            # 实时生成部分结果文件（包含已完成的部分）
            temp_df = pd.DataFrame(st.session_state.results)
            csv_data = temp_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇ 实时下载当前进度CSV（可用于断点续跑）",
                data=csv_data,
                file_name='gsc_results_partial.csv',
                mime='text/csv'
            )

        st.success("✅ 检测完成！")
        final_df = pd.DataFrame(st.session_state.results)
        st.download_button(
            label="⬇ 下载最终完整结果CSV",
            data=final_df.to_csv(index=False).encode('utf-8'),
            file_name=f'gsc_results_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            mime='text/csv'
        )
    else:
        st.error("请先上传 JSON 密钥 和 URL 列表，并输入 GSC 属性网址")
