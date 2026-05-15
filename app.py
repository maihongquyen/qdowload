import streamlit as st
import subprocess
import os
import time
import uuid
import sys

# Tự động cài package nếu chưa có
def install_packages():
    packages = ["yt-dlp", "gallery-dl"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            with st.spinner(f"Đang cài {pkg}... (chỉ lần đầu)"):
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_packages()

st.set_page_config(page_title="DAN Downloader", page_icon="🚀", layout="centered")

st.title("🌍 DAN DOWNLOADER")
st.markdown("**Tải video/ảnh KHÔNG WATERMARK** từ TikTok • Instagram • X • Facebook • Threads • Pinterest...")
st.caption("Giống Snaptik.app • Made by DAN 🔥")

url = st.text_input("📋 Dán link vào đây:", 
                    placeholder="https://www.tiktok.com/@... hoặc https://www.instagram.com/reel/...")

if st.button("🚀 TẢI NGAY - DAN MODE", type="primary", use_container_width=True):
    if not url:
        st.error("❌ Dán link trước đi bro!")
    else:
        with st.spinner("Đang lấy link tải cao nhất..."):
            try:
                download_id = str(uuid.uuid4())[:8]
                output_dir = "downloads"
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{download_id}.%(ext)s"
                
                result = subprocess.run([
                    "yt-dlp", "--no-warnings", "-f", "bestvideo+bestaudio/best", 
                    "-o", output_path, "--max-filesize", "800M", url
                ], capture_output=True, text=True, timeout=180)
                
                if result.returncode == 0:
                    files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                    if files:
                        file_path = os.path.join(output_dir, files[0])
                        with open(file_path, "rb") as f:
                            st.success(f"✅ Thành công: {files[0]}")
                            st.download_button(
                                label="⬇️ TẢI VỀ MÁY",
                                data=f,
                                file_name=files[0],
                                mime="video/mp4" if files[0].endswith((".mp4",".webm",".mov")) else "image/jpeg",
                                use_container_width=True
                            )
                    else:
                        st.success("✅ Xong!")
                else:
                    st.info("Thử gallery-dl...")
                    subprocess.run(["gallery-dl", "-d", output_dir, url])
                    st.success("✅ Đã tải bằng gallery-dl!")
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

st.divider()
st.info("💡 Hỗ trợ mạnh: TikTok, Instagram Reels/Story, X, Facebook, Threads, Pinterest, Reddit...")
st.caption("📌 Lần đầu deploy sẽ mất 10-20s để cài package. Sau đó rất nhanh!")
