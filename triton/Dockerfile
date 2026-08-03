FROM nvcr.io/nvidia/tritonserver:26.07-py3

# Install PyTorch with CUDA 11.8 first so open_clip_torch doesn't override it,
# then the rest, in one layer (still two pip calls to preserve install order).
RUN pip install --no-cache-dir \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118 && \
    pip install --no-cache-dir \
    open_clip_torch==2.24.0 \
    transformers==4.36.2 \
    Pillow==10.1.0 \
    ftfy==6.3.1

RUN mkdir -p /home/triton-server/.cache/huggingface && \
    chown -R triton-server:triton-server /home/triton-server
USER triton-server

HEALTHCHECK --interval=10s --timeout=5s --retries=18 --start-period=90s \
    CMD ["curl", "-f", "http://localhost:8000/v2/health/ready"]
