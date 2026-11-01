extends SceneTree
## Standalone Godot resource/playback verification, never a native game claim.
var failed = false

func fail(message: String) -> void:
	failed = true
	push_error(message)

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var args = OS.get_cmdline_user_args()
	if args.size() != 2 or not ProjectSettings.load_resource_pack(args[0]):
		fail("Expected candidate PCK and independent profile expectations")
		quit(1)
		return
	var expected = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var base = JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/audio/manifest.json"))
	var resolver = load("res://VolibearArt/scenes/audio_profile.gd")
	var resolved = resolver.resolve_manifest(base)
	if resolved.active_profile != expected.profile or resolved.cues.size() != 54:
		fail("Packed audio profile identity/cue count differs from the selected build")
	var overrides: Dictionary = {}
	for row in expected.overrides:
		overrides[row.cue] = row
	var cues: Dictionary = {}
	var fallback_count = 0
	for index in range(base.cues.size()):
		var cue = resolved.cues[index]
		cues[cue.id] = cue
		if not overrides.has(cue.id):
			fallback_count += 1
			if cue != base.cues[index]:
				fail("Unselected cue changed instead of preserving open fallback: " + cue.id)
		else:
			var row = overrides[cue.id]
			if cue.file != row.file or abs(cue.duration_seconds - row.duration_seconds) > 0.001:
				fail("Selected private cue is not the independently expected asset: " + cue.id)
	if overrides.size() != expected.overrides.size():
		fail("Duplicate independent audio expectations")
	var scene = load("res://VolibearArt/scenes/volibear_effects.tscn")
	var fx = scene.instantiate()
	fx.configure("audio_profile_check", "standalone")
	root.add_child(fx)
	await process_frame
	var decoded = 0
	var played = 0
	for cue_id in overrides:
		if not cues.has(cue_id):
			fail("Expected cue missing from full open fallback manifest")
			continue
		var row = overrides[cue_id]
		var stream = load("res://VolibearArt/audio/" + row.file) as AudioStreamOggVorbis
		if stream == null or abs(stream.get_length() - row.duration_seconds) > 0.01:
			fail("Private native stream did not load with expected length: " + cue_id)
			continue
		var lease = 3.0 if cue_id == "voice.death" else 10.0
		if stream.get_length() > lease:
			fail("Private voice would exceed its existing presentation lease: " + cue_id)
		var playback = stream.instantiate_playback()
		playback.start()
		var maximum = 0.0
		var frames = int(ceil(stream.get_length() * 48000.0)) + 4096
		while frames > 0:
			var samples = playback.mix_audio(1.0, mini(frames, 4096))
			for sample in samples:
				if not is_finite(sample.x) or not is_finite(sample.y):
					fail("Nonfinite native decode: " + cue_id)
				maximum = maxf(maximum, maxf(absf(sample.x), absf(sample.y)))
			frames -= 4096
		playback.stop()
		if maximum < 0.00001 or maximum >= 0.89:
			fail("Silent/clipped native private sound decode: " + cue_id)
		decoded += 1
		fx.stop_all()
		if not fx.play_sound("audio_profile:" + cue_id, cue_id, "", lease):
			fail("Production effects owner did not start private cue: " + cue_id)
		else:
			await create_timer(0.06).timeout
			if fx.active_voices() != 1 or not fx.get("_voices").values()[0].node.playing:
				fail("Production private playback did not stay active: " + cue_id)
			else:
				played += 1
		fx.stop_all()
	fx.queue_free()
	await process_frame
	await process_frame
	await create_timer(0.1).timeout
	if not failed:
		print("VOLIBEAR_AUDIO_PROFILE_PASS profile=", expected.profile, " overrides=", overrides.size(),
			" native_decoded=", decoded, " started=", played, " open_fallback=", fallback_count,
			" gameplay=NOT_RUN listening=NOT_REVIEWED")
	quit(1 if failed else 0)
