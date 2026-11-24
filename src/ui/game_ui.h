#pragma once
#include "platform/types.h"

#include "compiled/warning_off.h"
#include <string>
#include <vector>
#include "compiled/warning_on.h"

namespace Rml
{
class ElementDocument;
}

namespace smallcap
{
// Everything the UI document (resources/ui/game.rml) shows. The game scene fills it in every
// frame; the document reads it through an RmlUi data model.
struct UiState
{
    std::string screen = "title"; // title, play or ending

    // Title
    Bool blink = true;
    Int32 bob = 0;
    std::string startText = "Press Enter";
    std::string helpLine1 = "Arrows move  Z sword  X action";
    std::string helpLine2 = "C roll  Enter pause";

    // HUD
    std::vector<std::string> hearts;
    std::string gems = "000";
    Bool dungeon = false;
    Int32 keys = 0;
    Bool bigKey = false;
    std::string prompt;

    // Dialog
    Bool dialog = false;
    Bool dialogTop = false;
    std::string speaker;
    std::string text;
    Bool more = false;
    Int32 arrowFrame = 0;

    // Pause and game over
    Bool paused = false;
    std::string controlsText;
    std::string time;
    Bool gameOver = false;
    Bool retry = false;
    std::string retryText = "Press Enter to try again";

    // Ending
    Int32 endingLines = 0;
    std::string stats;
};

class GameUi final
{
  public:
    // Loads the font, the sprite sheet and the document. Needs the engine's UI manager.
    Bool Initialize();
    void Shutdown();

    UiState &State()
    {
        return state;
    }
    // Sends the state to the document; call once per frame after filling it in.
    void Commit();

  private:
    UiState state;
    Rml::ElementDocument *document = nullptr;
    Bool ready = false;
};

// The bitmap font keeps a heart under \x01; the UI font has it at U+2665.
std::string ToUiText(const std::string &text);
} // namespace smallcap
