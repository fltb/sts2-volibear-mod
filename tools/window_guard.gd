extends SceneTree
var next_sample_ms := 0
var low_fps_samples := 0

func _process(_delta):
	if invalid_window_state():
		push_error("WINDOW_GUARD_ERROR windowed/non-topmost contract lost")
		quit(3)
		return false
	var now := Time.get_ticks_msec()
	if now >= next_sample_ms:
		next_sample_ms = now + 10000
		if not verify_window_manager("runtime"):
			return false
		print("WINDOW_RUNTIME_TIMING ticksMs=", now, " fps=", Engine.get_frames_per_second(), " max_fps=", Engine.max_fps, " low_processor=", OS.low_processor_usage_mode, " low_sleep_usec=", OS.low_processor_usage_mode_sleep_usec, " vsync=", DisplayServer.window_get_vsync_mode())
		# Ignore startup; fail boundedly instead of spending hours at 1 FPS.
		if now >= 30000:
			if Engine.get_frames_per_second() < 10:
				low_fps_samples += 1
			else:
				low_fps_samples = 0
			if low_fps_samples >= 3:
				push_error("WINDOW_PERFORMANCE_FAILED sustained FPS below 10; inspect VSync/render waits")
				quit(3)
	return false

func _initialize():
	# Ordinary managed window: title bar, movement and normal user input.
	# Do not activate/raise it or use NO_FOCUS, which creates an unmanaged UTILITY.
	DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH, false)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	print("WINDOW_GUARD_READY configured_no_focus=", ProjectSettings.get_setting("display/window/size/no_focus", false), " no_focus=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS), " mouse_passthrough=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH))
	print("WINDOW_MODE_READY mode=", DisplayServer.window_get_mode(), " always_on_top=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP), " size=", DisplayServer.window_get_size(), " xid=", DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE))
	call_deferred("launch_original")

func launch_original():
	if not verify_window_manager("startup"):
		return
	var scene = ProjectSettings.get_setting("application/run/main_scene", "")
	if scene == "" or change_scene_to_file(scene) != OK:
		push_error("WINDOW_GUARD_ERROR original scene unavailable")
		quit(2)

func invalid_window_state() -> bool:
	var mode := DisplayServer.window_get_mode()
	var top := DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP)
	if mode != DisplayServer.WINDOW_MODE_FULLSCREEN and mode != DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN and not top:
		return false
	print("WINDOW_MODE_VIOLATION mode=", mode, " always_on_top=", top, " size=", DisplayServer.window_get_size())
	verify_window_manager("mode_violation")
	return true

# Read actual X11 state; Godot's mode alone cannot detect an unmanaged UTILITY window.
func verify_window_manager(stage: String) -> bool:
	var properties: Array = []
	var status := OS.execute("xprop", ["-id", str(DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE)), "_NET_WM_STATE", "_NET_WM_WINDOW_TYPE", "_NET_FRAME_EXTENTS", "_NET_WM_ALLOWED_ACTIONS", "_NET_WM_USER_TIME"], properties, true)
	var observed := " | ".join(properties).replace("\n", " | ")
	print("WINDOW_MANAGER_STATE stage=", stage, " ", observed)
	if stage == "startup" and not "_NET_WM_USER_TIME(CARDINAL) = 0 |" in observed:
		push_error("WINDOW_GUARD_ERROR missing pre-map non-activation hint")
		quit(3)
		return false
	if status != 0 or not "_NET_WM_WINDOW_TYPE_NORMAL" in observed or "_NET_WM_WINDOW_TYPE_UTILITY" in observed or "_NET_WM_STATE_ABOVE" in observed or "_NET_WM_STATE_FULLSCREEN" in observed:
		print("WINDOW_MODE_VIOLATION mode=", DisplayServer.window_get_mode(), " always_on_top=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP), " size=", DisplayServer.window_get_size())
		push_error("WINDOW_GUARD_ERROR window manager state is not a normal non-topmost window")
		quit(3)
		return false
	var active: Array = []
	var active_status := OS.execute("xprop", ["-root", "_NET_ACTIVE_WINDOW"], active, true)
	print("WINDOW_ACTIVE_OBSERVED stage=", stage, " status=", active_status, " ", " | ".join(active).replace("\n", " | "))
	print("WINDOW_MANAGER_VERIFIED mode=", DisplayServer.window_get_mode(), " size=", DisplayServer.window_get_size(), " always_on_top=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP))
	return true
