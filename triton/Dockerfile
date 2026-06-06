FROM nvcr.io/nvidia/tritonserver:23.09-py3

RUN pip install --no-cache-dir \
    transformers==4.35.2 \
    Pillow==10.1.0 \
    torch==2.1.0+cu118 \
    torchvision==0.16.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118
