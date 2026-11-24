#pragma once
#include "game/map.h"
#include "input/controls.h"
#include "math/random.h"

#include "compiled/warning_off.h"
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "compiled/warning_on.h"

namespace smallcap
{
constexpr Float TICK = 1.0f / 60.0f;

enum class Dir : UInt8
{
    DOWN,
    UP,
    LEFT,
    RIGHT
};

enum class Kind : UInt8
{
    BUSH,
    POT,
    CHEST,
    SIGN,
    NPC,
    DOOR,
    BLOCK,
    SWITCH,
    TORCH,
    PICKUP,
    SEED,
    BLOB,
    POD,
    BEETLE,
    BAT,
    ANT,
    BOSS,
    STUMP,
    PORTAL,
    WARP,
    TRIGGER,
    EFFECT
};

struct Entity
{
    Kind kind = Kind::EFFECT;
    Bool alive = true;
    // Waiting for its "showIf" condition (e.g. a chest that appears when a switch is pressed).
    Bool hidden = false;
    // Position of the pivot: bottom-centre for actors and objects.
    Float x = 0.0f;
    Float y = 0.0f;
    Float vx = 0.0f;
    Float vy = 0.0f;
    Float z = 0.0f;
    Float vz = 0.0f;
    // Collision box is [x - hw, x + hw] x [y - hh * 2, y].
    Float hw = 8.0f;
    Float hh = 8.0f;
    Int32 hp = 1;
    Dir dir = Dir::DOWN;
    Int32 state = 0;
    Float timer = 0.0f;
    Float timer2 = 0.0f;
    Float anim = 0.0f;
    Float hurt = 0.0f;
    Float knockX = 0.0f;
    Float knockY = 0.0f;
    Float knockT = 0.0f;
    Float homeX = 0.0f;
    Float homeY = 0.0f;
    Float life = -1.0f;
    Float scale = 1.0f;
    Int32 value = 0;
    Int32 room = -1;
    Int32 hitStamp = -1;
    // Persistent id ("map:objectid") used for opened chests, killed dungeon enemies, ...
    std::string flag;
    // Kind-specific variant: npc name, blob colour, door kind, item id, effect sprite.
    std::string variant;
    std::unordered_map<std::string, std::string> props;

    const std::string &Prop(const std::string &key) const
    {
        static const std::string empty;
        const auto it = props.find(key);
        return it == props.end() ? empty : it->second;
    }
};

enum class PState : UInt8
{
    NORMAL,
    SWING,
    SPIN,
    ROLL,
    HURT,
    HOLD,
    DEAD,
    SHRINK,
    GROW,
    SCRIPTED
};

struct Player
{
    Float x = 0.0f;
    Float y = 0.0f;
    Dir dir = Dir::DOWN;
    PState state = PState::NORMAL;
    Float t = 0.0f;
    Float anim = 0.0f;
    Bool moving = false;
    Float iframes = 0.0f;
    Float knockX = 0.0f;
    Float knockY = 0.0f;
    Int32 hp = 6;
    Int32 maxHp = 6;
    Bool charging = false;
    Float charge = 0.0f;
    Float pushT = 0.0f;
    Float rollCooldown = 0.0f;
    Float rollX = 0.0f;
    Float rollY = 0.0f;
    Float scale = 1.0f;
    Int32 swingStamp = 0;
    std::string holdItem;
};

enum class RequestType : UInt8
{
    NONE,
    DIALOG,
    ITEM,
    WARP,
    SHRINK,
    GROW,
    GAME_OVER
};

// Things the world asks the scene to do (show text, change map, ...).
struct Request
{
    RequestType type = RequestType::NONE;
    std::vector<std::string> pages;
    std::string item;
    std::string map;
    std::string spawn;
    // Item handed over after the dialog closes (an NPC giving something).
    std::string afterItem;
};

struct RoomScroll
{
    Bool active = false;
    Float t = 0.0f;
    Float fromX = 0.0f;
    Float fromY = 0.0f;
    Float toX = 0.0f;
    Float toY = 0.0f;
    Float playerVX = 0.0f;
    Float playerVY = 0.0f;
};

struct World
{
    Map map;
    TileInfo tileInfo;
    std::vector<Entity> entities;
    // Entities spawned during a tick; merged after the update so references stay valid.
    std::vector<Entity> spawned;
    Player player;
    std::unordered_set<std::string> flags;
    Int32 gems = 0;
    Int32 keys = 0;
    Bool bigKey = false;
    Bool hasSword = false;
    Float time = 0.0f;
    Float cameraX = 0.0f;
    Float cameraY = 0.0f;
    Int32 roomX = 0;
    Int32 roomY = 0;
    RoomScroll scroll;
    Float shake = 0.0f;
    Request request;
    std::string prompt;
    std::string spawnMap;
    std::string spawnName;
    math::Random rng{0xC0FFEEu};
    Float bossDeathTimer = -1.0f;
    Int32 tickCount = 0;
    // Test hook: skip regular enemies (SMALLCAP_PEACE).
    Bool peaceful = false;
};

// world.cpp
Bool HasFlag(const World &world, const std::string &flag);
Bool CheckCondition(const World &world, const std::string &condition);
void EnterMap(World &world, const std::string &map_name, const std::string &spawn, Renderer2D &renderer);
void UpdateWorld(World &world, const Controls &controls);
void ApplyItem(World &world, const std::string &item);
void UpdateCamera(World &world, Bool snap);
void PlacePlayerAtSpawn(World &world, const std::string &spawn);
Entity &SpawnEffect(World &world, const std::string &sprite, Float x, Float y, Float duration);
void SpawnDrop(World &world, Float x, Float y);
Bool BoxBlocked(const World &world, Float x0, Float y0, Float x1, Float y1, const Entity *ignore, Bool for_player);
Bool MoveActor(World &world, Entity &e, Float dx, Float dy);
Int32 RoomIndexAt(const World &world, Float x, Float y);
Bool RoomHasEnemies(const World &world, Int32 room);
Bool IsEnemy(Kind kind);
void DamageEnemy(World &world, Entity &e, Int32 damage, Float from_x, Float from_y);
void HurtPlayer(World &world, Int32 damage, Float from_x, Float from_y);

// enemies.cpp
void UpdateEnemy(World &world, Entity &e);

// render_world.cpp
void RenderWorld(World &world, Renderer2D &renderer);

inline Float DirX(const Dir d)
{
    return d == Dir::LEFT ? -1.0f : (d == Dir::RIGHT ? 1.0f : 0.0f);
}
inline Float DirY(const Dir d)
{
    return d == Dir::UP ? -1.0f : (d == Dir::DOWN ? 1.0f : 0.0f);
}
} // namespace smallcap
