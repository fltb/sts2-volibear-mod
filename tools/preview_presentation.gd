extends SceneTree
## Isolated resource renderer. No game model, fake combat or gameplay timing.
const SCENES = "res://VolibearArt/scenes/"
const ICONS = "res://VolibearArt/icons/relics/"
const FPS = 12
const TILE_SIZE = Vector2i(452, 400)
var _output = ""
var _page: Control
var _failed = false

class FixtureTarget extends Node2D:
	func _draw() -> void:
		draw_circle(Vector2(0, -74), 33, Color(0.20, 0.29, 0.34), true, -1.0, true)
		draw_style_box(_body(), Rect2(-29, -51, 58, 50))
		draw_line(Vector2(-35, 0), Vector2(35, 0), Color(0.45, 0.59, 0.63), 2, true)
	func _body() -> StyleBoxFlat:
		var style = StyleBoxFlat.new()
		style.bg_color = Color(0.16, 0.24, 0.28)
		style.corner_radius_top_left = 18
		style.corner_radius_top_right = 18
		return style

class FixtureGrid extends Node2D:
	func _draw() -> void:
		for x in range(0, 453, 32):
			draw_line(Vector2(x, 0), Vector2(x, 400), Color(0.12, 0.20, 0.24), 1)
		for y in range(0, 401, 32):
			draw_line(Vector2(0, y), Vector2(452, y), Color(0.12, 0.20, 0.24), 1)
		draw_line(Vector2(0, 290), Vector2(452, 290), Color(0.29, 0.42, 0.46), 1)

func _initialize() -> void:
	call_deferred("run")

func fail(message: String) -> void:
	_failed = true
	push_error(message)
	quit(1)

func text_at(parent: Node, text: String, point: Vector2, font_size: int = 20, width: float = 430.0) -> Label:
	var label = Label.new()
	label.text = text
	label.position = point
	label.size = Vector2(width, font_size * 1.7)
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", Color(0.86, 0.93, 0.94))
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

func rectangle(parent: Node, area: Rect2, color: Color, z: int = 0) -> ColorRect:
	var block = ColorRect.new()
	block.position = area.position
	block.size = area.size
	block.color = color
	block.z_index = z
	block.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(block)
	return block

func texture_at(parent: Node, path: String, area: Rect2) -> TextureRect:
	var view = TextureRect.new()
	view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	view.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	view.texture = load(path) as Texture2D
	if view.texture == null:
		fail("Missing production preview texture: " + path)
	view.position = area.position
	view.size = area.size
	view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(view)
	return view

func page(size: Vector2i, title: String, subtitle: String) -> void:
	if is_instance_valid(_page):
		_page.free()
	root.size = size
	_page = Control.new()
	_page.size = size
	root.add_child(_page)
	rectangle(_page, Rect2(Vector2.ZERO, size), Color(0.025, 0.052, 0.071), -100)
	text_at(_page, title, Vector2(30, 20), 34, size.x - 60)
	text_at(_page, subtitle, Vector2(32, 69), 17, size.x - 64)

func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var image = root.get_texture().get_image()
	if image == null or image.is_empty() or image.get_size() != root.size:
		fail("Renderer did not return a real viewport image: " + name)
		return
	if image.save_png(_output.path_join(name)) != OK:
		fail("Cannot save rendered preview: " + name)

func actor_at(parent: Node, point: Vector2, scale_value: float = 1.0):
	var actor = load(SCENES + "volibear_combat.tscn").instantiate()
	actor.position = point
	actor.scale = Vector2.ONE * scale_value
	parent.add_child(actor)
	return actor

func energy_at(parent: Node, point: Vector2, value: int, scale_value: float = 1.0):
	var energy = load(SCENES + "volibear_energy.tscn").instantiate()
	energy.position = point
	energy.scale = Vector2.ONE * scale_value
	parent.add_child(energy)
	energy.get_node("Label").text = str(value) + "/3"
	return energy

