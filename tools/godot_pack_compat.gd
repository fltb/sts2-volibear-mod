extends SceneTree

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2 or not ProjectSettings.load_resource_pack(args[0]):
		push_error("Cannot load compatibility-check PCK")
		quit(1)
		return
	var expected: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	if not expected is Dictionary or expected.is_empty():
		push_error("Missing independent GDScript source expectations")
		quit(1)
		return
	for path: String in expected:
		if not FileAccess.file_exists(path) or FileAccess.get_sha256(path) != expected[path]:
			push_error("Packed GDScript source changed or missing: " + path)
			quit(1)
			return
		if FileAccess.file_exists(path + ".remap") or FileAccess.file_exists(path.trim_suffix(".gd") + ".gdc"):
			push_error("Compiled GDScript remap is not portable: " + path)
			quit(1)
			return
	print("VOLIBEAR_PACK_COMPAT_PASS source_scripts=", expected.size(), " engine=4.5.1 renderer=gl_compatibility")
	quit(0)
