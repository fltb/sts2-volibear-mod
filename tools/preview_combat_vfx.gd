extends SceneTree
## Executes the production controller, not a game model. Targets are labelled
## geometry fixtures. Optional captures use a real renderer, never --headless.
var _output := ""
var _failed := false
var _checks := 0
var _page: Node2D
var _capture := false
var _controller_scene: PackedScene
var _audio_refs: Array[WeakRef] = []

const GROUPS = {
	"physical": ["claw", "cross_claw", "rake", "sweep", "uppercut", "lunge", "slam", "stomp", "bite", "bite_tear", "feral_claw"],
	"thunder": ["bolt", "chain", "spear", "storm", "ground_thunder", "fork", "eruption"],
	"defense_synergy": ["guard", "armor", "retaliation", "domain_echo", "storm_charge", "thunder_armor", "replay_echo", "lifesteal", "beast", "absorb", "purify"],
}

class FixtureTarget extends Node2D:
	var dimensions := Vector2(90, 120)
	var lift := 0.0
	var armored := false
	func _ready() -> void:
		var bounds := Control.new()
		bounds.name = "Bounds"
		bounds.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bounds.position = Vector2(-dimensions.x * 0.5, -dimensions.y - lift)
		bounds.size = dimensions
		add_child(bounds)
		var center := Marker2D.new()
		center.name = "CenterPos"
		center.position = Vector2(0, -dimensions.y * 0.52 - lift)
		add_child(center)
		var intent := Marker2D.new()
		intent.name = "IntentPos"
		intent.position = Vector2(0, -dimensions.y - lift - 12)
		add_child(intent)
	func _draw() -> void:
		var base := Vector2(0, -lift)
		draw_line(Vector2(-dimensions.x * 0.6, 2), Vector2(dimensions.x * 0.6, 2), Color(0.24, 0.33, 0.39), 1)
		var body := Rect2(Vector2(-dimensions.x * 0.39, -dimensions.y * 0.75) + base, Vector2(dimensions.x * 0.78, dimensions.y * 0.75))
		draw_style_box(_body_style(), body)
		draw_circle(base - Vector2(0, dimensions.y * 0.78), dimensions.x * 0.28, Color(0.19, 0.27, 0.32), true, -1, true)
		if armored:
			for i in 3:
				var a := base + Vector2(-dimensions.x * 0.40, -dimensions.y * (0.25 + i * 0.18))
				draw_line(a, a + Vector2(dimensions.x * 0.8, 0), Color(0.39, 0.51, 0.57), 4, true)
	func _body_style() -> StyleBoxFlat:
		var s := StyleBoxFlat.new()
		s.bg_color = Color(0.15, 0.23, 0.28)
		s.corner_radius_top_left = 17
		s.corner_radius_top_right = 17
		return s

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> bool:
	_checks += 1
	if not condition:
		_failed = true
		push_error("Combat VFX: " + message)
	return condition

func actor(parent: Node, at: Vector2, size: Vector2 = Vector2(90, 120), lift: float = 0.0) -> FixtureTarget:
	var body := FixtureTarget.new()
	body.position = at
	body.dimensions = size
	body.lift = lift
	parent.add_child(body)
	return body

func effects(parent: Node, owner_id: String):
	var fx = _controller_scene.instantiate()
	fx.configure("combat-vfx-resource-test", owner_id)
	parent.add_child(fx)
	return fx

func watch_audio(fx: Node) -> void:
	# Observe production playback without extending either object's lifetime.
	# AudioServer may retain a stopped playback until its next mixing update.
	for record in fx.get("_voices").values():
		_audio_refs.append(weakref(record.node.stream))
		_audio_refs.append(weakref(record.node.get_stream_playback()))

func pending_audio() -> int:
	var remaining := 0
	for reference in _audio_refs:
		if reference.get_ref() != null:
			remaining += 1
	return remaining

