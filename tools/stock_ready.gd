extends SceneTree
var started := Time.get_ticks_msec()
var ready_frames := 0
var exiting := false
var next_sample_ms := 30000
var low_fps_samples := 0

func _initialize():
	if OS.get_environment("VOLIBEAR_TEST_WINDOW_GUARD") == "1":
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS, false)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH, false)
		DisplayServer.window_set_size(Vector2i(1280, 720))
		print("WINDOW_MODE_READY mode=", DisplayServer.window_get_mode(), " always_on_top=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP), " size=", DisplayServer.window_get_size(), " xid=", DisplayServer.window_get_native_handle(DisplayServer.WINDOW_HANDLE))
		print("WINDOW_GUARD_READY configured_no_focus=", ProjectSettings.get_setting("display/window/size/no_focus", false), " no_focus=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_NO_FOCUS), " mouse_passthrough=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_MOUSE_PASSTHROUGH))
	call_deferred("launch_original")

func launch_original():
	if OS.get_environment("VOLIBEAR_TEST_WINDOW_GUARD") == "1" and not verify_window_manager("startup"):
		return
	var scene = ProjectSettings.get_setting("application/run/main_scene", "")
	print("STOCK_CONTROLLER_START scene=", scene)
	if scene == "" or change_scene_to_file(scene) != OK:
		print("STOCK_CONTROLLER_ERROR original scene unavailable")
		quit(2)

func find_source(node: Node, suffix: String):
	var script = node.get_script()
	if script != null and script.resource_path.ends_with(suffix):
		return node
	for child in node.get_children():
		var found = find_source(child, suffix)
		if found != null:
			return found
	return null

func _process(_delta):
	if exiting:
		return false
	if OS.get_environment("VOLIBEAR_TEST_WINDOW_GUARD") == "1" and (invalid_window_state()):
		push_error("WINDOW_GUARD_ERROR windowed/non-topmost contract lost")
		exiting = true
		quit(3)
		return false
	var now := Time.get_ticks_msec()
	if OS.get_environment("VOLIBEAR_TEST_WINDOW_GUARD") == "1" and now >= next_sample_ms:
		next_sample_ms = now + 10000
		print("WINDOW_RUNTIME_TIMING ticksMs=", now, " fps=", Engine.get_frames_per_second(), " max_fps=", Engine.max_fps, " vsync=", DisplayServer.window_get_vsync_mode())
		if Engine.get_frames_per_second() < 10:
			low_fps_samples += 1
		else:
			low_fps_samples = 0
		if low_fps_samples >= 3:
			push_error("WINDOW_PERFORMANCE_FAILED sustained FPS below 10")
			exiting = true
			quit(3)
			return false
	if Time.get_ticks_msec() - started > 240000:
		print("STOCK_CONTROLLER_ERROR readiness timeout")
		exiting = true
		quit(3)
		return false
	var path = OS.get_environment("VOLIBEAR_TEST_ARTIFACT_DIR") + "/game.log"
	var log_text = FileAccess.get_file_as_string(path) if FileAccess.file_exists(path) else ""
	if not "Preloading 'Common' Complete:" in log_text:
		return false
	var loader = find_source(root, "/NAssetLoader.cs")
	var game = find_source(root, "/NGame.cs")
	if loader != null and game != null and not loader.is_processing():
		ready_frames += 1
		if ready_frames >= 2:
			exiting = true
			if OS.get_environment("VOLIBEAR_TEST_WINDOW_GUARD") == "1":
				if not verify_window_manager("ready"):
					return false
			print("STOCK_CONTROLLER_READY_NATIVE_QUIT")
			game.call("Quit")
	else:
		ready_frames = 0
	return false

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
