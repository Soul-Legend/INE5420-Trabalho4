"""Drop-in replacement for Hunyuan3D's `custom_rasterizer` written in pure PyTorch.

The upstream package is a C++/CUDA extension. The Windows ROCm build of PyTorch
cannot link C++ extensions, so this module reimplements the same interface
(`rasterize`, `interpolate`) with tensor operations that run on any device.

It follows upstream's rasterizer.cpp exactly:
- clip -> screen: x_s = (x/w * 0.5 + 0.5) * (W - 1) + 0.5, same for y;
  depth z_s = z/w * 0.49999 + 0.5;
- a pixel (px, py) is covered when its centre (px + 0.5, py + 0.5) has all
  barycentric coordinates in [0, 1] (edges included);
- depth test: smallest quantised depth wins (z * 2^18), ties go to the lowest
  face index; findices holds face index + 1 (0 = empty);
- barycentrics returned are perspective-corrected (divided by w, renormalised).

Faces are processed in buckets by bounding-box size: a face whose box is at
most S x S pixels is tested against an S x S grid of candidate pixels, all
faces of the bucket at once, and the depth keys are merged with scatter_reduce.
"""

import torch

MAXINT = 2147483647
DEPTH_SCALE = 2 << 17


def _screen(pos, width, height):
    w = pos[:, 3:4]
    x = (pos[:, 0:1] / w * 0.5 + 0.5) * (width - 1) + 0.5
    y = (0.5 + 0.5 * pos[:, 1:2] / w) * (height - 1) + 0.5
    z = pos[:, 2:3] / w * 0.49999 + 0.5
    return torch.cat([x, y, z], dim=1)


def _barycentric(a, b, c, p):
    """Upstream calculateBarycentricCoordinate, vectorised. Shapes broadcast; last dim = 2."""
    def area2(u, v, t):
        return (t[..., 0] - u[..., 0]) * (v[..., 1] - u[..., 1]) - (v[..., 0] - u[..., 0]) * (t[..., 1] - u[..., 1])

    area = area2(a, b, c)
    safe = torch.where(area == 0, torch.ones_like(area), area)
    beta = area2(a, p, c) / safe
    gamma = area2(a, b, p) / safe
    alpha = 1.0 - beta - gamma
    bary = torch.stack([alpha, beta, gamma], dim=-1)
    return torch.where((area == 0).unsqueeze(-1), torch.full_like(bary, -1.0), bary)


def rasterize_image(V, F, D, width, height, occlusion_truncation=1e-6, use_depth_prior=0):
    device = V.device
    F = F.long()
    screen = _screen(V.float(), width, height)
    tri = screen[F]  # (nf, 3, 3)
    xy = tri[..., :2]
    x_min = xy[..., 0].min(dim=1).values
    x_max = xy[..., 0].max(dim=1).values
    y_min = xy[..., 1].min(dim=1).values
    y_max = xy[..., 1].max(dim=1).values
    # C++: for (int px = x_min; px < x_max + 1; ++px) -> int() truncates toward zero.
    px0 = torch.trunc(x_min).long()
    py0 = torch.trunc(y_min).long()
    nx = (torch.ceil(x_max + 1).long() - px0).clamp(min=0)
    ny = (torch.ceil(y_max + 1).long() - py0).clamp(min=0)
    inside_screen = (x_max >= 0) & (x_min < width) & (y_max >= 0) & (y_min < height)
    size = torch.maximum(nx, ny)

    empty = MAXINT * MAXINT + (MAXINT - 1)
    zbuffer = torch.full((height * width,), empty, dtype=torch.int64, device=device)
    depth_prior = None
    if use_depth_prior:
        depth_prior = (D.float().reshape(-1) * 0.49999 + 0.5 + occlusion_truncation).to(device)

    bucket = 1
    max_size = int(size.max().item()) if size.numel() else 0
    while bucket // 2 < max_size:
        sel = inside_screen & (size > bucket // 2) & (size <= bucket)
        idx = torch.nonzero(sel).squeeze(1)
        # Keep candidate tensors around 16M elements.
        chunk = max(1, (1 << 24) // (bucket * bucket))
        grid = torch.arange(bucket, device=device)
        gy, gx = torch.meshgrid(grid, grid, indexing="ij")
        gx, gy = gx.reshape(1, -1), gy.reshape(1, -1)
        for start in range(0, idx.numel(), chunk):
            faces = idx[start:start + chunk]
            px = px0[faces, None] + gx
            py = py0[faces, None] + gy
            valid = (gx < nx[faces, None]) & (gy < ny[faces, None])
            valid &= (px >= 0) & (px < width) & (py >= 0) & (py < height)
            p = torch.stack([px.float() + 0.5, py.float() + 0.5], dim=-1)
            t = tri[faces]
            bary = _barycentric(t[:, None, 0, :2], t[:, None, 1, :2], t[:, None, 2, :2], p)
            valid &= ((bary >= 0.0) & (bary <= 1.0)).all(dim=-1)
            depth = (bary * t[:, None, :, 2]).sum(dim=-1)
            pixel = py * width + px
            if depth_prior is not None:
                valid &= depth >= depth_prior[pixel.clamp(0, height * width - 1)]
            # unsigned C++ arithmetic: a negative quantised depth never wins
            valid &= depth >= 0
            z_q = (depth * DEPTH_SCALE).long()
            token = z_q * MAXINT + (faces[:, None] + 1)
            zbuffer.scatter_reduce_(0, pixel[valid], token[valid], reduce="amin")
        bucket *= 2

    f = zbuffer % MAXINT
    covered = f != (MAXINT - 1)
    findices = torch.where(covered, f, torch.zeros_like(f)).to(torch.int32)
    barycentric = torch.zeros((height * width, 3), dtype=torch.float32, device=device)
    pix = torch.nonzero(covered).squeeze(1)
    if pix.numel():
        face = f[pix] - 1
        p = torch.stack([(pix % width).float() + 0.5, (pix // width).float() + 0.5], dim=-1)
        t = tri[face]
        bary = _barycentric(t[:, 0, :2], t[:, 1, :2], t[:, 2, :2], p)
        w = V.float()[F[face], 3]  # (n, 3)
        bary = bary / w
        bary = bary / bary.sum(dim=-1, keepdim=True)
        barycentric[pix] = bary
    return findices.reshape(height, width), barycentric.reshape(height, width, 3)


def rasterize(pos, tri, resolution, clamp_depth=torch.zeros(0), use_depth_prior=0):
    assert pos.device == tri.device
    return rasterize_image(pos[0], tri, clamp_depth, resolution[1], resolution[0], 1e-6, use_depth_prior)


def interpolate(col, findices, barycentric, tri):
    f = findices - 1 + (findices == 0)
    vcol = col[0, tri.long()[f.long()]]
    result = barycentric.view(*barycentric.shape, 1) * vcol
    result = torch.sum(result, axis=-2)
    return result.view(1, *result.shape)
