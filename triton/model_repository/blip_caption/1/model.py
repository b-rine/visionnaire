import io

import numpy as np
import torch
import triton_python_backend_utils as pb_utils
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor


class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model_name = "Salesforce/blip-image-captioning-base"
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
        ).to(self.device)
        self.model.eval()

    def execute(self, requests):
        responses = []
        for request in requests:
            raw = pb_utils.get_input_tensor_by_name(request, "image_bytes")
            # dtype=object array, shape [1,1] for max_batch_size=1 and dims=[1]
            image_bytes = raw.as_numpy()[0][0]
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            inputs = self.processor(image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=50)
            caption = self.processor.decode(out[0], skip_special_tokens=True)

            out_tensor = pb_utils.Tensor(
                "caption",
                np.array([[caption.encode("utf-8")]], dtype=object),
            )
            responses.append(pb_utils.InferenceResponse(output_tensors=[out_tensor]))
        return responses

    def finalize(self):
        del self.model
        torch.cuda.empty_cache()