func overview() -> void:
	page(Vector2i(1920, 1080), "VOLIBEAR  /  PRODUCTION RESOURCE PREVIEW",
		"Actual PCK scenes and textures in Godot 4.5.1. Resource playback only; this is not a game acceptance capture.")
	rectangle(_page, Rect2(32, 132, 660, 916), Color(0.055, 0.10, 0.13))
	text_at(_page, "AUTHORED CHARACTER", Vector2(62, 158), 25)
	text_at(_page, "Native AnimatedSprite2D / idle loop", Vector2(62, 200), 18)
	actor_at(_page, Vector2(364, 888), 1.15)
	text_at(_page, "Ground pivot and frame geometry preserved", Vector2(62, 985), 17, 590)
	for index in 2:
		var x = 716 + index * 596
		var id = "lightning_heart" if index == 0 else "storm_crown"
		var name = "LIGHTNING HEART / STARTER" if index == 0 else "STORM CROWN / UPGRADED"
		rectangle(_page, Rect2(x, 132, 572, 590), Color(0.055, 0.10, 0.13))
		text_at(_page, name, Vector2(x + 28, 157), 22, 520)
		texture_at(_page, ICONS + "big/" + id + ".png", Rect2(x + 158, 216, 256, 256))
		text_at(_page, "256 px inspection", Vector2(x + 190, 479), 17, 270)
		texture_at(_page, ICONS + id + ".png", Rect2(x + 150, 544, 64, 64))
		texture_at(_page, ICONS + "outline/" + id + ".png", Rect2(x + 342, 544, 64, 64))
		text_at(_page, "64 px normal", Vector2(x + 122, 624), 17, 170)
		text_at(_page, "64 px outline", Vector2(x + 310, 624), 17, 180)
	rectangle(_page, Rect2(716, 748, 1168, 300), Color(0.055, 0.10, 0.13))
	text_at(_page, "ENERGY / NATIVE LABEL INPUTS", Vector2(744, 766), 23, 1100)
	var states = [3, 2, 0, 4]
	var captions = ["Available", "After spending", "Depleted", "Recovered"]
	for index in 4:
		var x = 784 + index * 270
		energy_at(_page, Vector2(x, 825), states[index])
		text_at(_page, captions[index], Vector2(x - 14, 982), 18, 230)
	await create_timer(0.16).timeout
	await capture("overview.png")

func energy_sequence() -> void:
	page(Vector2i(720, 360), "ENERGY / NATIVE SCENE", "The preview drives Label text; the production cosmetic child reads it.")
	var energy = energy_at(_page, Vector2(268, 110), 3, 1.4)
	var caption = text_at(_page, "3 / 3  -  available", Vector2(36, 309), 22, 650)
	var states = [3, 2, 0, 4]
	var captions = ["available", "spend", "depleted", "recover"]
	for step in 4:
		energy.get_node("Label").text = str(states[step]) + "/3"
		caption.text = str(states[step]) + " / 3  -  " + captions[step]
		for frame in FPS:
			await create_timer(1.0 / FPS).timeout
			await capture("energy_frames/%03d.png" % (step * FPS + frame))
			if frame == 1:
				await capture("energy_" + str(states[step]) + ".png")

func fixture_target(parent: Node) -> Node2D:
	var target = FixtureTarget.new()
	target.position = Vector2(656, 580)
	target.scale = Vector2.ONE * 2.0
	parent.add_child(target)
	for name in ["CenterPos", "IntentPos"]:
		var marker = Marker2D.new()
		marker.name = name
		marker.position = Vector2(0, -70 if name == "CenterPos" else -132)
		target.add_child(marker)
	return target

