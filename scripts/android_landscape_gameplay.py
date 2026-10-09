#!/usr/bin/env python3
"""Call the Android Activity's fixed-landscape policy at the actual Play edge.

SDL3's JNI accessors are used only for Android. The Activity posts the
orientation change onto its UI thread; the native game and SDL renderer retain
ownership of window/surface events. Gameplay remains locked through resume.
"""
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "upstream" / "tmc" / "port" / "port_main.c"
s = path.read_text(encoding="utf-8")

def replace_exact(old, new):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"Android landscape Play hook: expected one anchor, got {count}: {old[:90]!r}")
    s = s.replace(old, new, 1)

replace_exact(
    """#include <SDL3/SDL_main.h>
#include <unistd.h>
#endif

int main(int argc, char* argv[]) {""",
    """#include <SDL3/SDL_main.h>
#include <SDL3/SDL_system.h>
#include <jni.h>
#include <unistd.h>

/* This is called only after Play/autoplay leaves the prelaunch screen.
 * SDL3 returns the Activity as a JNI local ref; always delete it.
 * Android orientation APIs run on the UI thread in TMCActivity. */
static void Port_AndroidLockOrientationForGameplay(void) {
    JNIEnv* env = (JNIEnv*)SDL_GetAndroidJNIEnv();
    if (!env)
        return;
    jobject activity = (jobject)SDL_GetAndroidActivity();
    if (!activity)
        return;
    jclass cls = (*env)->GetObjectClass(env, activity);
    if (cls) {
        jmethodID lock = (*env)->GetMethodID(env, cls, "lockGameplayLandscape", "()V");
        if (lock) {
            (*env)->CallVoidMethod(env, activity, lock);
        }
        (*env)->DeleteLocalRef(env, cls);
    }
    if ((*env)->ExceptionCheck(env)) {
        (*env)->ExceptionDescribe(env);
        (*env)->ExceptionClear(env);
        fprintf(stderr, "[android] Unable to apply gameplay landscape orientation\\n");
    }
    (*env)->DeleteLocalRef(env, activity);
}
#endif

int main(int argc, char* argv[]) {"""
)
replace_exact(
    """        fprintf(stderr, "Prelaunch: Play — loading ROM and assets.\\n");
    }

    /* Play pressed and romPath is set. Select the active mod set before""",
    """        fprintf(stderr, "Prelaunch: Play — loading ROM and assets.\\n");
    }

#ifdef __ANDROID__
    /* Lock the actual Android Activity immediately when Play begins.
     * No sensor-driven portrait/auto-rotate during gameplay, pause or resume. */
    Port_AndroidLockOrientationForGameplay();
#endif

    /* Play pressed and romPath is set. Select the active mod set before"""
)
path.write_text(s, encoding="utf-8")
print("Android Play transition now requests fixed landscape on the Activity UI thread")
