extends SceneTree
## Composition/scale review using production actor + VFX resources. The fixture
## clock samples authored frames and supplies example committed-event order. It
## is deliberately not a game, a card simulator, or native timing acceptance.
const FPS := 24
const FRAME_COUNT := 60
const CASES = [
	{"title": "C02 / DOUBLE CLAW", "detail": "Two contact strokes / separate hit identities", "clip": "double_claw", "hits": [7, 15], "style": "cross_claw", "targets": 1},
	{"title": "U07 / MOUNTAIN STOMPS", "detail": "Four impacts / bounded ground contacts", "clip": "stomp_chain", "hits": [8, 17, 24, 29], "style": "stomp", "targets": 1},
	{"title": "U08 / BITE + MARKED FOLLOWUP", "detail": "First bite then tearing jaws / two hits", "clip": "bite_rend", "hits": [9, 17], "style": "bite", "targets": 1},
	{"title": "R17 / THUNDER SPEARS", "detail": "Channel pose / three distinct projectiles", "clip": "chain_channel", "hits": [9, 15, 21], "style": "spear", "targets": 1},
	{"title": "R07 / HEAVEN AND EARTH", "detail": "Storm channel / actual target anchors", "clip": "storm_channel", "hits": [15], "style": "eruption", "targets": 3},
	{"title": "C05 / DOMAIN + FOLLOWUP + ARMOR", "detail": "Attack > domain echo > chain > armor", "clip": "claw_flurry", "hits": [6, 12, 18], "style": "cross_claw", "targets": 3, "domain": true},
]
var _output := ""
var _page: Node2D
var _actor_scene: PackedScene
var _effects_scene: PackedScene
var _rows: Array[Dictionary] = []
var _failed := false
var _events := 0

class Target extends Node2D:
	var dimensions := Vector2(86, 125)
	func _ready() -> void:
		var bounds := Control.new()
		bounds.name = "Bounds"
		bounds.position = Vector2(-dimensions.x * 0.5, -dimensions.y)
		bounds.size = dimensions
		bounds.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(bounds)
		var center := Marker2D.new()
		center.name = "CenterPos"
		center.position = Vector2(0, -dimensions.y * 0.54)
		add_child(center)
	func _draw() -> void:
		var body := StyleBoxFlat.new()
		body.bg_color = Color(0.19, 0.29, 0.34)
		body.corner_radius_top_left = 15
		body.corner_radius_top_right = 15
		draw_style_box(body, Rect2(Vector2(-dimensions.x * 0.38, -dimensions.y * 0.74), dimensions * Vector2(0.76, 0.74)))
		draw_circle(Vector2(0, -dimensions.y * 0.78), dimensions.x * 0.28, Color(0.24, 0.34, 0.40), true, -1, true)
		draw_line(Vector2(-dimensions.x * 0.5, 2), Vector2(dimensions.x * 0.5, 2), Color(0.28, 0.40, 0.46), 1)

func _initialize() -> void:
	call_deferred("run")

func text(parent: Node, value: String, point: Vector2, size: int, color: Color = Color(0.77, 0.88, 0.93)) -> void:
	var label := Label.new()
	label.text = value
	label.position = point
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	parent.add_child(label)

func setup_case(index: int) -> void:
	var data: Dictionary = CASES[index]
	var slot := Node2D.new()
	slot.position = Vector2(25 + index % 2 * 730, 104 + int(index / 2) * 330)
	_page.add_child(slot)
	var background := ColorRect.new()
	background.position = Vector2(-6, -4)
	background.size = Vector2(710, 310)
	background.color = Color(0.045, 0.083, 0.105)
	background.z_index = -100
	slot.add_child(background)
	text(slot, data.title, Vector2(10, 7), 21)
	text(slot, data.detail, Vector2(10, 35), 15, Color(0.48, 0.66, 0.73))
	var actor = _actor_scene.instantiate()
	actor.position = Vector2(162, 296)
	actor.scale = Vector2.ONE * 0.54
	slot.add_child(actor)
	var sprite: AnimatedSprite2D = actor.get_node("Visuals/AnimatedSprite2D")
	var is_domain: bool = data.get("domain", false)
	sprite.return_animation = "domain_idle" if is_domain else "idle_loop"
	sprite.play_action(data.clip)
	sprite.pause()
	var targets := []
	for i in int(data.targets):
		var target := Target.new()
		target.position = Vector2(565 if data.targets == 1 else 450 + i * 95, 296)
		target.dimensions = Vector2(80, 122) if data.targets == 1 else Vector2(58, 96 + i * 14)
		slot.add_child(target)
		targets.append(target)
	var fx = _effects_scene.instantiate()
	fx.configure("resource-composition", "case:" + str(index))
	slot.add_child(fx)
	fx.set_process(false)
	if is_domain:
		fx.emit_effect("domain:entry", "domain_loop", {"owner": actor}, "", "sample-domain", 30.0, false)
	_rows.append({"data": data, "actor": actor, "sprite": sprite, "targets": targets, "fx": fx, "index": index})

