extends SceneTree
## Tests the shipped effects.gd controller itself, not a separate presentation simulator.
func fail(message: String) -> void:
	push_error(message)
	quit(1)

func _initialize() -> void:
	call_deferred("verify")

func verify() -> void:
	var args = OS.get_cmdline_user_args()
	if args.size() != 2 or not ProjectSettings.load_resource_pack(args[0]):
		fail("Cannot mount effects candidate")
		return
	var expected = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var frames = load("res://VolibearArt/scenes/volibear_effect_frames.tres") as SpriteFrames
	if frames == null or frames.get_animation_names().size() != 40:
		fail("Expected exactly 40 VFX animations")
		return
	for id in expected.effects:
		var row = expected.effects[id]
		if not frames.has_animation(id) or frames.get_frame_count(id) != row.frames or frames.get_animation_loop(id) != row.loop:
			fail("VFX frame/loop contract mismatch: " + id)
			return
		for index in frames.get_frame_count(id):
			var texture = frames.get_frame_texture(id, index) as AtlasTexture
			if texture == null or texture.get_size() != Vector2(row.tile[0], row.tile[1]):
				fail("VFX region mismatch: " + id)
				return
		var atlas = frames.get_frame_texture(id, 0) as AtlasTexture
		if atlas.atlas.get_image().is_empty():
			fail("VFX atlas decode failed: " + id)
			return
	for row in expected.audio:
		var stream = load(row.path) as AudioStreamOggVorbis
		if stream == null or absf(stream.get_length() - row.seconds) > 0.05:
			fail("Ogg stream duration/decode mismatch: " + row.path)
			return
		var playback = stream.instantiate_playback()
		playback.start()
		var energy = 0.0
		for block in 4:
			var samples = playback.mix_audio(1.0, 4096)
			for sample in samples:
				energy += sample.length_squared()
		playback.stop()
		if energy <= 0.000001:
			fail("Ogg decoder produced no nonzero PCM: " + row.path)
			return
	for path in expected.icons:
		var texture = load(path) as Texture2D
		var size = expected.icons[path]
		if texture == null or texture.get_size() != Vector2(size, size) or texture.get_image().is_empty():
			fail("Original rune icon decode failed: " + path)
			return
	var audio = JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/audio/manifest.json"))
	if audio.cues.size() != 54 or expected.audio.size() != 47:
		fail("Cue coverage mismatch")
		return
	if not await verify_energy():
		return
	var owner = Node2D.new()
	owner.position = Vector2(100, 200)
	root.add_child(owner)
	var target = Node2D.new()
	target.position = Vector2(500, 150)
	root.add_child(target)
	var fx = load("res://VolibearArt/scenes/volibear_effects.tscn").instantiate()
	fx.configure("resource_test_battle", "resource_test_owner")
	root.add_child(fx)
	if not await verify_ground_coverage(fx):
		return
	var anchors = {"owner": owner, "target": target}
	if not fx.emit_effect("hit_1", "claw_slash", anchors, "enemy_1"):
		fail("Production effect/sound failed to start")
		return
	if fx.emit_effect("hit_1", "claw_slash", anchors, "enemy_1") or fx.active_visuals() != 1 or fx.active_voices() != 1:
		fail("Semantic dedup failed")
		return
	await create_timer(0.15).timeout
	if fx.get("_visuals").values()[0].node.frame == 0 or not fx.get("_voices").values()[0].node.playing:
		fail("Native animation/audio playback did not advance")
		return
	await create_timer(1.05).timeout
	if fx.active_visuals() != 0 or fx.active_voices() != 0:
		fail("One-shot visual/audio did not clean up")
		return
	# Verify authored segment endpoints map to current real nodes, including reverse lifesteal.
	for id in ["lightning_chain", "lifesteal"]:
		if not fx.emit_effect("segment_" + id, id, anchors, "enemy_1", "", 10.0, false):
			fail("Segment failed to start: " + id)
			return
		var record = fx.get("_visuals").values()[0]
		var segment = record.effect.segment_anchors_px
		var start = Vector2(segment.source[0], segment.source[1])
		var finish = Vector2(segment.target[0], segment.target[1])
		var sprite = record.node
		var a = sprite.transform * (start + sprite.offset)
		var b = sprite.transform * (finish + sprite.offset)
		var wanted_a = target.position if id == "lifesteal" else owner.position
		var wanted_b = owner.position if id == "lifesteal" else target.position
		if a.distance_to(wanted_a) > 0.01 or b.distance_to(wanted_b) > 0.01:
			fail("Authored segment transform is wrong: " + id)
			return
		fx.stop_all()
	if not fx.emit_effect("domain_on", "domain_loop", {"owner": owner}, "", "domain", 0.5):
		fail("Persistent domain loop did not start")
		return
	var voice_id = fx.get("_voices").values()[0].node.get_instance_id()
	await create_timer(0.08).timeout
	if not fx.emit_effect("domain_refresh", "domain_loop", {"owner": owner}, "", "domain", 0.5) or fx.active_visuals() != 1 or fx.active_voices() != 1:
		fail("Persistent lease refresh duplicated a loop")
		return
	if fx.get("_voices").values()[0].node.get_instance_id() != voice_id:
		fail("Persistent sound restarted on visual renewal")
		return
	fx.stop_loop("domain")
	await create_timer(0.25).timeout
	if fx.active_visuals() != 0 or fx.active_voices() != 0:
		fail("Loop stop/fade did not clean up")
		return
	if fx.play_sound("disabled", "sfx.feral_aura", "feral"):
		fail("Default-disabled audio was unexpectedly played")
		return
	if not fx.play_sound("short", "sfx.guard_hit", "", 0.1):
		fail("Native audio failed to start")
		return
	if fx.play_sound("cooldown", "sfx.guard_hit"):
		fail("Cue cooldown was not enforced")
		return
	await create_timer(0.25).timeout
	if fx.active_voices() != 0:
		fail("Audio safety lease was not enforced")
		return
	if not fx.emit_effect("lease", "domain_loop", {"owner": owner}, "", "lease", 0.1):
		fail("Safety lease failed to start")
		return
	await create_timer(0.25).timeout
	if fx.active_visuals() != 0 or fx.active_voices() != 0:
		fail("Persistent safety lease leaked")
		return
	for index in 64:
		if not fx.emit_effect("capacity_" + str(index), "guard_gain", {"owner": owner}, "", "", 10.0, false):
			fail("Visual capacity rejected a valid slot")
			return
	if fx.emit_effect("overflow", "guard_gain", {"owner": owner}, "", "", 10.0, false) or fx.active_visuals() != 64:
		fail("Visual capacity is not bounded")
		return
	fx.stop_all()
	if not await verify_all_effects(fx, owner, target, expected.effects):
		return
	if not fx.emit_effect("mark", "mark_bite", anchors, "enemy_1", "mark", 10.0, false):
		fail("Target-bound loop failed")
		return
	target.queue_free()
	await process_frame
	await process_frame
	if fx.active_visuals() != 0:
		fail("Freed target retained presentation")
		return
	fx.emit_effect("exit", "domain_loop", {"owner": owner}, "", "exit", 10.0)
	root.remove_child(fx)
	if fx.active_visuals() != 0 or fx.active_voices() != 0:
		fail("Scene exit did not stop owned playback")
		return
	fx.free()
	owner.free()
	# Native AudioServer retires stopped playback on its mixer thread, not queue_free's frame.
	# Give it a bounded drain interval before testing clean engine shutdown.
	await create_timer(0.25).timeout
	print("VOLIBEAR_EFFECTS_PASS vfx=40 audio=47 cues=54 icons=10 lifecycle=PASS")
	quit(0)

