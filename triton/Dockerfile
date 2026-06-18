FROM nvcr.io/nvidia/tritonserver:23.09-py3

# Install PyTorch with CUDA 11.8 first so open_clip_torch doesn't override it
RUN pip install --no-cache-dir \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118

RUN pip install --no-cache-dir \
    open_clip_torch==2.24.0 \
    transformers==4.36.2 \
    Pillow==10.1.0 \
    ftfy
