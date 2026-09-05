from app.core.config import Settings


def test_openrouter_defaults_use_current_free_models_with_paid_vision_last():
    settings = Settings(_env_file=None)

    assert settings.OPENROUTER_TEXT_MODEL == "z-ai/glm-5.2:free"
    assert settings.OPENROUTER_TEXT_FALLBACKS == (
        "nvidia/nemotron-3-super-120b-a12b:free,openrouter/free"
    )
    assert settings.OPENROUTER_VISION_MODEL == "google/gemma-4-31b-it:free"
    assert settings.OPENROUTER_VISION_FALLBACKS == (
        "dots-studio/dots-3-note-preview:free,google/gemini-2.5-flash"
    )
