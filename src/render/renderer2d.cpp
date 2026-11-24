#include "render/renderer2d.h"

#include "graphics/renderer.h"
#include "graphics/transform.h"
#include "graphics/vertex_layout.h"
#include "math/evogine_math.h"
#include "resource/asset_manager.h"
#include "utils/logger.h"
#include "window/window_manager.h"

#include "compiled/warning_off.h"
#include <algorithm>
#include <cmath>
#include <nlohmann/json.hpp>
#include "compiled/warning_on.h"

namespace smallcap
{
namespace
{
constexpr Float DEPTH_FAR = 9.5f;
constexpr Float DEPTH_STEP = 0.00015f;

const VertexLayout &QuadLayout()
{
    static const VertexLayout layout{
        {VertexAttribute{VertexAttribute::Semantic::Position, VertexAttribute::Type::Float3},
         VertexAttribute{VertexAttribute::Semantic::UV, VertexAttribute::Type::Float2}}
    };
    return layout;
}

UInt64 PackKey(const Bool tiles, const Color &c, const Float flash)
{
    const auto q = [](const Float v) {
        return static_cast<UInt64>(std::lround(std::clamp(v, 0.0f, 1.0f) * 255.0f));
    };
    return q(c.r) | (q(c.g) << 8) | (q(c.b) << 16) | (q(c.a) << 24) | (q(flash) << 32) |
           (UInt64(tiles) << 40);
}

// Appends one textured quad. (x, y) is the top-left corner in game pixels (y down).
void AppendQuad(
    std::vector<Float> &vertices, std::vector<UInt32> &indices, const Float x, const Float y,
    const Float w, const Float h, const Float u0, const Float v0, const Float u1, const Float v1
)
{
    const auto base = static_cast<UInt32>(vertices.size() / 5);
    const Float quad[20] = {x,     -(y + h), 0.0f, u0, v1, x + w, -(y + h), 0.0f, u1, v1,
                            x + w, -y,       0.0f, u1, v0, x,     -y,       0.0f, u0, v0};
    vertices.insert(vertices.end(), quad, quad + 20);
    const UInt32 quad_indices[6] = {base, base + 1, base + 2, base + 2, base + 3, base};
    indices.insert(indices.end(), quad_indices, quad_indices + 6);
}
} // namespace

Bool Renderer2D::Initialize()
{
    auto *asset_manager = resource::AssetManager::GetInstance();
    shaderProgram = asset_manager->Load<resource::ShaderProgram>(
        resource::AssetPath("game://shaders/sprite.shaderprogram")
    );
    const resource::LoadOptions<resource::Texture> pixel_options{
        graphics::FilterMode::Nearest, graphics::WrapMode::Clamp
    };
    spriteTexture = asset_manager->Load<resource::Texture>(
        resource::AssetPath("game://textures/sprites.png"), pixel_options
    );
    tileTexture = asset_manager->Load<resource::Texture>(
        resource::AssetPath("game://textures/tiles.png"), pixel_options
    );
    auto atlas_json =
        asset_manager->Read<nlohmann::json>(resource::AssetPath("game://textures/sprites.json"));
    auto tileset_json =
        asset_manager->Read<nlohmann::json>(resource::AssetPath("game://textures/tileset.json"));
    if (!shaderProgram.isValid() || !spriteTexture.isValid() || !tileTexture.isValid() ||
        !atlas_json.has_value() || !tileset_json.has_value())
    {
        LOGERROR("Failed to load Small Cap's textures or shaders");
        return false;
    }

    const nlohmann::json &tileset = *tileset_json->Get();
    tileColumns = tileset["columns"].get<Int32>();
    tileImageWidth = tileset["imagewidth"].get<Float>();
    tileImageHeight = tileset["imageheight"].get<Float>();

    const nlohmann::json &atlas = *atlas_json->Get();
    const Float atlas_w = atlas["width"].get<Float>();
    const Float atlas_h = atlas["height"].get<Float>();
    for (const auto &[name, info] : atlas["sprites"].items())
    {
        Sprite sprite;
        const Float x = info["x"].get<Float>();
        const Float y = info["y"].get<Float>();
        sprite.width = info["w"].get<Float>();
        sprite.height = info["h"].get<Float>();
        sprite.pivotX = info["px"].get<Float>();
        sprite.pivotY = info["py"].get<Float>();
        std::vector<Float> vertices;
        std::vector<UInt32> indices;
        AppendQuad(
            vertices, indices, 0.0f, 0.0f, sprite.width, sprite.height, x / atlas_w, y / atlas_h,
            (x + sprite.width) / atlas_w, (y + sprite.height) / atlas_h
        );
        sprite.mesh = graphics::Renderer::GetInstance()->SetupMesh(
            reinterpret_cast<const Byte *>(vertices.data()),
            static_cast<UInt32>(vertices.size() * sizeof(Float)),
            reinterpret_cast<const Byte *>(indices.data()), static_cast<UInt32>(indices.size()),
            graphics::IndexType::UnsignedInt, QuadLayout()
        );
        spriteByName[name] = static_cast<SpriteId>(sprites.size());
        sprites.push_back(sprite);
    }

    white = Find("white");
    LOGINFO("Loaded %zu sprites", sprites.size());
    return white != NO_SPRITE;
}

void Renderer2D::Shutdown()
{
    materials.clear();
    shaderProgram = {};
    spriteTexture = {};
    tileTexture = {};
}

void Renderer2D::BeginFrame(const Float new_brightness)
{
    depth = DEPTH_FAR;
    brightness = new_brightness;
    auto &camera = graphics::Renderer::GetInstance()->GetCamera();
    camera.projection =
        math::GetOrthoProjectionMatrix(0.0f, SCREEN_W, -SCREEN_H, 0.0f, 0.0f, 10.0f);
    camera.view = Mat4::GetIdentity();
    camera.position = FVec4(0.0f, 0.0f, 0.0f, 0.0f);
    camera.previousPosition = camera.position;

    for (auto &[key, material] : materials)
    {
        material->Set("uBright", brightness);
    }
}

void Renderer2D::SetCamera(const Float x, const Float y)
{
    cameraX = std::floor(x);
    cameraY = std::floor(y);
}

SpriteId Renderer2D::Find(const std::string_view name) const
{
    const auto it = spriteByName.find(std::string(name));
    if (it == spriteByName.end())
    {
        return NO_SPRITE;
    }
    return it->second;
}

resource::Material *Renderer2D::GetMaterial(const Bool tiles, const Color &tint, const Float flash)
{
    const UInt64 key = PackKey(tiles, tint, flash);
    if (const auto it = materials.find(key); it != materials.end())
    {
        return it->second;
    }
    auto *material = new resource::Material(shaderProgram);
    material->Set("uMaterial.diffuse", tiles ? tileTexture : spriteTexture);
    material->Set("uTint", FVec4(tint.r, tint.g, tint.b, tint.a));
    material->Set("uFlash", flash);
    material->Set("uBright", brightness);
    MaterialState state = material->GetMaterialState();
    state.isDoubleSided = true;
    // The opaque queue draws in submission order and applies each material's state, so
    // translucent draws (shadows, overlays) blend over whatever was submitted before them.
    if (tint.a < 0.999f)
    {
        state.alphaMode = graphics::AlphaMode::Blend;
    }
    material->SetMaterialState(state);
    materials[key] = material;
    return material;
}

void Renderer2D::Draw(const SpriteId id, const Float x, const Float y, const DrawOptions &options)
{
    if (id == NO_SPRITE)
    {
        return;
    }
    const Sprite &sprite = sprites[static_cast<size_t>(id)];
    const Float s = options.scale;
    const Float ox = options.screen ? 0.0f : cameraX;
    const Float oy = options.screen ? 0.0f : cameraY;
    const Float pivot_x = options.flipX ? sprite.width - 1.0f - sprite.pivotX : sprite.pivotX;
    const Float pivot_y = options.flipY ? sprite.height - 1.0f - sprite.pivotY : sprite.pivotY;
    Float left = std::floor(x - ox) - std::floor(pivot_x * s);
    Float top = std::floor(y - oy) - std::floor(pivot_y * s);
    // Cull off-screen sprites early.
    if (left > SCREEN_W || top > SCREEN_H || left + sprite.width * s < 0.0f ||
        top + sprite.height * s < 0.0f)
    {
        return;
    }
    Float world_x = left;
    Float world_y = -top;
    if (options.flipX)
    {
        world_x += sprite.width * s;
    }
    if (options.flipY)
    {
        world_y -= sprite.height * s;
    }
    graphics::Transform transform;
    transform.worldPosition = FVec3(world_x, world_y, depth);
    transform.worldScale = FVec3(options.flipX ? -s : s, options.flipY ? -s : s, 1.0f);
    transform.worldRotation = Quat::GetIdentity();
    depth -= DEPTH_STEP;
    graphics::Renderer::GetInstance()->SubmitOpaqueMesh(
        sprite.mesh, GetMaterial(false, options.tint, options.flash), transform
    );
}

void Renderer2D::Draw(
    const std::string_view name, const Float x, const Float y, const DrawOptions &options
)
{
    Draw(Find(name), x, y, options);
}

TileLayerMesh Renderer2D::BuildTileLayer(
    const std::vector<UInt16> &tiles, const Int32 width, const Int32 height,
    const std::vector<UInt16> &animated_partner
)
{
    TileLayerMesh layer;
    const Float inset = 0.01f;
    for (Int32 frame = 0; frame < 2; ++frame)
    {
        std::vector<Float> vertices;
        std::vector<UInt32> indices;
        for (Int32 ty = 0; ty < height; ++ty)
        {
            for (Int32 tx = 0; tx < width; ++tx)
            {
                UInt16 id = tiles[static_cast<size_t>(ty * width + tx)];
                if (id == 0)
                {
                    continue;
                }
                if (frame == 1 && id < animated_partner.size() && animated_partner[id] != 0)
                {
                    id = animated_partner[id];
                    layer.animated = true;
                }
                const Float sx = static_cast<Float>((id % tileColumns) * TILE);
                const Float sy = static_cast<Float>((id / tileColumns) * TILE);
                AppendQuad(
                    vertices, indices, static_cast<Float>(tx * TILE),
                    static_cast<Float>(ty * TILE), TILE, TILE, (sx + inset) / tileImageWidth,
                    (sy + inset) / tileImageHeight, (sx + TILE - inset) / tileImageWidth,
                    (sy + TILE - inset) / tileImageHeight
                );
            }
        }
        if (vertices.empty())
        {
            continue;
        }
        layer.frames[frame] = graphics::Renderer::GetInstance()->SetupMesh(
            reinterpret_cast<const Byte *>(vertices.data()),
            static_cast<UInt32>(vertices.size() * sizeof(Float)),
            reinterpret_cast<const Byte *>(indices.data()), static_cast<UInt32>(indices.size()),
            graphics::IndexType::UnsignedInt, QuadLayout()
        );
    }
    return layer;
}

void Renderer2D::DrawTileLayer(const TileLayerMesh &layer, const Int32 frame)
{
    resource::Mesh *mesh = layer.frames[(layer.animated && frame % 2 == 1) ? 1 : 0];
    if (!mesh)
    {
        return;
    }
    graphics::Transform transform;
    transform.worldPosition = FVec3(-cameraX, cameraY, depth);
    transform.worldScale = FVec3(1.0f, 1.0f, 1.0f);
    transform.worldRotation = Quat::GetIdentity();
    depth -= DEPTH_STEP;
    graphics::Renderer::GetInstance()->SubmitOpaqueMesh(mesh, GetMaterial(true, {}, 0.0f), transform);
}

void Renderer2D::FillRect(
    const Float x, const Float y, const Float w, const Float h, const Color &color, const Bool screen
)
{
    if (white == NO_SPRITE || w <= 0.0f || h <= 0.0f)
    {
        return;
    }
    const Sprite &sprite = sprites[static_cast<size_t>(white)];
    const Float ox = screen ? 0.0f : cameraX;
    const Float oy = screen ? 0.0f : cameraY;
    graphics::Transform transform;
    transform.worldPosition = FVec3(std::floor(x - ox), -std::floor(y - oy), depth);
    transform.worldScale = FVec3(w / sprite.width, h / sprite.height, 1.0f);
    transform.worldRotation = Quat::GetIdentity();
    depth -= DEPTH_STEP;
    graphics::Renderer::GetInstance()->SubmitOpaqueMesh(
        sprite.mesh, GetMaterial(false, color, 0.0f), transform
    );
}
} // namespace smallcap
