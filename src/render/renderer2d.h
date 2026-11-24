#pragma once
#include "platform/types.h"
#include "resource/asset_proxy.h"
#include "resource/material.h"
#include "resource/mesh.h"
#include "resource/texture.h"

#include "compiled/warning_off.h"
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
#include "compiled/warning_on.h"

namespace smallcap
{
constexpr Float SCREEN_W = 240.0f;
constexpr Float SCREEN_H = 160.0f;
constexpr Int32 TILE = 16;

struct Color
{
    Float r = 1.0f;
    Float g = 1.0f;
    Float b = 1.0f;
    Float a = 1.0f;
};

struct DrawOptions
{
    Bool flipX = false;
    Bool flipY = false;
    Float scale = 1.0f;
    Color tint{};
    Float flash = 0.0f;
    // Screen-space draws ignore the camera (HUD, dialog).
    Bool screen = false;
};

using SpriteId = Int32;
constexpr SpriteId NO_SPRITE = -1;

struct Sprite
{
    resource::Mesh *mesh = nullptr;
    Float width = 0.0f;
    Float height = 0.0f;
    Float pivotX = 0.0f;
    Float pivotY = 0.0f;
};

// A tile layer baked into one engine mesh (one quad per tile), with an optional second
// mesh for animated tiles (water).
struct TileLayerMesh
{
    resource::Mesh *frames[2] = {nullptr, nullptr};
    Bool animated = false;
};

// Thin 2D layer over the engine renderer: every sprite is an engine mesh submitted to the
// opaque queue with a cached material; draw order is resolved through depth.
class Renderer2D final
{
  public:
    Bool Initialize();
    // Releases engine assets; must run before the engine's asset manager is destroyed.
    void Shutdown();
    void BeginFrame(Float brightness);
    void SetCamera(Float x, Float y);
    Float CameraX() const
    {
        return cameraX;
    }
    Float CameraY() const
    {
        return cameraY;
    }

    SpriteId Find(std::string_view name) const;
    const Sprite &Get(SpriteId id) const
    {
        return sprites[static_cast<size_t>(id)];
    }
    void Draw(SpriteId id, Float x, Float y, const DrawOptions &options = {});
    void Draw(std::string_view name, Float x, Float y, const DrawOptions &options = {});

    TileLayerMesh BuildTileLayer(
        const std::vector<UInt16> &tiles, Int32 width, Int32 height,
        const std::vector<UInt16> &animated_partner
    );
    void DrawTileLayer(const TileLayerMesh &layer, Int32 frame);

    void FillRect(Float x, Float y, Float w, Float h, const Color &color, Bool screen = true);

  private:
    resource::Material *GetMaterial(Bool tiles, const Color &tint, Float flash);

    resource::AssetProxy<resource::ShaderProgram> shaderProgram;
    resource::AssetProxy<resource::Texture> spriteTexture;
    resource::AssetProxy<resource::Texture> tileTexture;
    std::vector<Sprite> sprites;
    std::unordered_map<std::string, SpriteId> spriteByName;
    std::unordered_map<UInt64, resource::Material *> materials;
    SpriteId white = NO_SPRITE;
    Int32 tileColumns = 16;
    Float tileImageWidth = 256.0f;
    Float tileImageHeight = 256.0f;
    Float depth = 0.0f;
    Float cameraX = 0.0f;
    Float cameraY = 0.0f;
    Float brightness = 1.0f;
};
} // namespace smallcap
