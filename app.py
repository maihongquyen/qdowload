import streamlit as st
import subprocess
import os
import time
import uuid
import sys

# Tự động cài packages
def install_packages():
    pkgs = ["yt-dlp", "gallery-dl"]
    for pkg in pkgs:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            with st.spinner(f"Đang cài {pkg}..."):
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_packages()

st.set_page_config(page_title="All-in-One", page_icon="🚀", layout="centered")

st.title("🌍ALL-IN-ONE TOOL")

tab1, tab2 = st.tabs(["🚀 TẢI VIDEO TỪ MXH", "🗜️ NÉN VIDEO"])

# ==================== TAB 1: DOWNLOADER ====================
with tab1:
    st.markdown("**Tải video/ảnh không watermark từ TikTok • Instagram • X • FB • Threads • Pinterest...**")
    url = st.text_input("📋 Dán link vào đây:", 
                        placeholder="https://www.tiktok.com/@... hoặc https://www.instagram.com/reel/...")

    if st.button("🚀 TẢI NGAY", type="primary", use_container_width=True):
        if not url:
            st.error("❌ Dán link trước!")
        else:
            with st.spinner("Đang tải..."):
                try:
                    download_id = str(uuid.uuid4())[:8]
                    output_dir = "downloads"
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = f"{output_dir}/{download_id}.%(ext)s"
                    
                    result = subprocess.run([
                        "yt-dlp", "--no-warnings", "-f", "bestvideo+bestaudio/best",
                        "-o", output_path, "--max-filesize", "800M", url
                    ], capture_output=True, text=True, timeout=180)
                    
                    files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                    if not files:
                        subprocess.run(["gallery-dl", "-d", output_dir, url])
                        files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                    
                    if files:
                        file_path = os.path.join(output_dir, files[0])
                        with open(file_path, "rb") as f:
                            st.success(f"✅ Tải thành công: {files[0]}")
                            st.download_button("⬇️ TẢI VỀ", data=f, file_name=files[0], use_container_width=True)
                    else:
                        st.error("Không tải được file")
                except Exception as e:
                    st.error(f"Lỗi: {str(e)}")

# ==================== TAB 2: COMPRESSOR ====================
with tab2:
    st.markdown("**Upload video → Nén dung lượng → Tải về**")
    uploaded_file = st.file_uploader("Chọn video cần nén", 
                                     type=["mp4", "mov", "webm", "mkv", "avi"])

    if uploaded_file:
        quality = st.selectbox("Mức nén", [
            "Siêu nhỏ (CRF 32)", 
            "Nhỏ vừa (CRF 28 - Khuyến nghị)", 
            "Giữ chất lượng cao (CRF 23)"
        ], index=1)
        
        crf = {"Siêu nhỏ (CRF 32)": 32, "Nhỏ vừa (CRF 28 - Khuyến nghị)": 28, "Giữ chất lượng cao (CRF 23)": 23}[quality]

        if st.button("🗜️ BẮT ĐẦU NÉN", type="primary", use_container_width=True):
            with st.spinner("Đang nén video..."):
                try:
                    input_path = f"temp/{uuid.uuid4()}_{uploaded_file.name}"
                    os.makedirs("temp", exist_ok=True)
                    with open(input_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                    output_path = input_path.replace(".", "_compressed.")

                    subprocess.run([
                        "ffmpeg", "-i", input_path,
                        "-vcodec", "libx264", "-crf", str(crf),
                        "-preset", "medium", "-acodec", "aac",
                        "-b:a", "128k", "-movflags", "+faststart",
                        output_path
                    ], capture_output=True, text=True, timeout=300)

                    orig_size = os.path.getsize(input_path) / (1024*1024)
                    comp_size = os.path.getsize(output_path) / (1024*1024)

                    st.success(f"✅ Nén xong! {orig_size:.1f}MB → {comp_size:.1f}MB")
                    with open(output_path, "rb") as f:
                        st.download_button("⬇️ TẢI VIDEO ĐÃ NÉN", 
                                           data=f, 
                                           file_name=f"COMPRESSED_{uploaded_file.name}",
                                           use_container_width=True)
                except Exception as e:
                    st.error(f"Lỗi: {str(e)}")
