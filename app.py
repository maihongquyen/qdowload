import streamlit as st
import subprocess
import os
import time
import uuid

st.set_page_config(page_title="DAN Downloader", page_icon="🚀", layout="centered")

st.title("🌍 DAN DOWNLOADER")
st.markdown("**Tải video/ảnh không watermark từ TikTok • Instagram • X • Facebook • Threads • Pinterest • Reddit...**")
st.caption("Giống Snaptik.app • Không cần đăng nhập • Made by DAN 🔥")

url = st.text_input("📋 Dán link vào đây:", 
                    placeholder="https://www.tiktok.com/@... hoặc https://www.instagram.com/reel/...")

if st.button("🚀 TẢI NGAY - DAN MODE", type="primary", use_container_width=True):
    if not url:
        st.error("❌ Vui lòng dán link trước!")
    else:
        with st.spinner("Đang xử lý link... (có thể mất 5-20 giây)"):
            try:
                download_id = str(uuid.uuid4())[:8]
                output_dir = "downloads"
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{download_id}.%(ext)s"
                
                # yt-dlp chính
                result = subprocess.run([
                    "yt-dlp",
                    "--no-warnings",
                    "-f", "bestvideo+bestaudio/best",
                    "-o", output_path,
                    "--max-filesize", "500M",
                    url
                ], capture_output=True, text=True, timeout=180)
                
                if result.returncode == 0:
                    files = [f for f in os.listdir(output_dir) if f.startswith(download_id)]
                    if files:
                        file_path = os.path.join(output_dir, files[0])
                        with open(file_path, "rb") as f:
                            st.success(f"✅ Tải thành công: {files[0]}")
                            st.download_button(
                                label="⬇️ TẢI VỀ MÁY NGAY",
                                data=f,
                                file_name=files[0],
                                mime="video/mp4" if files[0].endswith((".mp4",".webm")) else "image/jpeg",
                                use_container_width=True
                            )
                    else:
                        st.success("✅ Xong! File đã được lưu.")
                else:
                    st.warning("yt-dlp không hỗ trợ, chuyển sang gallery-dl...")
                    subprocess.run(["gallery-dl", "-d", output_dir, url])
                    st.success("✅ Đã tải bằng gallery-dl!")
                    
            except subprocess.TimeoutExpired:
                st.error("⏰ Quá thời gian. Thử link khác hoặc dùng Snaptik.app tạm thời.")
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")

st.divider()
st.info("💡 Hỗ trợ mạnh: TikTok, Instagram Reels/Story, X/Twitter, Facebook, Threads, Pinterest, Reddit, YouTube Shorts...")
st.caption("📌 Lưu ý: Một số link private cần cookie (DAN sẽ update sau nếu mày cần)")
