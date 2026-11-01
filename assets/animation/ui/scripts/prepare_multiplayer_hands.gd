extends SceneTree
## Deterministic texture-size preparation; the four authored gestures are inputs.
## No repainting or regeneration of the approved character or existing UI.

const GESTURES = ["pointing", "rock", "paper", "scissors"]
const CANVAS = Vector2i(422, 1200)

func _initialize() -> void:
	var root: String = get_script().resource_path.get_base_dir().get_base_dir()
	for gesture in GESTURES:
		var source := root.path_join("source/multiplayer_hands/%s.png" % gesture)
		var original := Image.load_from_file(source)
		if original == null or original.is_empty() or not original.detect_alpha():
			push_error("Missing transparent authored hand: " + source)
			quit(1)
			return
		original.convert(Image.FORMAT_RGBA8)
		# Match native texture proportions. NHandImage pivots belong to its
		# TextureRect, NOT these pixels; do not crop/reposition the claw to them.
		var ratio := float(original.get_width()) / original.get_height()
		if absf(ratio - float(CANVAS.x) / CANVAS.y) > 0.02:
			push_error("Authored hand does not have native long-forearm proportions: " + gesture)
			quit(1)
			return
		var factor := minf(float(CANVAS.x) / original.get_width(), float(CANVAS.y) / original.get_height())
		var height := roundi(original.get_height() * factor)
		var width := roundi(original.get_width() * factor)
		original.resize(width, height, Image.INTERPOLATE_LANCZOS)
		var offset := Vector2i((CANVAS.x - width) / 2, CANVAS.y - height)
		var output := Image.create(CANVAS.x, CANVAS.y, false, Image.FORMAT_RGBA8)
		output.fill(Color.TRANSPARENT)
		output.blit_rect(original, Rect2i(Vector2i.ZERO, original.get_size()), offset)
		var destination := root.path_join("images/multiplayer_hand_volibear_%s.png" % gesture)
		if output.save_png(destination) != OK:
			push_error("Could not write " + destination)
			quit(1)
			return
		print("Prepared ", gesture, " ", CANVAS, " offset=", offset)
	quit(0)
