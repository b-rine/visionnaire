import io

import numpy as np
import open_clip
import torch
import triton_python_backend_utils as pb_utils
from PIL import Image

EMBED_DIM = 768
_ZERO_EMBED = np.zeros((1, EMBED_DIM), dtype=np.float32)
_EMPTY_CAPTION = np.array([[b""]], dtype=object)


class TritonPythonModel:
    def initialize(self, args):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "coca_ViT-L-14",
            pretrained="mscoco_finetuned_laion2B-s13B-b90k",
        )
        self.model = self.model.to(self.device).eval()
        self.tokenizer = open_clip.get_tokenizer("coca_ViT-L-14")

    def execute(self, requests):
        responses = []
        for request in requests:
            raw_data = pb_utils.get_input_tensor_by_name(request, "input_data").as_numpy()[0][0]
            mode = pb_utils.get_input_tensor_by_name(request, "input_mode").as_numpy()[0][0].decode("utf-8")

            with torch.no_grad(), torch.cuda.amp.autocast():
                if mode == "caption":
                    image = self._load_image(raw_data)
                    generated = self.model.generate(image)
                    caption = self.tokenizer.decode(generated[0].tolist())
                    embed_out = pb_utils.Tensor("embedding", _ZERO_EMBED)
                    cap_out = pb_utils.Tensor("caption", np.array([[caption.encode("utf-8")]], dtype=object))

                elif mode == "encode_image":
                    image = self._load_image(raw_data)
                    embedding = self.model.encode_image(image, normalize=True)
                    embed_out = pb_utils.Tensor("embedding", embedding.cpu().float().numpy())
                    cap_out = pb_utils.Tensor("caption", _EMPTY_CAPTION)

                else:  # encode_text
                    text = raw_data.decode("utf-8")
                    tokens = self.tokenizer([text]).to(self.device)
                    embedding = self.model.encode_text(tokens, normalize=True)
                    embed_out = pb_utils.Tensor("embedding", embedding.cpu().float().numpy())
                    cap_out = pb_utils.Tensor("caption", _EMPTY_CAPTION)

            responses.append(pb_utils.InferenceResponse(output_tensors=[embed_out, cap_out]))
        return responses

    def _load_image(self, raw: bytes) -> torch.Tensor:
        image = self.preprocess(Image.open(io.BytesIO(raw)).convert("RGB"))
        return image.unsqueeze(0).to(self.device)

    def finalize(self):
        del self.model
        torch.cuda.empty_cache()
