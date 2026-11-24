#include "game/world.h"

#include "compiled/warning_off.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include "compiled/warning_on.h"

namespace smallcap
{
namespace
{
enum class Ori : UInt8
{
    R,
    DR,
    D,
    DL,
    L,
    UL,
    U,
    UR
};

struct SwordPose
{
    Ori ori;
    Float ox;
    Float oy;
};

// Hilt positions relative to the player's feet for the three swing phases.
const SwordPose SWING[4][3] = {
    /* DOWN  */ {{Ori::R, 5, -9}, {Ori::DR, 4, -7}, {Ori::D, 1, -6}},
    /* UP    */ {{Ori::L, -5, -12}, {Ori::UL, -4, -14}, {Ori::U, -1, -15}},
    /* LEFT  */ {{Ori::U, -3, -15}, {Ori::UL, -4, -13}, {Ori::L, -5, -8}},
    /* RIGHT */ {{Ori::U, 3, -15}, {Ori::UR, 4, -13}, {Ori::R, 5, -8}},
};

const char *DirName(const Dir d)
{
    switch (d)
    {
    case Dir::UP:
        return "up";
    case Dir::LEFT:
    case Dir::RIGHT:
        return "right";
    case Dir::DOWN:
    default:
        return "down";
    }
}

void DrawSword(Renderer2D &r, const Ori ori, const Float x, const Float y, const Float flash)
{
    DrawOptions o;
    o.flash = flash;
    const char *name = "sword_h";
    switch (ori)
    {
    case Ori::R:
        break;
    case Ori::L:
        o.flipX = true;
        break;
    case Ori::D:
        name = "sword_v";
        break;
    case Ori::U:
        name = "sword_v";
        o.flipY = true;
        break;
    case Ori::DR:
        name = "sword_d";
        break;
    case Ori::DL:
        name = "sword_d";
        o.flipX = true;
        break;
    case Ori::UR:
        name = "sword_d";
        o.flipY = true;
        break;
    case Ori::UL:
        name = "sword_d";
        o.flipX = true;
        o.flipY = true;
        break;
    }
    r.Draw(name, x, y, o);
}

Bool SwordBehind(const Ori ori)
{
    return ori == Ori::U || ori == Ori::UL || ori == Ori::UR;
}

void TipOffset(const Ori ori, Float &tx, Float &ty)
{
    const Float angle = static_cast<Float>(static_cast<Int32>(ori)) * 0.7854f;
    tx = std::cos(angle) * 13.0f;
    ty = std::sin(angle) * 13.0f;
}

void DrawPlayer(const World &world, Renderer2D &r)
{
    const Player &p = world.player;
    const Bool blink = p.iframes > 0.0f && p.state != PState::HURT && (world.tickCount / 3) % 2 == 0;
    DrawOptions o;
    o.flipX = p.dir == Dir::LEFT;
    o.scale = p.scale;
    o.flash = p.state == PState::HURT ? 0.8f : 0.0f;
    if (p.charging && p.charge >= 0.7f && (world.tickCount / 4) % 2 == 0)
    {
        o.flash = 0.35f;
    }

    if (p.state != PState::DEAD || p.t < 1.2f)
    {
        DrawOptions shadow;
        shadow.tint = {0.0f, 0.0f, 0.0f, 0.45f};
        shadow.scale = p.scale;
        r.Draw("shadow", p.x, p.y, shadow);
    }

    // Sword pose for this frame (if any).
    Bool has_sword = false;
    SwordPose pose{};
    if (p.state == PState::SWING)
    {
        const Int32 phase = std::min(2, static_cast<Int32>(p.t / (0.22f / 3.0f)));
        pose = SWING[static_cast<Int32>(p.dir)][phase];
        has_sword = true;
    }
    else if (p.state == PState::SPIN)
    {
        static const Ori start[4] = {Ori::D, Ori::U, Ori::L, Ori::R};
        const Int32 step = static_cast<Int32>(p.t / 0.45f * 9.0f);
        const Int32 idx = (static_cast<Int32>(start[static_cast<Int32>(p.dir)]) + step) % 8;
        const Float angle = static_cast<Float>(idx) * 0.7854f;
        pose = {static_cast<Ori>(idx), std::cos(angle) * 5.0f, -8.0f + std::sin(angle) * 4.0f};
        has_sword = true;
    }
    else if (p.charging && p.state == PState::NORMAL)
    {
        pose = SWING[static_cast<Int32>(p.dir)][2];
        has_sword = true;
    }

    const Float sword_flash = (p.charging && p.charge >= 0.7f) ? 0.6f : 0.0f;
    if (has_sword && SwordBehind(pose.ori) && !blink)
    {
        DrawSword(r, pose.ori, p.x + pose.ox, p.y + pose.oy, sword_flash);
    }

    if (!blink)
    {
        std::string name;
        Float draw_x = p.x;
        Float draw_y = p.y;
        switch (p.state)
        {
        case PState::SWING:
        case PState::SPIN:
            name = std::string("hero_atk_") + DirName(p.dir);
            if (p.state == PState::SPIN)
            {
                static const Dir order[4] = {Dir::DOWN, Dir::LEFT, Dir::UP, Dir::RIGHT};
                const Dir d = order[static_cast<Int32>(p.t / 0.45f * 4.0f) % 4];
                name = std::string("hero_atk_") + DirName(d);
                o.flipX = d == Dir::LEFT;
            }
            break;
        case PState::ROLL:
            name = "hero_roll_" + std::to_string(static_cast<Int32>(p.t * 14.0f) % 4);
            o.flipX = p.rollX < 0.0f;
            break;
        case PState::HOLD:
            name = "hero_hold";
            o.flipX = false;
            break;
        case PState::DEAD:
        {
            if (p.t < 1.2f)
            {
                static const Dir order[4] = {Dir::DOWN, Dir::LEFT, Dir::UP, Dir::RIGHT};
                const Dir d = order[static_cast<Int32>(p.t * 10.0f) % 4];
                name = std::string("hero_") + DirName(d) + "_0";
                o.flipX = d == Dir::LEFT;
            }
            else
            {
                name = "hero_lie";
                o.flipX = false;
            }
            break;
        }
        default:
        {
            Int32 frame = 0;
            if (p.moving)
            {
                frame = static_cast<Int32>(p.anim * (p.charging ? 5.0f : 8.0f)) % 4;
            }
            name = std::string("hero_") + DirName(p.dir) + "_" + std::to_string(frame);
            break;
        }
        }
        if (p.state == PState::SHRINK || p.state == PState::GROW)
        {
            name = "hero_down_0";
            o.flipX = false;
            o.flash = (world.tickCount / 3) % 2 == 0 ? 0.6f : 0.0f;
        }
        r.Draw(name, draw_x, draw_y, o);
    }

    if (has_sword && !SwordBehind(pose.ori) && !blink)
    {
        DrawSword(r, pose.ori, p.x + pose.ox, p.y + pose.oy, sword_flash);
    }
    if (has_sword && p.charging && p.charge >= 0.7f)
    {
        Float tx, ty;
        TipOffset(pose.ori, tx, ty);
        r.Draw("sparkle_" + std::to_string((world.tickCount / 4) % 3), p.x + pose.ox + tx,
               p.y + pose.oy + ty, {});
    }
    if (p.state == PState::HOLD && !p.holdItem.empty())
    {
        r.Draw(p.holdItem, p.x, p.y - 22.0f, {});
    }
}

std::string PickupSprite(const Entity &e, const Int32 tick)
{
    const std::string &v = e.variant;
    if (v.rfind("gem_", 0) == 0)
    {
        return v + "_" + std::to_string((tick / 10) % 2);
    }
    if (v == "heartc")
    {
        return "heart_container";
    }
    if (v == "sunstone")
    {
        return "sunstone_" + std::to_string((tick / 12) % 2);
    }
    if (v == "key" || v == "bigkey" || v == "heart")
    {
        return v;
    }
    return "gem_g_0";
}

void DrawEntity(const World &world, const Entity &e, Renderer2D &r)
{
    DrawOptions o;
    o.flash = e.hurt > 0.0f && (world.tickCount / 2) % 2 == 0 ? 0.85f : 0.0f;
    DrawOptions shadow;
    shadow.tint = {0.0f, 0.0f, 0.0f, 0.45f};
    const Int32 tick = world.tickCount;
    switch (e.kind)
    {
    case Kind::BUSH:
        r.Draw("bush", e.x, e.y, o);
        break;
    case Kind::POT:
        r.Draw("pot", e.x, e.y, o);
        break;
    case Kind::CHEST:
        r.Draw(e.state == 0 ? "chest_closed" : "chest_open", e.x, e.y, o);
        break;
    case Kind::SIGN:
        r.Draw("sign", e.x, e.y, o);
        break;
    case Kind::BLOCK:
        r.Draw("block", e.x, e.y, o);
        break;
    case Kind::TORCH:
        r.Draw("torch_" + std::to_string((tick / 8) % 2), e.x, e.y + 2.0f, o);
        break;
    case Kind::NPC:
    {
        const Bool dirs = e.variant == "tobi" || e.variant == "guard";
        const Dir d = dirs ? e.dir : Dir::DOWN;
        Int32 frame = 0;
        if (e.state == 1)
        {
            frame = static_cast<Int32>(e.anim * 8.0f) % 4;
        }
        else if (static_cast<Int32>(e.anim * 1.5f) % 4 == 3)
        {
            frame = 1;
        }
        o.flipX = d == Dir::LEFT;
        r.Draw("shadow", e.x, e.y, shadow);
        r.Draw(e.variant + "_" + DirName(d) + "_" + std::to_string(frame), e.x, e.y, o);
        break;
    }
    case Kind::DOOR:
    {
        if (e.state != 0)
        {
            break;
        }
        const Bool tall = e.hh > e.hw;
        const std::string name = "door_" + e.variant + (tall ? "_h" : "_v");
        const Float x0 = e.x - e.hw;
        const Float y0 = e.y - e.hh * 2.0f;
        for (Float ty = y0; ty < e.y - 1.0f; ty += TILE)
        {
            for (Float tx = x0; tx < e.x + e.hw - 1.0f; tx += TILE)
            {
                r.Draw(name, tx + 8.0f, ty + 16.0f, o);
            }
        }
        break;
    }
    case Kind::PICKUP:
    {
        if (e.life > 0.0f && e.life < 2.5f && (tick / 3) % 2 == 0)
        {
            break;
        }
        const Bool floating = e.variant == "sunstone" || e.variant == "heartc";
        const Float bob = floating && e.vz == 0.0f ? std::sin(world.time * 3.0f) * 2.0f + 3.0f : 0.0f;
        r.Draw("shadow", e.x, e.y, shadow);
        r.Draw(PickupSprite(e, tick), e.x, e.y - e.z - bob, o);
        if (e.variant == "sunstone" && tick % 20 < 10)
        {
            r.Draw("sparkle_" + std::to_string((tick / 4) % 3), e.x + 8.0f, e.y - 22.0f - bob, {});
        }
        break;
    }
    case Kind::SEED:
        r.Draw("shadow", e.x, e.y + 2.0f, shadow);
        r.Draw("seed", e.x, e.y - 4.0f, o);
        break;
    case Kind::BLOB:
    {
        Int32 frame = 0;
        if (e.state == 1)
            frame = 2;
        else if (e.anim < 0.12f)
            frame = 1;
        else
            frame = static_cast<Int32>(e.anim * 3.0f) % 2;
        r.Draw("shadow", e.x, e.y, shadow);
        r.Draw("blob_" + e.variant + "_" + std::to_string(frame), e.x, e.y - e.z, o);
        break;
    }
    case Kind::POD:
        o.flipX = e.dir == Dir::LEFT;
        r.Draw(std::string("pod_") + DirName(e.dir) + "_" + std::to_string(e.state == 1 ? 1 : 0),
               e.x, e.y, o);
        break;
    case Kind::BEETLE:
    case Kind::ANT:
        o.flipX = e.dir == Dir::LEFT;
        r.Draw(std::string(e.kind == Kind::BEETLE ? "beetle_" : "ant_") + DirName(e.dir) + "_" +
                   std::to_string(static_cast<Int32>(e.anim * 7.0f) % 2),
               e.x, e.y, o);
        break;
    case Kind::BAT:
        r.Draw("shadow", e.x, e.y, shadow);
        r.Draw("bat_" + std::to_string(e.state == 0 ? 1 : static_cast<Int32>(e.anim * 9.0f) % 2),
               e.x, e.y - e.z, o);
        break;
    case Kind::BOSS:
    {
        DrawOptions big_shadow = shadow;
        r.Draw("shadow_big", e.x, e.y - 1.0f, big_shadow);
        Float sx = e.x;
        if (e.state == 1)
        {
            sx += (tick / 2) % 2 == 0 ? -1.0f : 1.0f;
        }
        std::string name;
        if (e.state == 4 || e.state == 5)
        {
            name = "boss_flip_" + std::to_string((tick / 6) % 2);
            if (e.state == 4 && e.timer < 0.8f)
            {
                sx += (tick / 2) % 2 == 0 ? -1.0f : 1.0f;
            }
        }
        else
        {
            o.flipX = e.dir == Dir::LEFT;
            const Float rate = e.state == 2 ? 16.0f : 6.0f;
            name = std::string("boss_") + DirName(e.dir) + "_" +
                   std::to_string(static_cast<Int32>(e.anim * rate) % 2);
        }
        if (e.state == 9)
        {
            o.flash = (tick / 3) % 2 == 0 ? 0.9f : 0.0f;
        }
        r.Draw(name, sx, e.y, o);
        break;
    }
    case Kind::EFFECT:
    {
        if (e.variant == "leaf")
        {
            r.Draw("leaf_" + std::to_string((tick / 5) % 2), e.x, e.y, o);
            break;
        }
        if (e.variant == "shard")
        {
            r.Draw("shard", e.x, e.y, o);
            break;
        }
        const Float t = 1.0f - std::max(0.0f, e.life) / std::max(0.001f, e.timer);
        const Int32 frame = std::min(e.value - 1, static_cast<Int32>(t * static_cast<Float>(e.value)));
        r.Draw(e.variant + "_" + std::to_string(frame), e.x, e.y, o);
        break;
    }
    default:
        break;
    }
}

Bool IsFlat(const Entity &e)
{
    return e.kind == Kind::SWITCH || e.kind == Kind::PORTAL ||
           (e.kind == Kind::EFFECT && e.variant == "dust");
}

Bool IsOverlay(const Entity &e)
{
    return e.kind == Kind::EFFECT && e.variant != "dust";
}
} // namespace

void RenderWorld(World &world, Renderer2D &r)
{
    Float sx = 0.0f;
    Float sy = 0.0f;
    if (world.shake > 0.0f)
    {
        sx = static_cast<Float>((world.tickCount * 7) % 5 - 2);
        sy = static_cast<Float>((world.tickCount * 3) % 3 - 1);
    }
    r.SetCamera(world.cameraX + sx, world.cameraY + sy);
    r.DrawTileLayer(world.map.layer, static_cast<Int32>(world.time * 2.0f));

    // Flat things on the floor first.
    for (const Entity &e : world.entities)
    {
        if (!e.alive || e.hidden || !IsFlat(e))
        {
            continue;
        }
        if (e.kind == Kind::SWITCH)
        {
            const Bool down = e.state == 1 || CheckCondition(world, e.Prop("target"));
            r.Draw(down ? "switch_down" : "switch_up", e.x, e.y, {});
        }
        else if (e.kind == Kind::PORTAL)
        {
            r.Draw("portal_" + std::to_string((world.tickCount / 6) % 4), e.x, e.y - e.hh, {});
        }
        else
        {
            const Float t = 1.0f - std::max(0.0f, e.life) / std::max(0.001f, e.timer);
            r.Draw("dust_" + std::to_string(t < 0.5f ? 0 : 1), e.x, e.y, {});
        }
    }
    // Stump shimmer once the player can use it.
    for (const Entity &e : world.entities)
    {
        if (e.kind == Kind::STUMP && world.hasSword && (world.tickCount / 8) % 3 != 0)
        {
            const Float a = world.time * 2.0f;
            r.Draw("sparkle_" + std::to_string((world.tickCount / 5) % 3),
                   e.x + std::cos(a) * 9.0f, e.y - e.hh + std::sin(a) * 5.0f, {});
        }
    }

    // Y-sorted actors and objects.
    std::vector<const Entity *> sorted;
    sorted.reserve(world.entities.size());
    for (const Entity &e : world.entities)
    {
        if (e.alive && !e.hidden && !IsFlat(e) && !IsOverlay(e))
        {
            sorted.push_back(&e);
        }
    }
    std::stable_sort(sorted.begin(), sorted.end(),
                     [](const Entity *a, const Entity *b) { return a->y < b->y; });
    Bool player_drawn = false;
    for (const Entity *e : sorted)
    {
        if (!player_drawn && e->y > world.player.y)
        {
            DrawPlayer(world, r);
            player_drawn = true;
        }
        DrawEntity(world, *e, r);
    }
    if (!player_drawn)
    {
        DrawPlayer(world, r);
    }
    for (const Entity &e : world.entities)
    {
        if (e.alive && IsOverlay(e))
        {
            DrawEntity(world, e, r);
        }
    }
}

} // namespace smallcap
