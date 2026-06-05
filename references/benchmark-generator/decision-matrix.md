# Decision Matrix

This file used to document base-image / package-manager / Vulkan-ICD choices for the docker backend. The plugin is now uv-only; dependency-generator picks the Python version + dep set from the repo's own `pyproject.toml` / `uv.lock` / README, and there is no Vulkan ICD or `cudagl` base-image story to document.

If your benchmark needs a system-level apt package (libegl1 / libosmesa6 / libvulkan1) the InstallationPlan extractor emits a `# sudo apt install ...` comment in `setup_uv.sh` and surfaces the missing-libs hint to the user — see `references/dependency-generator/install-plan-schema.md` for the schema.

For benchmark-side decisions, the only ones still owned by `benchmark-generator` are:

- **`{{SMOKE_ENV_BUILD}}` / `{{SMOKE_ENV_BUILD_RENDER}}`** — pick from the repo's upstream example (see Step 1a in `agents/benchmark-generator.md`).
- **`{{VIDEO_FRAME_EXTRACT}}`** — per-benchmark expression that returns one RGB frame from the env state. Common patterns:
  - gymnasium: `env.render() if getattr(env, 'render_mode', None) == 'rgb_array' else None`
  - SAPIEN / ManiSkill: `env.render_cameras()[0]['rgb']`
  - robosuite / LIBERO: `obs.get('robot0_agentview_left_image')`
  - dm_control + shimmy: `env.render()`
- **`{{TASK_EXAMPLE}}`** — a valid task identifier wired into the rendered scripts as the `--task` default.

Everything else (Python version pin, CUDA wheel pin, system apt deps) is dependency-generator territory.
