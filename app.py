import streamlit as st
import subprocess
import os
import time
import uuid
import sys

# Tự động cài package
def install_packages():
    packages = ["yt-dlp", "gallery-dl"]
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            with st.spinner(f"Đang cài {pkg}..."):
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

install_packages()

st.set_page_config(page_title="DAN Downloader", page_icon="🚀", layout="centered")

st.title("🌍 DAN DOWNLOADER + NÉN VIDEO")
st.markdown("**Tải + Nén video/ảnh không watermark** từ TikTok • Instagram • X • FB • Threads...")
st.caption("Giống Snaptik.app • Made by DAN 🔥")

url = st.text_input("📋 Dán link vào đây:", 
                    placeholder="https://www.tiktok.com/@...")

compress = st.checkbox("🗜️ Nén video (tiết kiệm 50-80% dung lượng)", value=True)

if st.button("🚀 TẢI NGAY - DAN MODE", type="primary", use_container_width=True):
    if not url:
        st.error("❌ Dán link trước!")
    else:
        with st.spinner("Đang tải..."):
            try:
                download_id = str(uuid.uuid4())[:8]
                output_dir = "downloads"
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{download_id}.%(ext)s"
                
                # Tải video
                result = subprocess.run([
                    "yt-dlp", "--no-warnings", "-f", "bestvideo+bestaudio/best",
                    "-o", output_path, "--max-filesize", "800M", url
                ], capture_output=True, text=True, timeout=180)
                
                files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                if not files:
                    st.warning("Thử gallery-dl...")
                    subprocess.run(["gallery-dl", "-d", output_dir, url])
                    files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                
                if files:
                    original_file = os.path.join(output_dir, files[0])
                    
                    # NÉN VIDEO nếu chọn
                    if compress and files[0].lower().endswith(('.mp4', '.mov', '.webm', '.mkv')):
                        with st.spinner("Đang nén video..."):
                            compressed_file = original_file.replace(".", "_compressed.")
                            subprocess.run([
                                "ffmpeg", "-i", original_file,
                                "-vcodec", "libx264", "-crf", "28",  # CRF 28 = chất lượng tốt + nén mạnh
                                "-preset", "medium",
                                "-acodec", "aac",
                                "-b:a", "128k",
                                compressed_file
                            ], capture_output=True, text=True)
                            
                            final_file = compressed_file
                            st.success("✅ Đã nén video!")
                    else:
                        final_file = original_file
                    
                    # Hiển thị nút tải
                    with open(final_file, "rb") as f:
                        st.success(f"✅ Thành công: {os.path.basename(final_file)}")
                        st.download_button(
                            label="⬇️ TẢI VỀ MÁY",
                            data=f,
                            file_name=os.path.basename(final_file),
                            mime="video/mp4",
                            use_container_width=True
                        )
                else:
                    st.error("Không tìm thấy file tải về.")
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

st.divider()
st.info("💡 Nén video dùng CRF 28 (chất lượng cao, dung lượng nhỏ). Có thể điều chỉnh CRF thấp hơn nếu muốn chất lượng tốt hơn.")
st.caption("Lần đầu deploy sẽ cài ffmpeg + packages (mất ~20s). Sau đó siêu nhanh!")
