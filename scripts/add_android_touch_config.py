#!/usr/bin/env python3
from pathlib import Path

cfg = Path("upstream/tmc/port/port_runtime_config.cpp")
src = cfg.read_text(encoding="utf-8")

# S24-class Android devices have ample headroom for the GBA display LUT.
# Keep Android aligned with desktop: colour correction is ON by default.
src = src.replace(
"""#ifdef __ANDROID__
bool sColorCorrect = false; /* Too heavy for low-end ARM by default */
#else
bool sColorCorrect = true; /* GBA-LCD colour correction (default on) */
#endif
""",
"""bool sColorCorrect = true; /* GBA-LCD colour correction (default on) */
""", 1)

src = src.replace(
"""#ifdef __ANDROID__
    { "color_correction", &sColorCorrect, false },
#else
    { "color_correction", &sColorCorrect, true },
#endif
""",
"""    { "color_correction", &sColorCorrect, true },
""", 1)

src = src.replace(
"""PortTouchScheme sTouchScheme = PORT_TOUCH_SCHEME_JOYSTICK;
float sTouchScale = 1.0f;   /* multiplies the touch layout unit  */
float sTouchOpacity = 1.0f; /* multiplies every control's alpha  */
""",
"""#ifdef __ANDROID__
PortTouchScheme sTouchScheme = PORT_TOUCH_SCHEME_DPAD;
bool sTouchEnabled = true;
#else
PortTouchScheme sTouchScheme = PORT_TOUCH_SCHEME_JOYSTICK;
bool sTouchEnabled = true;
#endif
float sTouchScale = 1.0f;   /* multiplies the touch layout unit  */
float sTouchOpacity = 1.0f; /* phone default: clear, high-contrast controls */
""", 1)

src = src.replace(
"""    j["touch_scheme"] = "joystick";
""",
"""#ifdef __ANDROID__
    j["touch_scheme"] = "dpad";
    j["touch_enabled"] = true;
    j["android_touch_layout_version"] = 1;
#else
    j["touch_scheme"] = "joystick";
    j["touch_enabled"] = true;
#endif
""", 1)

src = src.replace(
"""            sTouchScheme = (ts == "dpad") ? PORT_TOUCH_SCHEME_DPAD : PORT_TOUCH_SCHEME_JOYSTICK;
        }
        sTouchScale = std::min(1.6f, std::max(0.6f, JsonValue(j, "touch_scale", 1.0f)));
        sTouchOpacity = std::min(1.5f, std::max(0.3f, JsonValue(j, "touch_opacity", 1.0f)));
""",
"""            sTouchScheme = (ts == "dpad") ? PORT_TOUCH_SCHEME_DPAD : PORT_TOUCH_SCHEME_JOYSTICK;
        }
        sTouchEnabled = JsonValue(j, "touch_enabled", true);
        sTouchScale = std::min(1.6f, std::max(0.6f, JsonValue(j, "touch_scale", 1.0f)));
        sTouchOpacity = std::min(1.5f, std::max(0.3f, JsonValue(j, "touch_opacity", 1.0f)));
""", 1)

anchor = """extern "C" PortTouchScheme Port_Config_TouchScheme(void) {
    return sTouchScheme;
}

"""
if anchor not in src:
    raise SystemExit("touch scheme accessor anchor not found")
src = src.replace(anchor, anchor + """extern "C" bool Port_Config_TouchEnabled(void) {
    return sTouchEnabled;
}

extern "C" void Port_Config_SetTouchEnabled(bool enabled) {
    sTouchEnabled = enabled;
    sConfigJson["touch_enabled"] = enabled;
    SaveConfig();
}

""", 1)

migration_anchor = """    try {
        apply(j);
    } catch (const std::exception& e) {
        fprintf(stderr, "[CONFIG] Malformed config.json (%s); falling back to defaults.\\n", e.what());
        const nlohmann::json def = DefaultsJson();
        sConfigJson = def;
        apply(def); /* defaults are well-typed and cannot throw */
    }
}
"""

migration_new = """    try {
        apply(j);
    } catch (const std::exception& e) {
        fprintf(stderr, "[CONFIG] Malformed config.json (%s); falling back to defaults.\\n", e.what());
        const nlohmann::json def = DefaultsJson();
        sConfigJson = def;
        apply(def); /* defaults are well-typed and cannot throw */
    }

#ifdef __ANDROID__
    /*
     * One-time migration for installs created before the phone-native GBA
     * layout existed. Old configs saved the floating joystick as the default,
     * so merely changing DefaultsJson would never affect an existing phone.
     * Migrate once, persist the marker, then always respect the user's choice.
     */
    if (!sConfigJson.contains("android_touch_layout_version")) {
        sTouchScheme = PORT_TOUCH_SCHEME_DPAD;
        sTouchEnabled = true;
        sConfigJson["touch_scheme"] = "dpad";
        sConfigJson["touch_enabled"] = true;
        sConfigJson["android_touch_layout_version"] = 1;
        SaveConfig();
    }

    /* Existing Android installs inherited the old low-end-ARM default of
     * colour correction OFF. Migrate that default once, then respect the
     * user's choice forever after. */
    if (!sConfigJson.contains("android_color_correction_default_version")) {
        sColorCorrect = true;
        sConfigJson["color_correction"] = true;
        sConfigJson["android_color_correction_default_version"] = 1;
        SaveConfig();
    }

    if (!sConfigJson.contains("android_touch_visibility_version")) {
        if (sTouchOpacity < 1.0f)
            sTouchOpacity = 1.0f;
        sConfigJson["touch_opacity"] = sTouchOpacity;
        sConfigJson["android_touch_visibility_version"] = 1;
        SaveConfig();
    }
#endif
}
"""

if migration_anchor not in src:
    raise SystemExit("config load tail anchor not found")
src = src.replace(migration_anchor, migration_new, 1)

cfg.write_text(src, encoding="utf-8")

hdr = Path("upstream/tmc/port/port_runtime_config.h")
h = hdr.read_text(encoding="utf-8")
anchor_h = """PortTouchScheme Port_Config_TouchScheme(void);
void Port_Config_SetTouchScheme(PortTouchScheme scheme);
void Port_Config_CycleTouchScheme(int direction);
"""
if anchor_h not in h:
    raise SystemExit("touch header anchor not found")
h = h.replace(anchor_h, """PortTouchScheme Port_Config_TouchScheme(void);
void Port_Config_SetTouchScheme(PortTouchScheme scheme);
void Port_Config_CycleTouchScheme(int direction);
bool Port_Config_TouchEnabled(void);
void Port_Config_SetTouchEnabled(bool enabled);
""", 1)
hdr.write_text(h, encoding="utf-8")

print("Added persisted touch enable flag and GBA D-pad phone defaults")
