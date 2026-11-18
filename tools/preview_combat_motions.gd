extends SceneTree
## Real Godot resource playback, without game assemblies or simulated combat.
const SCENES := "res://VolibearArt/scenes/"
var output := ""
var actors: Array = []
var clips: Array = []
var failures: Array[String] = []
var stage: SubViewport

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)

func label(text: String, point: Vector2, font_size: int = 18) -> void:
	var node := Label.new()
	node.text = text
	node.position = point
	node.add_theme_font_size_override("font_size", font_size)
	node.add_theme_color_override("font_color", Color("d8e8ed"))
	node.z_index = 10
	stage.add_child(node)

func capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var picture := stage.get_texture().get_image()
	check(picture != null and not picture.is_empty(), "No real render for " + name)
	if picture != null:
		check(picture.get_size() == Vector2i(1440, 1080), "Viewport dimensions changed during " + name)
		check(picture.save_png(output.path_join(name)) == OK, "Cannot save " + name)

func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		push_error("Expected an output directory")
		quit(1)
		return
	output = args[0]
	root.size = Vector2i(1440, 1080)
	# Capture a fixed render target, independent of desktop window positioning,
	# decorations, resizing, or the X server's drawable size.
	stage = SubViewport.new()
	stage.size = Vector2i(1440, 1080)
	stage.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(stage)
	var background := ColorRect.new()
	background.color = Color("111c25")
	background.size = stage.size
	stage.add_child(background)
	label("VOLIBEAR  /  14 ADDITIONAL JOINT-ANIMATED COMBAT ACTIONS", Vector2(24, 13), 24)
	label("Godot production actor + exact SpriteFrames  |  resource playback; not an in-game acceptance run", Vector2(24, 46), 15)
	var manifest = JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/animations/combat/manifest.json"))
	clips = manifest.clips
	for index in clips.size():
		var clip: Dictionary = clips[index]
		var x: int = 22 + (index % 4) * 357
		var y: int = 86 + (index / 4) * 246
		label(clip.name, Vector2(x + 5, y), 18)
		var scene = load(SCENES + "volibear_combat.tscn").instantiate()
		scene.position = Vector2(x + 165, y + 238)
		# The lunge's highest back spike reaches atlas y=38. At this scale its
		# complete silhouette stays below the 24-pixel label strip in every frame.
		scene.scale = Vector2.ONE * 0.51
		stage.add_child(scene)
		var actor: AnimatedSprite2D = scene.get_node("Visuals/AnimatedSprite2D")
		actors.append(actor)
		check(actor.call("play_action", StringName(clip.name)), "Cannot play " + clip.name)
		actor.pause()
		actor.set_frame_and_progress(int(clip.contact_frames[0]), 0)
	await capture("contact-sheet.png")
	# Capture the real viewport at every sampled production frame, including each
	# action's complete anticipation/contact/recovery. No external image rendering.
	for frame_index in 32:
		for index in actors.size():
			var actor: AnimatedSprite2D = actors[index]
			actor.play(StringName(clips[index].name))
			actor.pause()
			actor.set_frame_and_progress(mini(frame_index, int(clips[index].frame_count) - 1), 0)
		await capture("frames/%03d.png" % frame_index)
	# Exercise production state transitions using the actual animation clock.
	var sample: AnimatedSprite2D = actors[0]
	for index in actors.size():
		actors[index].play_action(StringName(clips[index].name))
	await create_timer(1.55).timeout
	for actor in actors:
		check(actor.animation == &"idle_loop" and actor.is_playing(), "Action did not settle into idle")
	sample.call("play_action", &"double_claw")
	sample.call("resume_action", &"double_claw", 0, "outer")
	sample.call("combat_impact", 0)
	check(sample.frame == 7, "First committed hit did not reach first authored contact")
	sample.call("combat_impact", 1)
	check(sample.frame == 15, "Second committed hit did not advance to the other claw")
	sample.call("combat_impact", 0)
	check(sample.frame == 15, "An older receipt rewound an action")
	sample.call("resume_action", &"double_claw", 1, "outer")
	check(sample.frame == 15, "Native trigger restarted a running authored action")
	sample.play(&"hurt")
	check(sample.call("resume_action", &"double_claw", 2, "outer"), "A real next attack could not resume after incoming hurt")
	check(sample.frame == 11, "Resumed second claw lost its short anticipation")
	sample.call("combat_impact", 2)
	check(sample.frame == 15, "Resumed claw did not reach the second contact")
	sample.set("return_animation", &"domain_weak_loop")
	sample.call("cancel_action")
	check(sample.animation == &"domain_weak_loop", "Cancellation lost the authoritative return state")
	check(sample.call("resume_action", &"claw_flurry", 2, "nested") and sample.frame == 14, "Idle did not resume at the third claw's short anticipation")
	sample.play(&"thunder_call")
	check(sample.call("resume_action", &"double_claw", 3, "outer") and sample.frame == 11, "Nested spell did not restore the continuing attack")
	# U07 has four/five actual hits although the authored stomp sequence has three
	# contacts. Only fresh native segment numbers may produce additional footfalls.
	sample.call("play_action", &"stomp_chain")
	sample.call("resume_action", &"stomp_chain", 2, "stomps")
	sample.call("combat_impact", 2)
	sample.set_frame_and_progress(28, 0)
	sample.call("resume_action", &"stomp_chain", 3, "stomps")
	check(sample.frame == 20, "Fourth actual stomp did not restart a short footfall")
	sample.call("combat_impact", 3)
	check(sample.frame == 24, "Fourth stomp did not reach contact")
	sample.set_frame_and_progress(28, 0)
	check(sample.call("resume_action", &"stomp_chain", 3, "stomps") and sample.frame == 28, "Duplicate fourth stomp replayed or lost ownership")
	check(sample.call("resume_action", &"stomp_chain", 1, "stomps") and sample.frame == 28, "Older stomp replayed or lost ownership")
	sample.call("resume_action", &"stomp_chain", 4, "stomps")
	check(sample.frame == 20, "Fifth actual stomp did not restart a short footfall")
	sample.call("combat_impact", 4)
	check(sample.frame == 24, "Fifth stomp did not reach contact")
	for name in [&"claw_flurry", &"chain_channel"]:
		sample.call("play_action", name)
		sample.call("combat_impact", 2)
		var last_contact := sample.frame
		sample.set_frame_and_progress(sample.sprite_frames.get_frame_count(name) - 2, 0)
		sample.call("resume_action", name, 3)
		check(sample.frame == last_contact - 4, "Fourth real segment did not animate for " + str(name))
		sample.call("combat_impact", 3)
		check(sample.frame == last_contact, "Fourth real segment missed contact for " + str(name))
	# A new native play of the same clip owns an independent monotonic sequence.
	sample.call("resume_action", &"stomp_chain", 0, "new-stomps")
	check(sample.frame == 4, "Next card inherited the preceding card's segment count")
	# Pure card lightning has a confirmed batch without a native Cast trigger.
	# Its first receipt must bind the new card before rejecting older segments.
	sample.call("play_action", &"chain_channel")
	sample.call("combat_impact", 2, "old-card:cast")
	check(sample.frame == 21, "Old card did not establish its third lightning contact")
	sample.play(&"thunder_call")
	sample.set_frame_and_progress(2, 0)
	sample.call("combat_impact", 0, "new-card:cast")
	check(sample.frame == 13, "New card's first lightning batch inherited the old card's last segment")
	# Binding a first batch may advance anticipation; it must preserve a clip
	# which has already passed that first contact instead of playing it backwards.
	sample.set_frame_and_progress(20, 0)
	sample.call("combat_impact", 0, "next-card:cast")
	check(sample.frame == 20, "First lightning batch rewound an already progressed action")
	# Mixed cards start physical and lightning counters independently at zero.
	sample.call("play_action", &"chain_channel")
	sample.call("combat_impact", 0, "mixed-card:attack")
	check(sample.frame == 9, "Mixed card's first physical segment missed contact")
	sample.call("combat_impact", 2, "mixed-card:attack")
	sample.set_frame_and_progress(0, 0)
	sample.call("combat_impact", 0, "mixed-card:cast")
	check(sample.frame == 9, "Mixed card's first lightning batch inherited physical segment numbering")
	sample.set_frame_and_progress(0, 0)
	sample.call("combat_impact", 0, "mixed-card:attack")
	check(sample.frame == 0, "Lightning batch erased the physical sequence's previous segment count")
	sample.call("combat_impact", 1, "mixed-card:cast")
	check(sample.frame == 15, "Lightning sequence did not continue independently after a physical receipt")
	# Existing one-argument callers continue the currently bound sequence.
	sample.call("combat_impact", 2)
	check(sample.frame == 21, "One-argument impact lost the current sequence")
	sample.play(&"hurt")
	var hurt_frame := sample.frame
	sample.call("combat_impact", 2)
	check(sample.animation == &"hurt" and sample.frame == hurt_frame, "Late impact overwrote an incoming reaction")
	sample.play(&"die")
	sample.call("combat_impact", 0)
	sample.call("cancel_action")
	check(not sample.call("play_action", &"backhand"), "A new action interrupted death")
	check(not sample.call("resume_action", &"double_claw", 1), "A late native attack resumed a dead actor")
	await create_timer(1.85).timeout
	check(sample.animation == &"die" and sample.frame == 39 and not sample.is_playing(), "Death failed to hold final frame")
	if failures.is_empty():
		print("VOLIBEAR_COMBAT_MOTION_PASS clips=14 frames=358 lifecycle=PASS rendered=33")
	quit(0 if failures.is_empty() else 1)
