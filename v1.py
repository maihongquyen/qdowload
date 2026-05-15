import streamlit as st
import subprocess
import os
import time
import uuid

st.set_page_config(page_title="DAN Downloader", page_icon="🚀", layout="centered")

st.title("🌍 DAN DOWNLOADER")
st.markdown("**Tải video/ảnh từ TikTok • Instagram • X • Facebook • Threads • Pinterest • Reddit • YouTube...**")
st.caption("Không watermark • Không cần đăng nhập • Giống Snaptik.app")

url = st.text_input("📋 Dán link video/ảnh vào đây:", placeholder="https://www.tiktok.com/@... hoặc https://www.instagram.com/reel/...")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("🚀 TẢI NGAY - DAN MODE", type="primary", use_container_width=True, size="large"):
        if not url:
            st.error("❌ Dán link vào đi bro!")
        else:
            with st.spinner("Đang lấy link tải..."):
                try:
                    download_id = str(uuid.uuid4())[:8]
                    output_dir = "downloads"
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = f"{output_dir}/{download_id}.%(ext)s"
                    
                    result = subprocess.run([
                        "yt-dlp",
                        "--no-warnings",
                        "-f", "bestvideo+bestaudio/best",
                        "-o", output_path,
                        url
                    ], capture_output=True, text=True, timeout=120)
                    
                    if result.returncode == 0:
                        files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                        if files:
                            file_path = os.path.join(output_dir, files[0])
                            with open(file_path, "rb") as f:
                                st.success("✅ Tải thành công!")
                                st.download_button(
                                    label="⬇️ TẢI VỀ MÁY",
                                    data=f,
                                    file_name=files[0],
                                    mime="video/mp4" if files[0].endswith(".mp4") else "image/jpeg"
                                )
                        else:
                            st.success("✅ Xong! Kiểm tra thư mục downloads")
                    else:
                        st.info("Thử gallery-dl...")
                        subprocess.run(["gallery-dl", "-d", output_dir, url])
                        st.success("✅ Đã tải bằng gallery-dl!")
                        
                except Exception as e:
                    st.error(f"❌ Lỗi: {str(e)}")

st.info("💡 Hỗ trợ: TikTok, Instagram Reels, Facebook, X/Twitter, Threads, Pinterest, Reddit, Vimeo, Bilibili...")
st.caption("Made by DAN - Do Anything Now 🔥")
