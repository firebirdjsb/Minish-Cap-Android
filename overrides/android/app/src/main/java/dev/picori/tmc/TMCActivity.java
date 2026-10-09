package dev.picori.tmc;

import android.content.pm.ActivityInfo;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

import org.libsdl.app.SDLActivity;

/**
 * Minish Cap Android — phone-first Project Picori shell.
 *
 * The game, renderer, audio, menu and touch controls all live in libmain.so.
 * This Activity owns Android presentation policy. Prelaunch permits the
 * normal sensor-landscape policy; Play fixes orientation to landscape for
 * the entire gameplay session, even when the device rotates or resumes.
 */
public class TMCActivity extends SDLActivity {
    private static final String KEY_GAME_STARTED = "gameStarted";
    private volatile boolean gameStarted;

    private void enforceOrientation() {
        final int orientation = gameStarted
                ? ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                : ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
        if (getRequestedOrientation() != orientation) {
            setRequestedOrientation(orientation);
        }
    }

    /**
     * Called via JNI by native port_main immediately after Play succeeds.
     * Orientation is owned by the activity UI thread, not the SDL game
     * thread. Never unlock gameplay when opening menus or pausing.
     */
    public void lockGameplayLandscape() {
        gameStarted = true;
        runOnUiThread(() -> {
            enforceOrientation();
            configurePhoneWindow();
        });
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        outState.putBoolean(KEY_GAME_STARTED, gameStarted);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        gameStarted = savedInstanceState != null &&
                savedInstanceState.getBoolean(KEY_GAME_STARTED, false);
        enforceOrientation();
        super.onCreate(savedInstanceState);
        configurePhoneWindow();
    }

    @Override
    protected void onResume() {
        super.onResume();
        enforceOrientation();
        configurePhoneWindow();
    }

    @Override
    protected String[] getLibraries() {
        return new String[] { "main" };
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enforceOrientation();
            configurePhoneWindow();
        }
    }

    /**
     * The game uses a single SDL surface. Touch controls are drawn over the
     * gameplay surface; there is no separate controller pane / second screen.
     */
    private void configurePhoneWindow() {
        final Window window = getWindow();
        if (window == null) {
            return;
        }

        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        final WindowManager.LayoutParams lp = window.getAttributes();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            lp.layoutInDisplayCutoutMode =
                    WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            window.setAttributes(lp);
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false);
            final WindowInsetsController controller = window.getInsetsController();
            if (controller != null) {
                controller.hide(
                        WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            window.getDecorView().setSystemUiVisibility(
                    View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                            | View.SYSTEM_UI_FLAG_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                            | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                            | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        }
    }
}
