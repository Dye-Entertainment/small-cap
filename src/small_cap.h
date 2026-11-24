#pragma once
#include "ecs/core/game_application.h"
#include "render/renderer2d.h"
#include "ui/game_ui.h"

class SmallCap final : public GameApplication
{
  public:
    Bool DerrivedInitialize() override;
    Bool UpdateLoop(const Double elapsed_seconds) override;
    void Destroy() override;

  private:
    smallcap::Renderer2D renderer;
    smallcap::GameUi ui;
};
