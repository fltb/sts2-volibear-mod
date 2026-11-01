extends SceneTree
## Isolated Godot resource check, deliberately NOT a game acceptance test.
func fail(message: String) -> void:
	push_error(message)
	quit(1)

func _initialize() -> void:
	call_deferred("verify")

func verify() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2 or not ProjectSettings.load_resource_pack(args[0]):
		fail("Could not mount resource candidate")
		return
	var expected = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var frames = load("res://VolibearArt/scenes/volibear_frames.tres") as SpriteFrames
	if frames == null:
		fail("Missing SpriteFrames")
		return
	var frame_count := 0
	for clip in expected.clips:
		if not frames.has_animation(clip) or frames.get_frame_count(clip) != expected.clips[clip].frames or frames.get_animation_loop(clip) != expected.clips[clip].loop:
			fail("Wrong authored clip: " + clip)
			return
		for index in frames.get_frame_count(clip):
			var texture = frames.get_frame_texture(clip, index) as AtlasTexture
			if texture == null or texture.atlas == null or texture.get_size() != Vector2(512, 512):
				fail("Invalid atlas region: " + clip)
				return
		frame_count += frames.get_frame_count(clip)
	for path in expected.portraits:
		var portrait = load(path) as Texture2D
		var size := Vector2(1000, 760) if "/big/" in path else Vector2(250, 190)
		if portrait == null or portrait.get_size() != size or portrait.get_image().is_empty():
			fail("Invalid portrait: " + path)
			return
	var combat = load("res://VolibearArt/scenes/volibear_combat.tscn").instantiate()
	root.add_child(combat)
	for marker in ["Visuals", "PhobiaModeVisuals", "Bounds", "CenterPos", "IntentPos", "TalkPos", "OrbPos", "FormVfx"]:
		if combat.get_node_or_null("%" + marker) == null:
			fail("Missing unique BaseLib marker: " + marker)
			return
	var actor = combat.get_node("Visuals/AnimatedSprite2D")
	if actor.animation != &"idle_loop" or not actor.is_playing():
		fail("Combat idle did not start")
		return
	for trigger in ["Attack", "Hurt"]:
		actor.play(trigger)
		await create_timer(1.2).timeout
		if actor.animation != &"idle_loop" or not actor.is_playing():
			fail("Action failed to return to idle: " + trigger)
			return
	actor.play("Die")
	await create_timer(1.9).timeout
	if actor.animation != &"Die" or actor.frame != 39 or actor.is_playing():
		fail("Death did not hold authored final frame")
		return
	var selection = load("res://VolibearArt/scenes/volibear_selection.tscn").instantiate()
	root.add_child(selection)
	var selection_actor = selection.get_node("ActorAnchor/AnimatedSprite2D")
	if selection_actor.animation != &"relaxed_loop" or not selection_actor.is_playing():
		fail("Selection animation did not start")
		return
	selection.free()
	combat.free()
	if not verify_ui():
		return
	print("VOLIBEAR_RESOURCE_PASS clips=", expected.clips.size(), " frames=", frame_count, " portraits=", expected.portraits.size())
	quit(0)

func verify_ui() -> bool:
	var icon = load("res://VolibearArt/scenes/volibear_icon.tscn").instantiate()
	root.add_child(icon)
	if not icon is TextureRect or icon.texture.get_size() != Vector2(128, 128):
		fail("Invalid authored character icon")
		return false
	icon.free()
	var energy = load("res://VolibearArt/scenes/volibear_energy.tscn").instantiate()
	root.add_child(energy)
	for marker in ["Layers", "RotationLayers", "EnergyVfxBack", "EnergyVfxFront", "StarAnchor"]:
		if energy.get_node_or_null("%" + marker) == null:
			fail("Missing energy conversion marker: " + marker)
			return false
	if not energy.get_node("Label") is Label or energy.size != Vector2(128, 128):
		fail("Invalid energy label/root contract")
		return false
	energy.free()
	var rest = load("res://VolibearArt/scenes/volibear_rest.tscn").instantiate()
	root.add_child(rest)
	if not rest.get_node("ControlRoot") is Control:
		fail("Rest ControlRoot must support native flip")
		return false
	for marker in ["Hitbox", "ThoughtBubbleLeft", "ThoughtBubbleRight"]:
		if not rest.get_node_or_null("%" + marker) is Control:
			fail("Missing rest conversion marker: " + marker)
			return false
	if not rest.get_node("ControlRoot/AnimatedSprite2D").is_playing():
		fail("Rest relaxed animation is not playing")
		return false
	rest.free()
	var merchant = load("res://VolibearArt/scenes/volibear_merchant.tscn").instantiate()
	root.add_child(merchant)
	var actor = merchant.get_node("AnimatedSprite2D")
	if not actor.is_playing() or actor.animation != &"relaxed_loop":
		fail("Merchant relaxed animation is not playing")
		return false
	var social: SpriteFrames = actor.sprite_frames
	if social.get_frame_texture("idle", 0) != social.get_frame_texture("relaxed_loop", 0):
		fail("BaseLib merchant idle alias must resolve to approved relaxed clip")
		return false
	merchant.free()
	var trail = load("res://VolibearArt/scenes/volibear_trail.tscn").instantiate()
	root.add_child(trail)
	if not trail.get_node("Sprites") is Node2D or not trail.get_node("Sprites/Sparks") is CPUParticles2D:
		fail("Trail must expose native follower/fade particle contract")
		return false
	trail.free()
	var transition = load("res://VolibearArt/scenes/volibear_transition.tres") as ShaderMaterial
	if transition == null or transition.shader == null or transition.get_shader_parameter("threshold") != 0.0:
		fail("Transition must expose native threshold material contract")
		return false
	var portrait = transition.get_shader_parameter("portrait") as Texture2D
	if portrait == null or portrait.get_size() != Vector2(1920, 1080):
		fail("Transition must use approved character cutout")
		return false
	transition.set_shader_parameter("threshold", 1.0)
	if transition.get_shader_parameter("threshold") != 1.0:
		fail("Native transition threshold cannot be driven")
		return false
	transition.set_shader_parameter("threshold", 0.0)
	print("VOLIBEAR_UI_RESOURCE_PASS scenes=5 transition=1")
	return true
