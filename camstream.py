"""RTSP 카메라를 브라우저가 바로 보는 MJPEG(multipart) 로 바꿔 내보냅니다 (젯슨 GStreamer)"""
import os
import subprocess

kChunk = 65536
kBoundary = "frame"
# 젯슨 HW 디코더(NVMM) → nvvidconv 로 축소 → JPEG 프레임을 multipart 로
kPipeline = ("decodebin ! nvvidconv ! video/x-raw,width=640,height=360,format=I420 ! jpegenc quality=70"
             " ! multipartmux boundary=%s ! fdsink fd=1" % kBoundary)


def mjpeg(handler, query):
    url = query.get("url", [""])[0]
    is_valid = url.startswith("rtsp://") and '"' not in url and not any(c.isspace() for c in url)
    if not is_valid:
        handler.send(400, b"rtsp:// url required", "text/plain")
        return
    args = ["gst-launch-1.0", "-q", "rtspsrc", 'location="%s"' % url, "protocols=tcp", "latency=0", "!"] + kPipeline.split()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    handler.send_response(200)
    handler.send_header("Content-Type", "multipart/x-mixed-replace; boundary=" + kBoundary)
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    try:
        while True:
            data = os.read(proc.stdout.fileno(), kChunk)
            if not data:
                break
            handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        proc.kill()
        proc.wait()
