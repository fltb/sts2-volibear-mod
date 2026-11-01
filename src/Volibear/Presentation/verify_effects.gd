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
	var owner = Node2D.new()
	owner.position = Vector2(100, 200)
	root.add_child(owner)
	var target = Node2D.new()
	target.position = Vector2(500, 150)
	root.add_child(target)
	var fx = load("res://VolibearArt/scenes/volibear_effects.tscn").instantiate()
	fx.configure("resource_test_battle", "resource_test_owner")
	root.add_child(fx)
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
