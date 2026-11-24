#include "ui/game_ui.h"

#include "ui/ui_manager.h"
#include "utils/logger.h"
#include "window/window_manager.h"

#include "compiled/warning_off.h"
#include <RmlUi/Core.h>
#include "compiled/warning_on.h"

namespace smallcap
{
namespace
{
const std::string UI_DIR = std::string(RESOURCE_UI_DIR) + "/";

Rml::DataModelHandle model;
} // namespace

std::string ToUiText(const std::string &text)
{
    std::string out;
    out.reserve(text.size());
    for (const char c : text)
    {
        if (c == '\x01')
        {
            out += "\xE2\x99\xA5"; // U+2665
        }
        else
        {
            out += c;
        }
    }
    return out;
}

Bool GameUi::Initialize()
{
    auto *manager = ui::Manager::GetInstance();
    if (!manager || !manager->GetContext())
    {
        LOGERROR("Small Cap needs the engine UI");
        return false;
    }
    if (!manager->LoadFontFace(UI_DIR + "pixel.ttf", true))
    {
        return false;
    }
    manager->SetPixelatedImages(true);

    Rml::DataModelConstructor constructor = manager->GetContext()->CreateDataModel("game");
    if (!constructor)
    {
        return false;
    }
    constructor.RegisterArray<std::vector<std::string>>();
    constructor.Bind("screen", &state.screen);
    constructor.Bind("blink", &state.blink);
    constructor.Bind("bob", &state.bob);
    constructor.Bind("startText", &state.startText);
    constructor.Bind("helpLine1", &state.helpLine1);
    constructor.Bind("helpLine2", &state.helpLine2);
    constructor.Bind("hearts", &state.hearts);
    constructor.Bind("gems", &state.gems);
    constructor.Bind("dungeon", &state.dungeon);
    constructor.Bind("keys", &state.keys);
    constructor.Bind("bigKey", &state.bigKey);
    constructor.Bind("prompt", &state.prompt);
    constructor.Bind("dialog", &state.dialog);
    constructor.Bind("dialogTop", &state.dialogTop);
    constructor.Bind("speaker", &state.speaker);
    constructor.Bind("text", &state.text);
    constructor.Bind("more", &state.more);
    constructor.Bind("arrowFrame", &state.arrowFrame);
    constructor.Bind("paused", &state.paused);
    constructor.Bind("controlsText", &state.controlsText);
    constructor.Bind("time", &state.time);
    constructor.Bind("gameOver", &state.gameOver);
    constructor.Bind("retry", &state.retry);
    constructor.Bind("retryText", &state.retryText);
    constructor.Bind("endingLines", &state.endingLines);
    constructor.Bind("stats", &state.stats);
    model = constructor.GetModelHandle();

    document = manager->LoadDocument(UI_DIR + "game.rml");
    if (!document)
    {
        return false;
    }
    document->Show();
    ready = true;
    Commit();
    return true;
}

void GameUi::Shutdown()
{
    if (document)
    {
        document->Close();
        document = nullptr;
    }
    model = {};
    ready = false;
}

void GameUi::Commit()
{
    if (!ready)
    {
        return;
    }
    // The UI is laid out on the 240x160 game screen, which the window shows scaled up.
    const IVec2 size = window::Manager::GetInstance()->GetWindowSize(0);
    if (size.y > 0)
    {
        ui::Manager::GetInstance()->SetDensityIndependentPixelRatio(
            static_cast<Float>(size.y) / 160.0f
        );
    }
    model.DirtyAllVariables();
}
} // namespace smallcap