func verify() -> void:
	var space := Node2D.new()
	root.add_child(space)
	space.position = Vector2(37, 19)
	space.scale = Vector2(1.2, 0.9)
	var owner := actor(space, Vector2(80, 240))
	var target := actor(space, Vector2(350, 240), Vector2(52, 76), 66)
	var fx = effects(space, "test-owner")
	fx.position = Vector2(11, -8)
	fx.scale = Vector2(0.8, 1.1)
	var anchors := {"owner": owner, "source": owner.get_node("CenterPos"), "target": target}
	var styles := 0
	for group in GROUPS.values():
		for style in group:
			check(fx.emit_combat("style:" + style, style, anchors, "target", {"hit_index": styles}), "style did not start: " + style)
			var v = fx.get("_combat_visuals").values()[-1].node
			check(v.source_point.is_finite() and v.contact_point.is_finite() and v.ground_point.is_finite() and v.target_size.is_finite(), "nonfinite geometry: " + style)
			styles += 1
	check(styles == 29 and fx.active_visuals() == 29, "all style routes are present")
	check(fx.active_voices() == 0, "new geometry must not create duplicate voices")
	check(not fx.emit_combat("style:claw", "claw", anchors, "target"), "same event must deduplicate")
	check(not fx.emit_combat("missing", "not-a-style", anchors, "target"), "unknown style must fail")
	check(not fx.emit_combat("missing-target-id", "claw", anchors), "target must have identity")
	var v = fx.get("_combat_visuals").values()[0].node
	var inverse: Transform2D = fx.get_global_transform_with_canvas().affine_inverse()
	var center: Vector2 = inverse * target.get_node("CenterPos").get_global_transform_with_canvas().origin
	var bounds: Control = target.get_node("Bounds")
	var feet: Vector2 = inverse * (bounds.get_global_transform_with_canvas() * Vector2(bounds.size.x * 0.5, bounds.size.y))
	check(v.contact_point.distance_to(center) < 0.01 and v.ground_point.distance_to(feet) < 0.01, "contact and feet must use current real target anchors")
	check(v.target_size.x < 90 and v.target_size.y < 90, "small target bounds adapt visual size")
	var small_radius: float = v._radius()
	bounds.size = Vector2(300, 420)
	fx._process(0.01)
	check(v._radius() > small_radius and v._radius() <= 110, "giant target grows with a bounded radius")
	var before: Vector2 = v.contact_point
	target.position.x += 70
	fx._process(0.01)
	check(v.contact_point.x > before.x + 60, "moving target must be followed")
	fx.stop_all()
	check(fx.active_visuals() == 0, "explicit owner clear")
	for i in 6:
		check(fx.emit_combat("accent:" + str(i), "thunder_armor", {"owner": owner}, "", {"hit_index": i}), "passive accent refresh is accepted")
	check(fx.active_visuals() == 1, "rapid passive receipts refresh one accent rather than obscure the actor")
	fx.stop_all()
	check(fx.emit_effect("ending-domain", "domain_loop", {"owner": owner}, "", "ending-domain", 10.0, true), "ending persistent field setup")
	check(fx.emit_effect("ending-atlas", "claw_slash", anchors, "target", "", 10.0, true), "ending atlas impact setup")
	check(fx.emit_combat("ending-impact", "claw", anchors, "target"), "ending procedural impact setup")
	check(fx.active_visuals() == 3 and fx.active_voices() == 2, "ending begins with loop and both impact paths")
	watch_audio(fx)
	fx.stop_persistent()
	check(fx.active_visuals() == 2 and fx.active_voices() == 1, "ending stops persistent field and loop sound, retaining one-shots")
	fx.stop_persistent()
	check(fx.active_visuals() == 2 and fx.active_voices() == 1, "persistent stop is idempotent")
	await create_timer(1.2).timeout
	check(fx.active_visuals() == 0 and fx.active_voices() == 0, "last impact and sound naturally finish after ending")
	check(fx.emit_effect("fading-domain", "domain_loop", {"owner": owner}, "", "fading-domain", 10.0, true), "fading loop setup")
	watch_audio(fx)
	fx.stop_loop("fading-domain", true)
	check(fx.active_voices() == 1, "fade leaves a short detached loop voice")
	fx.stop_persistent()
	check(fx.active_voices() == 0, "ending also stops a loop that has relinquished its key while fading")
	check(fx.emit_combat("final-clear", "chain", anchors, "target"), "final room clear setup")
	fx.stop_all()
	check(fx.active_visuals() == 0 and fx.active_voices() == 0, "full teardown still removes hit tails")
	for i in 80:
		fx.emit_combat("cap:" + str(i), "claw", anchors, "target", {"hit_index": i})
	check(fx.active_visuals() == 64, "shared visual cap")
	fx._process(1.0)
	check(fx.active_visuals() == 0, "fast delta expires every transient without a timer backlog")
	check(fx.emit_combat("freed-target", "chain", anchors, "target"), "free-target setup")
	target.free()
	fx._process(0.001)
	check(fx.active_visuals() == 0, "freed target clears attached visuals")
	var second := actor(space, Vector2(410, 260))
	var fx2 = effects(space, "second-owner")
	var a2 := {"owner": owner, "target": second}
	check(fx.emit_combat("same-event", "bolt", a2, "second") and fx2.emit_combat("same-event", "bolt", a2, "second"), "distinct owner controllers must not share dedup state")
	fx.stop_all()
	check(fx2.active_visuals() == 1, "owner clear leaves the other owner intact")
	space.free()
	await process_frame
	check(not is_instance_valid(fx) and not is_instance_valid(fx2), "room removal frees controllers and children")

func label(parent: Node, text: String, at: Vector2, size: int = 18) -> void:
	var node := Label.new()
	node.text = text
	node.position = at
	node.add_theme_font_size_override("font_size", size)
	node.add_theme_color_override("font_color", Color(0.76, 0.86, 0.90))
	parent.add_child(node)

func page(title: String, size: Vector2i) -> void:
	if is_instance_valid(_page):
		_page.free()
	root.size = size
	_page = Node2D.new()
	root.add_child(_page)
	var backdrop := ColorRect.new()
	backdrop.size = size
	backdrop.color = Color(0.025, 0.055, 0.075)
	backdrop.z_index = -100
	_page.add_child(backdrop)
	label(_page, title, Vector2(24, 17), 29)
	label(_page, "Production VFX in Godot / geometry targets / resource playback, not a game capture", Vector2(25, 56), 15)

