#include "game/game_scene.h"

#include "audio/sound.h"
#include "core/application.h"
#include "graphics/renderer.h"
#include "utils/logger.h"

#include "compiled/warning_off.h"
#include <stb/stb_image_write.h>
#include "compiled/warning_on.h"

#include "compiled/warning_off.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <sstream>
#include "compiled/warning_on.h"

namespace smallcap
{
namespace
{
constexpr Float FADE_TIME = 0.3f;
constexpr size_t LINE_CHARS = 34;
constexpr size_t PAGE_LINES = 3;
constexpr Float TYPE_SPEED = 55.0f;

struct ItemDef
{
    const Char *id;
    const Char *sprite;
    const Char *text;
};

const ItemDef ITEMS[] = {
    {"sword", "item_sword",
     "You got Elder Bram's old sword!|Press Z to swing it. Hold Z to charge, then let go for a "
     "spin attack!|Press C to roll."},
    {"key", "key", "You found a small key!|It opens a locked door somewhere in this dungeon."},
    {"bigkey", "bigkey", "You got the Big Key!|It opens the great door of Root Hollow's master."},
    {"heartc", "heart_container",
     "You got a Heart Container!|Your life grew by one heart, and you are fully healed."},
    {"gems20", "gem_r_0", "You found 20 gems!"},
    {"gems50", "gem_r_0", "You found 50 gems! What a haul!"},
    {"sunstone", "sunstone_0",
     "You got the Sunstone!|Its warm light pours through the roots of the hollow..."},
};

const ItemDef *FindItem(const std::string &id)
{
    for (const ItemDef &item : ITEMS)
    {
        if (id == item.id)
        {
            return &item;
        }
    }
    return nullptr;
}

std::vector<std::string> SplitPages(const std::string &text)
{
    std::vector<std::string> out;
    std::string current;
    for (const char c : text)
    {
        if (c == '|')
        {
            out.push_back(current);
            current.clear();
        }
        else
        {
            current += c;
        }
    }
    if (!current.empty())
    {
        out.push_back(current);
    }
    return out;
}

std::vector<std::string> Wrap(const std::string &text)
{
    std::vector<std::string> lines;
    std::istringstream paragraphs(text);
    std::string paragraph;
    while (std::getline(paragraphs, paragraph, '\n'))
    {
        std::istringstream words(paragraph);
        std::string word;
        std::string line;
        while (words >> word)
        {
            if (!line.empty() && line.size() + 1 + word.size() > LINE_CHARS)
            {
                lines.push_back(line);
                line.clear();
            }
            line += (line.empty() ? "" : " ") + word;
        }
        lines.push_back(line);
    }
    return lines;
}

} // namespace

GameScene::GameScene(Renderer2D *renderer_2d, GameUi *game_ui) : renderer(renderer_2d), ui(game_ui)
{
    if (!LoadTileInfo(world.tileInfo))
    {
        LOGERROR("Tile info failed to load");
    }
    EnterMap(world, "village", "start", *renderer);
    PlayMusic(Music::TITLE);
    if (const char *input = std::getenv("SMALLCAP_INPUT"))
    {
        std::stringstream stream(input);
        std::string token;
        while (stream >> token)
        {
            const size_t colon = token.find(':');
            if (colon == std::string::npos)
            {
                continue;
            }
            script.push_back({token.substr(0, colon), std::atoi(token.c_str() + colon + 1)});
        }
    }
    if (const char *shots = std::getenv("SMALLCAP_SHOTS"))
    {
        std::stringstream stream(shots);
        std::string token;
        while (std::getline(stream, token, ','))
        {
            shotTicks.push_back(std::atoi(token.c_str()));
        }
    }
    if (std::getenv("SMALLCAP_AUTOSTART") || std::getenv("SMALLCAP_MAP"))
    {
        NewGame();
    }
}

void GameScene::NewGame()
{
    world.flags.clear();
    world.gems = 0;
    world.keys = 0;
    world.bigKey = false;
    world.hasSword = false;
    world.player = Player{};
    world.map.name.clear();
    playTime = 0.0f;
    pendingItem.clear();
    pendingShrink = pendingGrow = pendingEnding = false;

    // Debug/test hooks: jump straight into an area.
    const char *map = std::getenv("SMALLCAP_MAP");
    const char *spawn = std::getenv("SMALLCAP_SPAWN");
    if (std::getenv("SMALLCAP_SWORD"))
    {
        ApplyItem(world, "sword");
    }
    if (const char *flags = std::getenv("SMALLCAP_FLAGS"))
    {
        std::stringstream stream(flags);
        std::string flag;
        while (std::getline(stream, flag, ','))
        {
            world.flags.insert(flag);
            if (flag == "bigkey")
                world.bigKey = true;
            if (flag == "key")
                world.keys++;
        }
    }
    world.peaceful = std::getenv("SMALLCAP_PEACE") != nullptr;
    EnterMap(world, map ? map : "village", spawn ? spawn : "start", *renderer);
    if (const char *pos = std::getenv("SMALLCAP_POS"))
    {
        Float tx = 0.0f;
        Float ty = 0.0f;
        if (std::sscanf(pos, "%f,%f", &tx, &ty) == 2)
        {
            world.player.x = tx * TILE;
            world.player.y = ty * TILE;
            world.roomX = static_cast<Int32>(std::floor(world.player.x / SCREEN_W));
            world.roomY = static_cast<Int32>(std::floor((world.player.y - 4.0f) / SCREEN_H));
            UpdateCamera(world, true);
        }
    }
    UpdateMusic();
    phase = Phase::FADE_IN;
    phaseTime = 0.0f;
    if (!map)
    {
        world.request.type = RequestType::DIALOG;
        world.request.pages = SplitPages(
            "Capo: Pip! Psst, Pip! Wake up, sleepyhead!|Capo: Yes, it's me, Capo, the smartest hat "
            "in Hearthwood. Elder Bram wants to see us in the village square!|Capo: Use the arrow "
            "keys to walk. Press X to talk to folks. Let's go!"
        );
    }
    if (std::getenv("SMALLCAP_ENDING"))
    {
        // Test hook: jump straight to the ending.
        world.request = Request{};
        phase = Phase::ENDING;
        phaseTime = 0.0f;
        PlayMusic(Music::ENDING);
    }
}

void GameScene::ApplyScript()
{
    if (scriptIndex >= script.size())
    {
        return;
    }
    const ScriptStep &step = script[scriptIndex];
    const auto set = [&](Button &b, const char *name) {
        const Bool down = step.buttons.find(name) != std::string::npos;
        b.pressed = down && (scriptFrame == 0 || !b.down);
        b.released = !down && b.down;
        b.down = down;
    };
    set(controls.left, "left");
    set(controls.right, "right");
    set(controls.up, "up");
    set(controls.down, "down");
    set(controls.sword, "sword");
    set(controls.action, "action");
    set(controls.roll, "roll");
    set(controls.start, "start");
    if (++scriptFrame >= step.frames)
    {
        scriptFrame = 0;
        scriptIndex++;
    }
}

void GameScene::Update(const double elapsed_seconds)
{
    if (script.empty())
    {
        PollControls(controls);
    }
    accumulator += std::min(elapsed_seconds, 0.1);
    Int32 steps = 0;
    while (accumulator >= TICK && steps < 4)
    {
        if (!script.empty())
        {
            ApplyScript();
        }
        Tick();
        ConsumePresses(controls);
        accumulator -= TICK;
        ++steps;
    }
}

void GameScene::UpdateMusic()
{
    Music desired = world.map.music;
    if (world.map.rooms)
    {
        const Int32 room = RoomIndexAt(world, world.player.x, world.player.y - 4.0f);
        for (const Entity &e : world.entities)
        {
            if (e.kind == Kind::BOSS && e.room == room)
            {
                desired = e.state == 9 ? Music::NONE : Music::BOSS;
            }
        }
        if (HasFlag(world, "boss_dead") && room == 1)
        {
            desired = Music::NONE;
        }
    }
    PlayMusic(desired);
}

void GameScene::OpenDialog(const std::vector<std::string> &source_pages)
{
    pages.clear();
    for (const std::string &p : source_pages)
    {
        const std::vector<std::string> wrapped = Wrap(p);
        for (size_t i = 0; i < wrapped.size(); i += PAGE_LINES)
        {
            std::string chunk;
            for (size_t j = i; j < std::min(wrapped.size(), i + PAGE_LINES); ++j)
            {
                chunk += (j == i ? "" : "\n") + wrapped[j];
            }
            pages.push_back(chunk);
        }
    }
    if (pages.empty())
    {
        FinishDialog();
        return;
    }
    page = 0;
    typed = 0.0f;
    phase = Phase::DIALOG;
    phaseTime = 0.0f;
}

void GameScene::AdvanceDialog()
{
    const size_t total = pages[page].size();
    if (typed < static_cast<Float>(total))
    {
        typed = static_cast<Float>(total);
        return;
    }
    PlaySfx(Sfx::MENU, 0.5f);
    page++;
    typed = 0.0f;
    if (page >= pages.size())
    {
        FinishDialog();
    }
}

void GameScene::FinishDialog()
{
    phase = Phase::PLAY;
    phaseTime = 0.0f;
    world.player.state = world.player.state == PState::HOLD ? PState::NORMAL : world.player.state;
    world.player.holdItem.clear();
    if (!pendingItem.empty())
    {
        const std::string item = pendingItem;
        pendingItem.clear();
        StartItemGet(item);
        return;
    }
    if (pendingShrink)
    {
        pendingShrink = false;
        phase = Phase::SHRINK;
        phaseTime = 0.0f;
        world.player.state = PState::SHRINK;
        PlaySfx(Sfx::SHRINK);
        PlayMusic(Music::NONE);
        return;
    }
    if (pendingEnding)
    {
        pendingEnding = false;
        phase = Phase::ENDING;
        phaseTime = 0.0f;
        PlayMusic(Music::ENDING);
        return;
    }
}

void GameScene::StartItemGet(const std::string &item)
{
    const ItemDef *def = FindItem(item);
    phase = Phase::ITEM_GET;
    phaseTime = 0.0f;
    currentItem = item;
    world.player.state = PState::HOLD;
    world.player.dir = Dir::DOWN;
    world.player.charging = false;
    world.player.holdItem = def ? def->sprite : "gem_r_0";
    ApplyItem(world, item);
    PlaySfx(Sfx::ITEM);
}

void GameScene::StartWarp(const std::string &map, const std::string &spawn)
{
    warpMap = map;
    warpSpawn = spawn;
    phase = Phase::FADE_OUT;
    phaseTime = 0.0f;
    PlaySfx(Sfx::DOOR, 0.5f);
}

void GameScene::HandleRequest()
{
    Request request = world.request;
    world.request = Request{};
    switch (request.type)
    {
    case RequestType::DIALOG:
        pendingItem = request.afterItem;
        OpenDialog(request.pages);
        break;
    case RequestType::ITEM:
        StartItemGet(request.item);
        break;
    case RequestType::WARP:
        StartWarp(request.map, request.spawn);
        break;
    case RequestType::SHRINK:
        warpMap = request.map;
        warpSpawn = request.spawn;
        pendingShrink = true;
        if (!request.pages.empty())
        {
            OpenDialog(request.pages);
        }
        else
        {
            FinishDialog();
        }
        break;
    case RequestType::GROW:
        warpMap = request.map;
        warpSpawn = request.spawn;
        phase = Phase::GROW;
        phaseTime = 0.0f;
        world.player.state = PState::GROW;
        PlaySfx(Sfx::GROW);
        PlayMusic(Music::NONE);
        break;
    case RequestType::GAME_OVER:
        phase = Phase::GAME_OVER;
        phaseTime = 0.0f;
        break;
    case RequestType::NONE:
    default:
        break;
    }
}

void GameScene::HandleShots()
{
    for (auto it = pendingShots.begin(); it != pendingShots.end();)
    {
        if (it->second.wait_for(std::chrono::seconds(0)) != std::future_status::ready)
        {
            ++it;
            continue;
        }
        resource::RawTexture shot = it->second.get();
        stbi_flip_vertically_on_write(1);
        stbi_write_png(it->first.c_str(), shot.width, shot.height, shot.nrOfChannels,
                       shot.pixels.data(), shot.width * shot.nrOfChannels);
        LOGINFO("Saved %s", it->first.c_str());
        it = pendingShots.erase(it);
    }
    if (!shotTicks.empty())
    {
        if (shotTicks.front() >= 0 && totalTicks >= shotTicks.front())
        {
            const char *prefix = std::getenv("SMALLCAP_SHOT_PREFIX");
            const std::string path =
                std::string(prefix ? prefix : "shot") + "_" + std::to_string(shotTicks.front()) + ".png";
            pendingShots.emplace_back(path, graphics::Renderer::GetInstance()->RequestScreenshot());
            shotTicks.erase(shotTicks.begin());
            if (shotTicks.empty())
            {
                shotTicks.push_back(-1);
            }
        }
    }
    if (shotTicks.size() == 1 && shotTicks.front() == -1 && pendingShots.empty())
    {
        core::Application::GetInstance()->Quit();
    }
}

void GameScene::Tick()
{
    totalTicks++;
    phaseTime += TICK;
    switch (phase)
    {
    case Phase::TITLE:
    {
        world.time += TICK;
        world.tickCount++;
        // Slow pan across the village behind the title.
        const Float pan = (std::sin(phaseTime * 0.12f) * 0.5f + 0.5f);
        world.cameraX = pan * std::max(0.0f, world.map.PixelWidth() - SCREEN_W);
        world.cameraY = 96.0f;
        brightness = std::min(1.0f, phaseTime * 2.0f);
        if (phaseTime > 0.5f && (controls.start.pressed || controls.sword.pressed || controls.action.pressed))
        {
            PlaySfx(Sfx::MENU);
            NewGame();
        }
        break;
    }
    case Phase::PLAY:
    {
        brightness = 1.0f;
        playTime += TICK;
        if (controls.start.pressed && world.player.state != PState::DEAD)
        {
            phase = Phase::PAUSE;
            phaseTime = 0.0f;
            PlaySfx(Sfx::MENU);
            break;
        }
        UpdateWorld(world, controls);
        UpdateMusic();
        if (world.request.type != RequestType::NONE)
        {
            HandleRequest();
        }
        break;
    }
    case Phase::DIALOG:
    {
        const Float before = typed;
        typed = std::min(static_cast<Float>(pages[page].size()), typed + TYPE_SPEED * TICK);
        if (static_cast<Int32>(before) / 3 != static_cast<Int32>(typed) / 3 &&
            typed < static_cast<Float>(pages[page].size()))
        {
            PlaySfx(Sfx::TEXT, 0.35f);
        }
        if (phaseTime > 0.15f && (controls.action.pressed || controls.sword.pressed || controls.start.pressed))
        {
            AdvanceDialog();
        }
        break;
    }
    case Phase::ITEM_GET:
    {
        world.time += TICK;
        if (phaseTime >= 1.1f)
        {
            const ItemDef *def = FindItem(currentItem);
            if (currentItem == "sunstone")
            {
                pendingEnding = true;
            }
            const std::vector<std::string> item_pages =
                SplitPages(def ? def->text : "You found something!");
            // Keep the hold pose while the text is up.
            OpenDialog(item_pages);
        }
        break;
    }
    case Phase::FADE_OUT:
    {
        brightness = std::max(0.0f, 1.0f - phaseTime / FADE_TIME);
        if (phaseTime >= FADE_TIME)
        {
            EnterMap(world, warpMap, warpSpawn, *renderer);
            UpdateMusic();
            phase = Phase::FADE_IN;
            phaseTime = 0.0f;
        }
        break;
    }
    case Phase::FADE_IN:
    {
        brightness = std::min(1.0f, phaseTime / FADE_TIME);
        if (phaseTime >= FADE_TIME)
        {
            phase = Phase::PLAY;
            phaseTime = 0.0f;
            brightness = 1.0f;
            if (world.request.type != RequestType::NONE)
            {
                HandleRequest();
            }
        }
        break;
    }
    case Phase::SHRINK:
    {
        world.time += TICK;
        world.tickCount++;
        Player &p = world.player;
        p.scale = std::max(0.12f, 1.0f - phaseTime / 1.3f * 0.88f);
        if (world.tickCount % 5 == 0)
        {
            const Float a = phaseTime * 9.0f;
            SpawnEffect(world, "sparkle", p.x + std::cos(a) * 12.0f, p.y - 8.0f + std::sin(a) * 10.0f, 0.3f);
        }
        UpdateWorld(world, Controls{});
        if (phaseTime >= 1.7f)
        {
            StartWarp(warpMap, warpSpawn);
        }
        break;
    }
    case Phase::GROW:
    {
        world.time += TICK;
        Player &p = world.player;
        p.scale = 1.0f + std::min(1.0f, phaseTime / 1.2f) * 1.6f;
        if (world.tickCount % 5 == 0)
        {
            const Float a = phaseTime * 9.0f;
            SpawnEffect(world, "sparkle", p.x + std::cos(a) * 16.0f, p.y - 12.0f + std::sin(a) * 12.0f, 0.3f);
        }
        UpdateWorld(world, Controls{});
        if (phaseTime >= 1.5f)
        {
            StartWarp(warpMap, warpSpawn);
        }
        break;
    }
    case Phase::GAME_OVER:
    {
        brightness = std::max(0.35f, 1.0f - phaseTime);
        if (phaseTime > 1.2f && (controls.start.pressed || controls.sword.pressed || controls.action.pressed))
        {
            PlaySfx(Sfx::MENU);
            world.player.hp = std::min(world.player.maxHp, 6);
            world.player.iframes = 0.0f;
            world.player.state = PState::NORMAL;
            world.map.name.clear();
            warpMap = world.spawnMap;
            warpSpawn = world.spawnName;
            EnterMap(world, warpMap, warpSpawn, *renderer);
            UpdateMusic();
            phase = Phase::FADE_IN;
            phaseTime = 0.0f;
        }
        break;
    }
    case Phase::PAUSE:
    {
        if (controls.start.pressed && phaseTime > 0.1f)
        {
            phase = Phase::PLAY;
            phaseTime = 0.0f;
            PlaySfx(Sfx::MENU);
        }
        break;
    }
    case Phase::ENDING:
    {
        brightness = 1.0f;
        world.time += TICK;
        world.tickCount++;
        if (phaseTime > 8.0f && (controls.start.pressed || controls.action.pressed || controls.sword.pressed))
        {
            phase = Phase::TITLE;
            phaseTime = 0.0f;
            world.flags.clear();
            world.map.name.clear();
            EnterMap(world, "village", "start", *renderer);
            PlayMusic(Music::TITLE);
        }
        break;
    }
    }
}

void GameScene::Render()
{
    if (!shotTicks.empty() || !pendingShots.empty())
    {
        HandleShots();
    }
    renderer->BeginFrame(phase == Phase::ENDING ? 1.0f : brightness);
    if (phase == Phase::ENDING)
    {
        RenderEnding();
    }
    else
    {
        RenderWorld(world, *renderer);
    }
    UpdateUi();
}

void GameScene::UpdateUi()
{
    if (!ui)
    {
        return;
    }
    UiState &state = ui->State();
    state.screen = phase == Phase::TITLE ? "title" : (phase == Phase::ENDING ? "ending" : "play");
    state.blink = static_cast<Int32>(phaseTime * 2.0f) % 2 == 0;
    state.bob = static_cast<Int32>(std::lround(std::sin(phaseTime * 2.0f) * 2.0f));

    // HUD
    const Player &p = world.player;
    state.hearts.clear();
    for (Int32 i = 0; i < p.maxHp / 2; ++i)
    {
        const Int32 value = p.hp - i * 2;
        state.hearts.emplace_back(
            value >= 2 ? "hud-heart-full" : (value == 1 ? "hud-heart-half" : "hud-heart-empty")
        );
    }
    char buffer[64];
    std::snprintf(buffer, sizeof(buffer), "%03d", world.gems);
    state.gems = buffer;
    state.dungeon = world.map.rooms;
    state.keys = world.keys;
    state.bigKey = world.bigKey;
    state.prompt = world.prompt.empty() ? std::string() : "X " + ToUiText(world.prompt);

    // Dialog: typed out character by character; a leading "Name:" is the speaker, in gold.
    state.dialog = phase == Phase::DIALOG;
    state.speaker.clear();
    state.text.clear();
    state.more = false;
    if (state.dialog)
    {
        state.dialogTop = world.player.y - world.cameraY > 100.0f;
        const std::string &text = pages[page];
        const size_t shown = std::min(static_cast<size_t>(typed), text.size());
        std::string visible = text.substr(0, shown);
        const size_t colon = text.find(':');
        const size_t first_break = text.find('\n');
        if (colon != std::string::npos && colon < 12 && colon < first_break &&
            text.substr(0, colon).find(' ') == std::string::npos)
        {
            const size_t speaker_length = std::min(colon + 1, visible.size());
            state.speaker = visible.substr(0, speaker_length);
            visible = visible.substr(speaker_length);
        }
        state.text = ToUiText(visible);
        state.more = shown >= text.size();
        state.arrowFrame = static_cast<Int32>((world.tickCount / 15) % 2);
    }

    state.paused = phase == Phase::PAUSE;
    state.controlsText = "Move     Arrows/WASD\nSword    Z / J\nSpin     hold Z\n"
                         "Action   X / K\nRoll     C / Shift";
    const auto seconds = static_cast<Int32>(playTime);
    std::snprintf(buffer, sizeof(buffer), "Time %d:%02d", seconds / 60, seconds % 60);
    state.time = buffer;

    state.gameOver = phase == Phase::GAME_OVER;
    state.retry = phaseTime > 1.2f;

    // Ending: the lines appear one by one, then the stats.
    state.endingLines = 0;
    state.stats.clear();
    if (phase == Phase::ENDING)
    {
        for (Int32 i = 0; i < 6; ++i)
        {
            if (phaseTime > 0.8f + static_cast<Float>(i) * 0.7f)
            {
                state.endingLines = i + 1;
            }
        }
        if (phaseTime > 6.0f)
        {
            std::snprintf(buffer, sizeof(buffer), "Time %d:%02d   Gems %d", seconds / 60,
                          seconds % 60, world.gems);
            state.stats = buffer;
        }
    }
    ui->Commit();
}

void GameScene::RenderEnding()
{
    Renderer2D &r = *renderer;
    r.FillRect(0.0f, 0.0f, SCREEN_W, SCREEN_H, {0.07f, 0.06f, 0.16f, 1.0f});
    DrawOptions o;
    o.screen = true;
    const Float t = phaseTime;
    for (Int32 i = 0; i < 14; ++i)
    {
        const Float a = t * 0.4f + static_cast<Float>(i) * 0.449f;
        r.Draw("sparkle_" + std::to_string((world.tickCount / 6 + i) % 3),
               120.0f + std::cos(a) * (60.0f + 10.0f * std::sin(t + i)),
               62.0f + std::sin(a) * 34.0f, o);
    }
    r.Draw("sunstone_" + std::to_string((world.tickCount / 12) % 2), 120.0f, 64.0f, o);
    r.Draw("capo_small", 106.0f, 84.0f + std::sin(t * 3.0f) * 1.5f, o);
    r.Draw("hero_down_0", 126.0f, 86.0f, o);
}
} // namespace smallcap