func verify_ground_coverage(fx) -> bool:
	var actor = load("res://VolibearArt/scenes/volibear_combat.tscn").instantiate()
	actor.position = Vector2(600, 600)
	root.add_child(actor)
	var body = actor.get_node("Bounds") as Control
	for id in ["domain_enter", "domain_loop", "domain_exit", "feral_aura"]:
		if not fx.emit_effect("ground_" + id, id, {"owner": actor}, "", "ground" if id == "domain_loop" else "", 10.0, false):
			fail("Ground composition effect did not start: " + id)
			return false
		var record = fx.get("_visuals").values()[0]
		var sprite = record.node as AnimatedSprite2D
		sprite.set_frame_and_progress(int(record.effect.poster_frame), 0.0)
		var used = sprite.sprite_frames.get_frame_texture(id, sprite.frame).get_image().get_used_rect()
		var left = (sprite.transform * (Vector2(used.position) + sprite.offset)).x - actor.position.x
		var right = (sprite.transform * (Vector2(used.end) + sprite.offset)).x - actor.position.x
		if left > body.position.x or right < body.position.x + body.size.x or right - left > body.size.x * 1.25:
			fail("Ground effect must enclose the native feet without becoming an oversized field: " + id)
			return false
		if sprite.z_index >= 0 or not sprite.position.is_equal_approx(actor.position):
			fail("Ground effect must remain behind the actor at its ground pivot: " + id)
			return false
		actor.position += Vector2(20, 10)
		await process_frame
		await process_frame
		if not sprite.position.is_equal_approx(actor.position):
			fail("Ground effect did not follow the actor's real position: " + id)
			return false
		fx.stop_all()
	actor.free()
	print("VOLIBEAR_GROUND_VFX_PASS effects=4 feet_coverage=PASS following=PASS layering=PASS")
	return true