func tile(index: int, style: String, options: Dictionary = {}):
	var column := index % 4
	var row := int(index / 4)
	var slot := Node2D.new()
	slot.position = Vector2(22 + column * 340, 100 + row * 276)
	_page.add_child(slot)
	label(slot, style.to_upper().replace("_", " "), Vector2(5, 3), 19)
	var owner := actor(slot, Vector2(37, 225), Vector2(39, 75))
	var target := actor(slot, Vector2(228, 225), Vector2(86, 125))
	var fx = effects(slot, "gallery:" + style)
	fx.emit_combat("gallery:" + style, style, {"owner": owner, "target": target, "source": owner.get_node("CenterPos")}, "fixture", options)
	fx.set_process(false)
	for r in fx.get("_combat_visuals").values():
		r.node.seek_fraction(0.26)
	return fx

func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if not check(image != null and not image.is_empty() and image.get_size() == root.size, "real viewport capture: " + name):
		return
	check(image.save_png(_output.path_join(name)) == OK, "write capture: " + name)

func gallery() -> void:
	for group in GROUPS:
		var styles: Array = GROUPS[group]
		page("VOLIBEAR / " + group.to_upper().replace("_", " + "), Vector2i(1404, 100 + ceili(styles.size() / 4.0) * 276))
		for i in styles.size():
			tile(i, styles[i], {"hit_index": i})
		await capture(group + ".png")
	page("VOLIBEAR / TARGET GEOMETRY + BLOCK", Vector2i(1404, 660))
	for i in 4:
		var slot := Node2D.new()
		slot.position = Vector2(22 + i * 340, 120)
		_page.add_child(slot)
		label(slot, ["SMALL / CLAW", "LARGE / CLAW", "AIRBORNE / GROUND", "BLOCKED / CLAW"][i], Vector2(4, 0), 18)
		var owner := actor(slot, Vector2(27, 420), Vector2(34, 70))
		var target := actor(slot, Vector2(220, 420), [Vector2(45, 60), Vector2(150, 255), Vector2(80, 110), Vector2(90, 140)][i], 100 if i == 2 else 0)
		target.armored = i == 3
		var fx = effects(slot, "geometry:" + str(i))
		fx.emit_combat("geometry:" + str(i), "ground_thunder" if i == 2 else "claw", {"owner": owner, "target": target}, "fixture", {"blocked": i == 3})
		fx.set_process(false)
		for r in fx.get("_combat_visuals").values():
			r.node.seek_fraction(0.25)
	await capture("target_geometry.png")
	page("VOLIBEAR / MOTION STUDIES", Vector2i(1404, 652))
	var animated := []
	for i in 8:
		animated.append(tile(i, ["cross_claw", "sweep", "slam", "bite_tear", "chain", "storm", "eruption", "lifesteal"][i]))
	for frame in 32:
		for fx in animated:
			for r in fx.get("_combat_visuals").values():
				r.node.seek_fraction((frame % 16) / 16.0)
		await capture("frames/%03d.png" % frame)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() >= 1 and args[0] != "-":
		if not check(ProjectSettings.load_resource_pack(args[0]), "load production PCK"):
			quit(1)
			return
	_output = args[1] if args.size() >= 2 else ""
	_capture = not _output.is_empty()
	_controller_scene = load("res://VolibearArt/scenes/volibear_effects.tscn")
	await verify()
	if _capture and not _failed:
		await gallery()
	if is_instance_valid(_page):
		_page.free()
	_page = null
	# Release and verify the fixture's final strong resource reference before
	# shutdown rather than relying on SceneTree destruction during engine exit.
	var controller_ref: WeakRef = weakref(_controller_scene)
	_controller_scene = null
	# process_frame is emitted before the deferred-delete queue drains. Cross
	# that boundary and the following frame; headless has no frame_post_draw.
	await process_frame
	await process_frame
	check(root.get_child_count() == 0, "fixture removes every scene node before exit")
	check(controller_ref.get_ref() == null, "fixture releases the controller PackedScene before exit")
	# Headless process frames can finish before one audio mix. Give the real
	# audio thread bounded time to relinquish stopped streams/playbacks; never
	# ignore a leaked reference or turn a failed shutdown into a passing result.
	var pending_at_teardown := pending_audio()
	var deadline := Time.get_ticks_msec() + 500
	while pending_audio() > 0 and Time.get_ticks_msec() < deadline:
		await create_timer(0.01).timeout
	check(pending_audio() == 0, "stopped audio streams and playbacks release within 500 ms")
	print("VOLIBEAR_COMBAT_VFX_AUDIO_DRAIN observed=" + str(_audio_refs.size()) + " pending_at_teardown=" + str(pending_at_teardown) + " remaining=" + str(pending_audio()))
	_audio_refs.clear()
	print("VOLIBEAR_COMBAT_VFX_" + ("FAIL" if _failed else "PASS") + " styles=29 checks=" + str(_checks) + " capture=" + str(_capture))
	quit(1 if _failed else 0)