func emit(row: Dictionary, frame: int, hit: int, style: String, target_index: int, owner_effect: bool = false) -> void:
	var anchors := {"owner": row.actor, "source": row.actor.get_node("CenterPos")}
	if not owner_effect:
		anchors.target = row.targets[target_index]
	var id := "sample:%s:%s:%s:%s:%s" % [row.index, frame, hit, style, target_index]
	if not row.fx.emit_combat(id, style, anchors, "" if owner_effect else "fixture:" + str(target_index), {"hit_index": hit}):
		_failed = true
		push_error("Composition failed to dispatch " + id)
	_events += 1

func sample(frame: int) -> void:
	for row in _rows:
		var data: Dictionary = row.data
		var sprite: AnimatedSprite2D = row.sprite
		var action_frames: int = sprite.sprite_frames.get_frame_count(data.clip)
		if frame < action_frames:
			sprite.animation = data.clip
			sprite.set_frame_and_progress(frame, 0.0)
		else:
			sprite.animation = sprite.return_animation
			sprite.set_frame_and_progress((frame - action_frames) % sprite.sprite_frames.get_frame_count(sprite.return_animation), 0.0)
		sprite.pause()
		row.fx._process(1.0 / FPS)
		for hit in data.hits.size():
			var contact_frame: int = data.hits[hit]
			if frame == contact_frame:
				var style: String = "bite_tear" if row.index == 2 and hit > 0 else data.style
				if row.index == 4:
					for i in row.targets.size():
						emit(row, frame, hit, style, i)
				else:
					emit(row, frame, hit, style, 0)
			if row.index == 5:
				if frame == contact_frame + 2:
					for i in row.targets.size():
						emit(row, frame, hit, "domain_echo", i)
				if frame == contact_frame + 4:
					for i in row.targets.size():
						emit(row, frame, hit, "chain", i)
				if frame == contact_frame + 5:
					emit(row, frame, hit, "thunder_armor", 0, true)

func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var picture := root.get_texture().get_image()
	if picture == null or picture.is_empty() or picture.get_size() != root.size or picture.save_png(_output.path_join(name)) != OK:
		_failed = true
		push_error("Composition capture failed: " + name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		push_error("Expected pack-or-dash and output directory")
		quit(1)
		return
	if args[0] != "-" and not ProjectSettings.load_resource_pack(args[0]):
		push_error("Cannot load production pack")
		quit(1)
		return
	_output = args[1]
	_actor_scene = load("res://VolibearArt/scenes/volibear_combat.tscn")
	_effects_scene = load("res://VolibearArt/scenes/volibear_effects.tscn")
	root.size = Vector2i(1480, 1100)
	_page = Node2D.new()
	root.add_child(_page)
	var background := ColorRect.new()
	background.size = root.size
	background.color = Color(0.025, 0.05, 0.067)
	background.z_index = -100
	_page.add_child(background)
	text(_page, "VOLIBEAR / COMBAT PRESENTATION", Vector2(26, 17), 31)
	text(_page, "Production actor + effects / resource playback on geometry targets / illustrative event order, not game timing acceptance", Vector2(28, 62), 16)
	for i in CASES.size():
		setup_case(i)
	for frame in FRAME_COUNT:
		sample(frame)
		await capture("frames/%03d.png" % frame)
		if frame == 18:
			await capture("combat_combos.png")
	for row in _rows:
		row.fx.stop_all()
	_page.free()
	await process_frame
	print("VOLIBEAR_COMBAT_COMPOSITION_" + ("FAIL" if _failed else "PASS") + " cases=6 frames=60 effects=" + str(_events))
	quit(1 if _failed else 0)
