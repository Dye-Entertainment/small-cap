#pragma once
#include "core/scene.h"
#include "game/world.h"
#include "input/controls.h"
#include "render/renderer2d.h"
#include "ui/game_ui.h"
#include "resource/raw_texture.h"

#include "compiled/warning_off.h"
#include <future>
#include <string>
#include <vector>
#include "compiled/warning_on.h"

namespace smallcap
{
enum class Phase : UInt8
{
    TITLE,
    PLAY,
    DIALOG,
    ITEM_GET,
    FADE_OUT,
    FADE_IN,
    SHRINK,
    GROW,
    GAME_OVER,
    PAUSE,
    ENDING
};

class GameScene final : public core::Scene
{
  public:
    GameScene(Renderer2D *renderer, GameUi *ui);
    void Update(const double elapsed_seconds) override;
    void Render() override;

  private:
    void Tick();
    void NewGame();
    void HandleRequest();
    void OpenDialog(const std::vector<std::string> &pages);
    void AdvanceDialog();
    void FinishDialog();
    void StartItemGet(const std::string &item);
    void StartWarp(const std::string &map, const std::string &spawn);
    void UpdateMusic();
    // Fills in the UI document's state from the game.
    void UpdateUi();
    // The ending's sparkles and characters; its text is in the UI document.
    void RenderEnding();

    Renderer2D *renderer = nullptr;
    GameUi *ui = nullptr;
    World world;
    Controls controls;
    Phase phase = Phase::TITLE;
    Double accumulator = 0.0;
    Float phaseTime = 0.0f;
    Float brightness = 1.0f;
    Float playTime = 0.0f;

    // Dialog state.
    std::vector<std::string> pages;
    size_t page = 0;
    Float typed = 0.0f;
    std::vector<std::string> lines;

    // What happens once the current dialog closes.
    std::string pendingItem;
    Bool pendingShrink = false;
    Bool pendingGrow = false;
    Bool pendingEnding = false;
    std::string warpMap;
    std::string warpSpawn;
    std::string currentItem;

    // Test hook: SMALLCAP_INPUT="right:60 sword:1 wait:30" drives the controls.
    struct ScriptStep
    {
        std::string buttons;
        Int32 frames = 0;
    };
    std::vector<ScriptStep> script;
    size_t scriptIndex = 0;
    Int32 scriptFrame = 0;
    void ApplyScript();

    // Test hook: SMALLCAP_SHOTS="120,300" saves screenshots at those ticks, then quits.
    std::vector<Int32> shotTicks;
    std::vector<std::pair<std::string, std::future<resource::RawTexture>>> pendingShots;
    Int32 totalTicks = 0;
    void HandleShots();
};
} // namespace smallcap
