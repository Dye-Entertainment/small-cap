#include "small_cap.h"

#include "audio/sound.h"
#include "core/scene_manager.h"
#include "game/game_scene.h"
#include "utils/logger.h"

Bool SmallCap::DerrivedInitialize()
{
    if (!renderer.Initialize())
    {
        LOGERROR("Small Cap could not load its graphics");
        return false;
    }
    if (!ui.Initialize())
    {
        LOGERROR("Small Cap could not load its UI");
        return false;
    }
    smallcap::InitializeAudio();
    core::SceneManager::GetInstance()->AddScene("Small Cap", new smallcap::GameScene(&renderer, &ui));
    return true;
}

Bool SmallCap::UpdateLoop(const Double)
{
    return true;
}

void SmallCap::Destroy()
{
    smallcap::ShutdownAudio();
    ui.Shutdown();
    renderer.Shutdown();
    GameApplication::Destroy();
}
