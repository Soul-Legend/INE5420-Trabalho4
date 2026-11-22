import os, time, torch
import torch.nn.functional as F
torch.manual_seed(0)
dev = "cuda"
# correctness on a small case: flash/mem-efficient vs math
q = torch.randn(2, 5, 2048, 64, device=dev, dtype=torch.float16)
k, v = torch.randn_like(q), torch.randn_like(q)
from torch.nn.attention import sdpa_kernel, SDPBackend
with sdpa_kernel([SDPBackend.MATH]):
    ref = F.scaled_dot_product_attention(q, k, v)
for name, be in [("flash", SDPBackend.FLASH_ATTENTION), ("mem_efficient", SDPBackend.EFFICIENT_ATTENTION)]:
    try:
        with sdpa_kernel([be]):
            out = F.scaled_dot_product_attention(q, k, v)
        torch.cuda.synchronize()
        print(name, "ok, max diff vs math:", (out - ref).abs().max().item())
    except Exception as e:
        print(name, "unavailable:", str(e).splitlines()[0][:120])
# the real size: 6 views x 64x64 tokens, 5 heads, batch 2 (CFG)
L = 6 * 64 * 64
q = torch.randn(2, 5, L, 64, device=dev, dtype=torch.float16)
torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize(); t = time.time()
out = F.scaled_dot_product_attention(q, q, q)
torch.cuda.synchronize()
print(f"L={L}: {time.time() - t:.2f}s, peak {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB, finite={torch.isfinite(out).all().item()}")
