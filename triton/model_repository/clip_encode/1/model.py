import io

import numpy as np
import torch
import triton_python_backend_utils as pb_utils
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = "openai/clip-vit-base-patch32"
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
        ).to(self.device)
        self.model.eval()

    def execute(self, requests):
        responses = []
        for request in requests:
            data_tensor = pb_utils.get_input_tensor_by_name(request, "input_data")
            mode_tensor = pb_utils.get_input_tensor_by_name(request, "input_mode")

            raw_data = data_tensor.as_numpy()[0][0]
            mode = mode_tensor.as_numpy()[0][0].decode("utf-8")

            with torch.no_grad():
                if mode == "image":
                    image = Image.open(io.BytesIO(raw_data)).convert("RGB")
                    inputs = self.processor(images=image, return_tensors="pt").to(self.device)
                    embedding = self.model.get_image_features(**inputs)
                else:
                    text = raw_data.decode("utf-8")
                    inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
                    embedding = self.model.get_text_features(**inputs)

            # L2-normalize so dot product == cosine similarity in Qdrant
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            embedding_np = embedding.cpu().float().numpy()[0]  # (512,)

            out_tensor = pb_utils.Tensor("embedding", embedding_np.reshape(1, 512))
            responses.append(pb_utils.InferenceResponse(output_tensors=[out_tensor]))
        return responses

    def finalize(self):
        del self.model
        torch.cuda.empty_cache()