func make_tile(effect: Dictionary, point: Vector2, number: int, background: Color = Color(0.048, 0.081, 0.10)) -> void:
	text_at(_page, "%02d  %s" % [number, effect.id], point, 20, TILE_SIZE.x)
	text_at(_page, effect.anchor + " / authored frame " + str(effect.poster_frame), point + Vector2(0, 29), 14, TILE_SIZE.x)
	var container = SubViewportContainer.new()
	container.position = point + Vector2(0, 56)
	container.size = TILE_SIZE
	_page.add_child(container)
	var viewport = SubViewport.new()
	viewport.size = TILE_SIZE
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(viewport)
	rectangle(viewport, Rect2(Vector2.ZERO, TILE_SIZE), background, -100)
	var grid = FixtureGrid.new()
	grid.z_index = -90
	viewport.add_child(grid)
	# Review at half-size by scaling the whole fixture, not only the character.
	# Leaving VFX unscaled beside a reduced actor overstates their size and obscures
	# whether the authored contact, ground and status effects fit the native actor.
	var world = Node2D.new()
	world.scale = Vector2.ONE * 0.5
	viewport.add_child(world)
	var owner = actor_at(world, Vector2(264, 580))
	var target = fixture_target(world)
	var card = rectangle(world, Rect2(540, 290, 208, 296), Color(0.16, 0.27, 0.31))
	texture_at(card, "res://VolibearArt/cards/production/sts2/Volibear/images/card_portraits/b01.png", Rect2(8, 48, 192, 188))
	var cost = text_at(card, "1", Vector2(10, 2), 38, 44)
	cost.size = Vector2(44, 48)
	cost.z_index = 32
	text_at(card, "CARD", Vector2(54, 248), 26, 140)
	var energy = energy_at(world, Vector2(492, 308), 3)
	var draw_pile = rectangle(world, Rect2(144, 498, 76, 96), Color(0.18, 0.30, 0.34))
	var discard_pile = rectangle(world, Rect2(604, 454, 88, 116), Color(0.18, 0.30, 0.34))
	text_at(discard_pile, "PILE", Vector2(6, 38), 24, 84)
	var card_effect = "card" in str(effect.anchor) or "pile" in str(effect.anchor)
	card.visible = card_effect
	energy.visible = effect.anchor == "owner_energy"
	draw_pile.visible = effect.anchor in ["draw_pile_to_hand", "source_pile_to_hand"]
	discard_pile.visible = effect.anchor == "card_to_discard_pile"
	target.visible = not card_effect and effect.anchor != "owner_energy"
	var hand = owner.get_node("%Visuals/VfxSpawnPosition") if owner.has_node("%Visuals/VfxSpawnPosition") else owner.get_node("%CenterPos")
	var mouth = owner.get_node("%TalkPos")
	var anchors = {"owner": owner, "target": discard_pile if effect.anchor == "card_to_discard_pile" else target,
		"source": draw_pile if draw_pile.visible else hand, "card": card, "energy": energy,
		"hand": hand, "mouth": mouth, "cost": cost}
	var fx = load(SCENES + "volibear_effects.tscn").instantiate()
	fx.configure("resource_preview", str(number))
	world.add_child(fx)
	if not fx.emit_effect("preview_" + effect.id, effect.id, anchors, "fixture_target",
		"preview_loop" if effect.loop else "", 60.0, false):
		fail("Production effect dispatch failed: " + effect.id)
		return
	# Static contact sheets deliberately seek an authored keyframe after real dispatch.
	# Disabling this preview instance's processing prevents the normal one-shot cleanup
	# from deleting its paused sprite; freeing the viewport still runs production exit cleanup.
	fx.set_process(false)
	var record = fx.get("_visuals").values()[0]
	var sprite = record.node as AnimatedSprite2D
	sprite.pause()
	sprite.set_frame_and_progress(int(effect.poster_frame), 0.0)
	var texture = sprite.sprite_frames.get_frame_texture(sprite.animation, sprite.frame)
	var used = texture.get_image().get_used_rect()
	if used.size == Vector2i.ZERO:
		fail("Authored keyframe is empty: " + effect.id)
		return
	var bounds = Rect2()
	var first = true
	for corner in [Vector2(used.position), Vector2(used.position + Vector2i(used.size.x, 0)),
		Vector2(used.end), Vector2(used.position + Vector2i(0, used.size.y))]:
		var pixel = sprite.get_global_transform_with_canvas() * (corner + sprite.offset)
		bounds = Rect2(pixel, Vector2.ZERO) if first else bounds.expand(pixel)
		first = false
	if not Rect2(Vector2.ZERO, TILE_SIZE).encloses(bounds):
		fail("Preview fixture would clip visible VFX: " + effect.id + " " + str(bounds))

func vfx_sheets() -> void:
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/vfx/manifest.json"))
	if manifest.effects.size() != 40:
		fail("Expected all 40 approved effects")
		return
	for group in 5:
		page(Vector2i(1920, 1080), "VFX %02d-%02d / 40  -  AUTHORED KEYFRAMES" % [group * 8 + 1, group * 8 + 8],
			"Production dispatch; actor and VFX share 50% zoom. Neutral target/card fixtures; resource review only. Audio is disabled.")
		for index in 8:
			make_tile(manifest.effects[group * 8 + index], Vector2(28 + (index % 4) * 474, 112 + floori(index / 4.0) * 476), group * 8 + index + 1)
			if _failed:
				return
		await process_frame
		await capture("vfx_group_%02d.png" % (group + 1))
	page(Vector2i(1920, 1080), "VFX CONTRAST / DARK AND LIGHT BACKGROUNDS",
		"Top: dark field. Bottom: bright stone. Actor and effects share 50% zoom; no contrast filter is applied.")
	var ids = ["lightning_strike", "lightning_all", "domain_loop", "absorb"]
	for row in 2:
		for column in 4:
			var effect: Dictionary
			for item in manifest.effects:
				if item.id == ids[column]:
					effect = item
					break
			make_tile(effect, Vector2(28 + column * 474, 112 + row * 476), column + 1,
				Color(0.048, 0.081, 0.10) if row == 0 else Color(0.80, 0.76, 0.66))
			if _failed:
				return
	await process_frame
	await capture("vfx_contrast.png")

func run() -> void:
	var args = OS.get_cmdline_user_args()
	if args.size() != 2 or not ProjectSettings.load_resource_pack(args[0]):
		fail("Usage: preview_presentation.gd -- production.pck output_directory")
		return
	_output = args[1]
	await overview()
	if _failed:
		return
	await energy_sequence()
	if _failed:
		return
	await vfx_sheets()
	if _failed:
		return
	_page.free()
	await process_frame
	print("VOLIBEAR_PREVIEW_PASS vfx=40 energy_states=4 relics=2")
	quit(0)
