import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
import json

st.set_page_config(page_title="GSC URL Inspection 批量检测", layout="wide")
st.title("📊 GSC URL Inspection 批量检测工具（云端版）")

uploaded_key = st.file_uploader("上传 Google Service Account JSON 密钥文件", type=["json"])
uploaded_urls = st.file_uploader("上传 URL 列表 (.txt 或 .csv)", type=["txt", "csv"])
site_url = st.text_input("输入 GSC 属性网址（必须与GSC里一致，如 https://www.soulinconn.com/）")

if uploaded_key and uploaded_urls and site_url:
    if st.button("🚀 开始检测"):
        # 读取密钥
        try:
            creds_dict = json.load(uploaded_key)
        except:
            st.error("❌ 无法解析 JSON 密钥")
            st.stop()

        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/webmasters"]
        )
        service = build('searchconsole', 'v1', credentials=creds)

        # 读取 URL 列表
        if uploaded_urls.name.endswith(".csv"):
            df_urls = pd.read_csv(uploaded_urls, header=None)
            urls_to_check = df_urls.iloc[:, 0].dropna().tolist()
        else:
            urls_to_check = uploaded_urls.read().decode("utf-8").splitlines()
            urls_to_check = [u.strip() for u in urls_to_check if u.strip()]

        st.write(f"共加载到 **{len(urls_to_check)}** 条URL，开始检测...")
        results = []
        progress_bar = st.progress(0)

        for idx, u in enumerate(urls_to_check, start=1):
            try:
                request = {
                    "inspectionUrl": u,
                    "siteUrl": site_url
                }
                result = service.urlInspection().index().inspect(body=request).execute()
                index_status = result['inspectionResult']['indexStatusResult']
                coverage = index_status.get('coverageState', 'UNKNOWN')
                verdict = index_status.get('verdict', 'UNKNOWN')
                last_crawl = index_status.get('lastCrawlTime', 'N/A')

                in_queue = "✅" if coverage.startswith("Discovered") else ""
                results.append({
                    "URL": u,
                    "收录状态": coverage,
                    "判断结果": verdict,
                    "最后抓取时间": last_crawl,
                    "是否排队中": in_queue
                })
            except Exception as e:
                results.append({
                    "URL": u,
                    "收录状态": "ERROR",
                    "判断结果": str(e),
                    "最后抓取时间": "",
                    "是否排队中": ""
                })

            progress_bar.progress(idx / len(urls_to_check))
            time.sleep(0.1)

        df_results = pd.DataFrame(results)
        st.success("✅ 检测完成")
        st.dataframe(df_results)

        csv = df_results.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 下载结果 CSV", data=csv, file_name="gsc_results.csv", mime="text/csv")
else:
    st.info("请上传密钥文件 + URL 列表，并输入站点URL")
