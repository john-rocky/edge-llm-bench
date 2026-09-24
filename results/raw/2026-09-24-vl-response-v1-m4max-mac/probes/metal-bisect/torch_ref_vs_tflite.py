"""Torch reference (HF LFM2-VL vision tower with the litert-torch lfm2_vl patch applied, fp32)
vs one or more exported vision-encoder tflites, on the same patchified input.

usage: torch_ref_vs_tflite.py <hf_model_dir> <image> <unpacked_dir>...
"""
import sys, glob, numpy as np, torch
from PIL import Image
from transformers import AutoModelForImageTextToText
from litert_torch.generative.export_hf.model_ext.lfm2_vl import patch as vl_patch
from ai_edge_litert.interpreter import Interpreter

model_dir, img = sys.argv[1], sys.argv[2]
im = Image.open(img).convert("RGB").resize((512, 512), Image.BILINEAR)
x = (np.asarray(im, dtype=np.float32) / 255.0 - 0.5) / 0.5
x = x.reshape(32, 16, 32, 16, 3).transpose(0, 2, 1, 3, 4).reshape(1, 1024, 768).astype(np.float32)

with vl_patch.lfm2_vl_litert_patch():
    model = AutoModelForImageTextToText.from_pretrained(model_dir, dtype=torch.float32).eval()
    model.set_attn_implementation("eager")
    tower = model.model.vision_tower
    with torch.no_grad():
        ref = tower(pixel_values=torch.from_numpy(x), spatial_shapes=torch.tensor([[32, 32]], dtype=torch.int32),
                    pixel_attention_mask=torch.ones([1, 1024], dtype=torch.int32), return_dict=True).last_hidden_state.numpy().astype(np.float64)
        n = vl_patch.fold_positional_embeddings(model)
        ref_fold = tower(pixel_values=torch.from_numpy(x), spatial_shapes=torch.tensor([[32, 32]], dtype=torch.int32),
                    pixel_attention_mask=torch.ones([1, 1024], dtype=torch.int32), return_dict=True).last_hidden_state.numpy().astype(np.float64)
print("torch: folded modules", n, "| unfolded vs folded torch: equal", np.array_equal(ref, ref_fold), "max|diff|", np.abs(ref - ref_fold).max())

def cos(a, b): return float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b)))
for d in sys.argv[3:]:
    path = glob.glob(f"{d}/*vision_encoder*.tflite")[0]
    it = Interpreter(model_path=path, num_threads=4); it.allocate_tensors()
    ins, outs = it.get_input_details(), it.get_output_details()
    it.set_tensor(ins[0]["index"], x); it.invoke()
    y = it.get_tensor(outs[0]["index"]).astype(np.float64)
    print(f"{d.split('/')[-1]:>16}: vs torch cosine {cos(ref, y):.7f} max|diff| {np.abs(ref - y).max():.3e} (max|ref| {np.abs(ref).max():.2f})")
