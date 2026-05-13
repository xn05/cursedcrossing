class RegionTitle:
    def __init__(self, config, textures):
        self.config = config or {}
        self.textures = textures
        self.time = 0.0
        self.active = bool(self.config.get("enabled", False))

    def reset(self):
        self.time = 0.0
        self.active = bool(self.config.get("enabled", False))

    def update(self, dt):
        if not self.active:
            return
        duration = max(0.0, float(self.config.get("duration", 0.0)))
        fade = max(0.0, float(self.config.get("fade_duration", 0.0)))
        self.time += dt
        if self.time >= duration + fade:
            self.active = False