func verify_energy() -> bool:
	var energy = load("res://VolibearArt/scenes/volibear_energy.tscn").instantiate()
	root.add_child(energy)
	var ring = energy.get_node_or_null("Layers/RotationLayers/StormRing")
	var label = energy.get_node("Label") as Label
	if ring == null or ring.get_script() == null or not ring.get("_has_value") or ring.get("_energy_value") != 3 or ring.get("_pulse") != 0.0:
		fail("Energy must initialize from the native label without a false gain pulse")
		return false
	var phase = ring.get("_phase")
	await create_timer(0.1).timeout
	if ring.get("_phase") == phase or label.text != "3/3":
		fail("Energy rim did not animate independently of the native numeric value")
		return false
	for step in [["2/3", 2, -1], ["0/3", 0, -1], ["4/3", 4, 1]]:
		label.text = step[0]
		await process_frame
		await process_frame
		if ring.get("_energy_value") != step[1] or ring.get("_pulse_direction") != step[2] or ring.get("_pulse") <= 0.0 or label.text != step[0]:
			fail("Energy spend/depletion/recovery did not follow the native label")
			return false
	await create_timer(0.5).timeout
	label.text = "4/4"
	await process_frame
	await process_frame
	if ring.get("_pulse") != 0.0:
		fail("Max-energy formatting changes must not fabricate a gain pulse")
		return false
	label.text = "?"
	await process_frame
	await process_frame
	if ring.get("_energy_value") != 4:
		fail("Unknown native energy text was treated as depletion")
		return false
	label.text = "[color=#ffffff]0/4[/color]"
	await process_frame
	await process_frame
	if ring.get("_energy_value") != 0:
		fail("Formatted native label did not preserve the numeric energy state")
		return false
	if energy.get_node("Layers/Emblem").size.x > 48 or label.z_index <= energy.get_node("Layers").z_index:
		fail("Energy crest/number separation regressed")
		return false
	energy.free()
	print("VOLIBEAR_ENERGY_PASS animation=PASS spend=PASS depleted=PASS recovery=PASS")
	return true

func verify_all_effects(fx, owner: Node2D, target: Node2D, expected: Dictionary) -> bool:
	# Exercise every shipped effect through its production dispatcher, with all required anchors.
	# Atlas decoding alone cannot reveal an unhandled anchor or a stopped animation.
	var card = Control.new()
	card.position = Vector2(720, 480)
	card.size = Vector2(180, 260)
	root.add_child(card)
	var energy = Control.new()
	energy.position = Vector2(30, 570)
	energy.size = Vector2(128, 128)
	root.add_child(energy)
	var cost = Node2D.new()
	cost.position = Vector2(12, 12)
	card.add_child(cost)
	var anchors = {"owner": owner, "target": target, "source": owner, "card": card,
		"energy": energy, "hand": owner, "mouth": owner, "cost": cost}
	for id in expected:
		var key = "all_" + id if expected[id].loop else ""
		if not fx.emit_effect("all_" + id, id, anchors, "enemy_1", key, 3.0, false):
			fail("Shipped effect could not execute its anchor route: " + id)
			return false
	if fx.active_visuals() != 40:
		fail("All forty effects must start as independent presentation instances")
		return false
	await create_timer(0.15).timeout
	for record in fx.get("_visuals").values():
		if record.node.frame == 0 or not record.node.is_playing():
			fail("Shipped effect animation did not advance: " + record.effect.id)
			return false
	await create_timer(1.8).timeout
	var remaining: Array = []
	for record in fx.get("_visuals").values():
		remaining.append(str(record.effect.id))
	remaining.sort()
	if remaining != ["domain_loop", "mark_bite"]:
		fail("One-shot cleanup or persistent-loop playback failed: " + str(remaining))
		return false
	fx.stop_all()
	if fx.active_visuals() != 0 or fx.active_voices() != 0:
		fail("All-effect batch left presentation owners alive")
		return false
	card.free()
	energy.free()
	print("VOLIBEAR_ALL_VFX_PASS played=40 advanced=40 cleanup=PASS")
	return true
