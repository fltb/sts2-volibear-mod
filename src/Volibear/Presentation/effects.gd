extends Node2D
## Production presentation owner. Never computes rules or waits on gameplay.
const AudioProfile = preload("res://VolibearArt/scenes/audio_profile.gd")
const CombatVfx = preload("res://VolibearArt/scenes/combat_vfx.gd")
const FmodAudio = preload("res://VolibearArt/scenes/fmod_audio.gd")
const MAX_VISUALS = 64
const MAX_VOICES = 24
const DEDUP_WINDOW = 4096
const MAX_LEASE = 60.0
const COALESCED_ACCENTS = ["domain_echo", "storm_charge", "thunder_armor", "replay_echo", "beast", "absorb", "purify"]
# The approved ground atlases have a ~190px footprint; the native actor's feet
# span its 310px bounds. Enclose both feet without changing the raster or timing.
const OWNER_GROUND_SCALE = 1.8
var battle_id = ""
var owner_id = ""
var volume_provider: Callable
var _effects: Dictionary = {}
var _cues: Dictionary = {}
static var _resolved_audio: Dictionary = {}
var _mix: Dictionary = {}
var _frames: SpriteFrames
var _visuals: Dictionary = {}
var _combat_visuals: Dictionary = {}
var _voices: Dictionary = {}
var _loops: Dictionary = {}
var _voice_loops: Dictionary = {}
var _cooldowns: Dictionary = {}
var _seen: Dictionary = {}
var _seen_order: Array = []
var _streams: Dictionary = {}
var _fmod = null
static var _bank_loaded := false
# Space confirmed rapid hits on the presentation clock without delaying combat.
const CRACK_INTERVAL = 0.085
var _pending_cracks: Array[Dictionary] = []
var _next_crack_at := 0.0
var _next = 0
var _closing = false
var _refresh_elapsed = 0.0
var _last_reject := ""

func configure(battle: String, owner: String, gain_provider: Callable = Callable()) -> void:
	battle_id = battle
	owner_id = owner
	volume_provider = gain_provider

func _ready() -> void:
	_frames = load("res://VolibearArt/scenes/volibear_effect_frames.tres")
	var visual_manifest = JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/vfx/manifest.json"))
	for item in visual_manifest.effects:
		_effects[item.id] = item
	if _resolved_audio.is_empty():
		_resolved_audio = AudioProfile.resolve_manifest(JSON.parse_string(FileAccess.get_file_as_string("res://VolibearArt/audio/manifest.json")))
	var audio_manifest = _resolved_audio
	for item in audio_manifest.cues:
		_cues[item.id] = item
	_mix = audio_manifest.mix_rules
	_fmod = FmodAudio.new()
	if _fmod.available() and not _bank_loaded:
		_bank_loaded = _fmod.load_bank("res://VolibearArt/audio/fmod/Volibear.bank")

func _now() -> float:
	return Time.get_ticks_msec() / 1000.0

func _remember(key: String) -> bool:
	if _seen.has(key):
		return false
	_seen[key] = true
	_seen_order.append(key)
	if _seen_order.size() > DEDUP_WINDOW:
		_seen.erase(_seen_order.pop_front())
	return true

func _valid(node) -> bool:
	return is_instance_valid(node) and node is CanvasItem and node.is_inside_tree() and not node.is_queued_for_deletion()

func _point(node: CanvasItem, kind: String = "contact") -> Vector2:
	var marker = null
	if kind != "ground" and node is Node2D:
		marker = node.find_child("IntentPos" if kind == "status" else "CenterPos", true, false)
	if marker is CanvasItem:
		return marker.get_global_transform_with_canvas().origin
	var point = node.get_global_transform_with_canvas().origin
	if node is Control:
		var offset = node.size * 0.5
		if kind == "status":
			offset.y = 0
		elif kind == "ground":
			offset.y = node.size.y
		point = node.get_global_transform_with_canvas() * offset
	return point

func _anchor_bundle(effect: Dictionary, anchors: Dictionary) -> Dictionary:
	var owner = anchors.get("owner")
	var target = anchors.get("target")
	var source = anchors.get("source", owner)
	var card = anchors.get("card")
	var a = owner
	var b = owner
	var kind_a = "contact"
	var kind_b = "contact"
	var target_position = false
	match effect.anchor:
		"owner_ground": kind_a = "ground"
		"owner_status": kind_a = "status"
		"owner_front", "owner_contact": pass
		"owner_hand": a = anchors.get("hand")
		"owner_energy": a = anchors.get("energy")
		"target_contact", "resolved_enemy_group":
			b = target
			target_position = true
		"target_ground":
			b = target
			kind_b = "ground"
			target_position = true
		"target_status":
			b = target
			kind_b = "status"
			target_position = true
		"owner_to_target": b = target
		"source_to_target":
			a = source
			b = target
		"damaged_target_to_owner":
			a = target
			b = owner
		"owner_mouth_to_targets":
			a = anchors.get("mouth")
			b = target if _valid(target) else owner
		"selected_card", "owner_to_selected_card", "converted_attack_card", "converted_other_card", "exhausted_card", "played_card":
			b = card
			target_position = true
		"draw_pile_to_hand", "source_pile_to_hand":
			a = source
			b = card
			target_position = true
		"card_to_discard_pile":
			a = card
			b = target
			target_position = true
		"card_cost_anchor":
			b = anchors.get("cost")
			target_position = true
		_:
			return {}
	if not _valid(owner) or not _valid(a) or not _valid(b):
		return {}
	return {"a": a, "b": b, "kind_a": kind_a, "kind_b": kind_b, "target_position": target_position, "owner": owner}

func _position_visual(record: Dictionary) -> bool:
	if not is_instance_valid(record.node) or record.node.is_queued_for_deletion():
		return false
	var bundle = record.bundle
	if not _valid(bundle.owner) or not _valid(bundle.a) or not _valid(bundle.b):
		return false
	var inverse = get_global_transform_with_canvas().affine_inverse()
	var a: Vector2 = inverse * _point(bundle.a, bundle.kind_a)
	var b: Vector2 = inverse * _point(bundle.b, bundle.kind_b)
	var sprite: AnimatedSprite2D = record.node
	var effect: Dictionary = record.effect
	if effect.has("segment_anchors_px"):
		var start = Vector2(effect.segment_anchors_px.source[0], effect.segment_anchors_px.source[1])
		var finish = Vector2(effect.segment_anchors_px.target[0], effect.segment_anchors_px.target[1])
		var authored = finish - start
		var desired = b - a
		if authored.length_squared() < 0.0001 or desired.length_squared() < 0.0001:
			return false
		var u = authored.normalized()
		var v = Vector2(-u.y, u.x)
		var along = desired.normalized()
		var across = Vector2(-along.y, along.x)
		var stretch = desired.length() / authored.length()
		sprite.offset = -start
		sprite.transform = Transform2D(along * stretch * u.x + across * v.x, along * stretch * u.y + across * v.y, a)
	else:
		sprite.position = b if bundle.target_position else a
		if effect.anchor == "owner_ground":
			var owner_scale: Vector2 = (inverse * bundle.owner.get_global_transform_with_canvas()).get_scale()
			sprite.scale = Vector2(absf(owner_scale.x), absf(owner_scale.y)) * OWNER_GROUND_SCALE
	return true

func emit_effect(event_id: String, effect_id: String, anchors: Dictionary, target_id: String = "", persistent_key: String = "", lease_seconds: float = 10.0, sound: bool = true) -> bool:
	if _closing or event_id.is_empty() or not _effects.has(effect_id) or lease_seconds <= 0:
		return false
	var effect: Dictionary = _effects[effect_id]
	if effect.loop and persistent_key.is_empty():
		return false
	var bundle = _anchor_bundle(effect, anchors)
	if bundle.is_empty():
		return false
	if not _remember("v:" + event_id + ":" + effect_id + ":" + target_id):
		return false
	if effect.loop and _loops.has(persistent_key):
		var existing = _visuals[_loops[persistent_key]]
		if existing.effect.id != effect_id:
			return false
		existing.bundle = bundle
		return renew_loop(persistent_key, lease_seconds)
	if active_visuals() >= MAX_VISUALS:
		return false
	var sprite = AnimatedSprite2D.new()
	sprite.sprite_frames = _frames
	sprite.centered = false
	var pivot = effect.get("target_anchor_px", effect.pivot_px) if effect.anchor == "owner_to_selected_card" else effect.pivot_px
	sprite.offset = -Vector2(pivot[0], pivot[1])
	if effect.anchor == "owner_ground":
		sprite.scale = Vector2.ONE * OWNER_GROUND_SCALE
	sprite.z_index = effect.layer_z
	add_child(sprite)
	_next += 1
	var token = _next
	var duration = minf(lease_seconds, MAX_LEASE) if effect.loop else minf(lease_seconds, effect.duration_seconds + 0.2)
	var record = {"node": sprite, "effect": effect, "bundle": bundle, "expires": _now() + duration, "key": persistent_key if effect.loop else ""}
	if not _position_visual(record):
		sprite.queue_free()
		return false
	_visuals[token] = record
	if effect.loop:
		_loops[persistent_key] = token
	sprite.play(effect_id)
	if sound and effect.has("audio_cue"):
		play_sound(event_id, effect.audio_cue, persistent_key, lease_seconds)
	return true

## Committed combat geometry, independent of the legacy atlas/audio dispatcher.
## The stable event + target identity deduplicates observations, while hit_index
## controls stroke direction/offset only. It never means an extra damage event.
func emit_combat(event_id: String, style: String, anchors: Dictionary, target_id: String = "", options: Dictionary = {}) -> bool:
	if _closing or event_id.is_empty() or not CombatVfx.supports(style):
		return false
	if anchors.has("target") and target_id.is_empty():
		return false
	var owner = anchors.get("owner")
	var target = anchors.get("target", anchors.get("card", owner))
	var source = anchors.get("source", anchors.get("hand", owner))
	if not _valid(owner) or not _valid(target) or not _valid(source):
		return false
	if not _remember("combat:" + event_id + ":" + style + ":" + target_id):
		return false
	# Repeated passive receipts refresh one short accent instead of stacking
	# shields/halos over the actor's head. Actual attack strokes and thunder paths
	# remain independent per hit. This changes no receipt or gameplay count.
	if style in COALESCED_ACCENTS:
		for record in _combat_visuals.values():
			if record.node.style == style and record.owner == owner and record.target == target:
				record.node.configure(style, event_id, options)
				record.node.age = 0.0
				record.source = source
				return _position_combat(record)
	if active_visuals() >= MAX_VISUALS:
		return false
	var visual = CombatVfx.new()
	visual.configure(style, event_id, options)
	add_child(visual)
	_next += 1
	var record = {"node": visual, "owner": owner, "source": source, "target": target}
	if not _position_combat(record):
		visual.queue_free()
		return false
	_combat_visuals[_next] = record
	return true

func _position_combat(record: Dictionary) -> bool:
	if not _valid(record.node) or not _valid(record.owner) or not _valid(record.source) or not _valid(record.target):
		return false
	var inverse := get_global_transform_with_canvas().affine_inverse()
	var target: CanvasItem = record.target
	var center: Vector2 = inverse * _point(target)
	var ground: Vector2 = inverse * _point(target, "ground")
	var size := Vector2(120, 160)
	# Bounds is the native visual contract. Do not infer species, armor or flying
	# rules from the model name, a sprite texture, or the last selected enemy.
	var bounds = target if target is Control else target.find_child("Bounds", true, false)
	if bounds is Control and bounds.size.x > 0 and bounds.size.y > 0:
		var local: Transform2D = inverse * bounds.get_global_transform_with_canvas()
		var top_left: Vector2 = local * Vector2.ZERO
		var top_right: Vector2 = local * Vector2(bounds.size.x, 0)
		var bottom_left: Vector2 = local * Vector2(0, bounds.size.y)
		size = Vector2(top_left.distance_to(top_right), top_left.distance_to(bottom_left))
		# CenterPos remains the authoritative contact anchor, including a flyer.
		# The ground stroke belongs at the visual's own feet/bottom, never the HUD.
		ground = local * Vector2(bounds.size.x * 0.5, bounds.size.y)
		if target is Control:
			center = local * (bounds.size * 0.5)
	record.node.set_endpoints(inverse * _point(record.source), center, ground, size)
	return true

func _stop_combat(token) -> void:
	if not _combat_visuals.has(token):
		return
	var record = _combat_visuals[token]
	_combat_visuals.erase(token)
	if is_instance_valid(record.node):
		record.node.queue_free()

func has_private_sound(cue_id: String) -> bool:
	return _cues.has(cue_id) and str(_cues[cue_id].file).begins_with("profiles/riot_en/")

func last_reject() -> String:
	return _last_reject

func play_sound(event_id: String, cue_id: String, persistent_key: String = "", lease_seconds: float = 10.0, allow_disabled: bool = false) -> bool:
	_last_reject = ""
	if _closing or event_id.is_empty() or not _cues.has(cue_id) or lease_seconds <= 0:
		_last_reject = "closing-or-missing-cue:%s:%s" % [event_id, cue_id]
		return false
	var cue: Dictionary = _cues[cue_id]
	if not cue.default_enabled and not allow_disabled:
		_last_reject = "cue-disabled:" + cue_id
		return false
	if cue.loop and persistent_key.is_empty():
		_last_reject = "loop-without-key:" + cue_id
		return false
	if not _remember("a:" + event_id + ":" + cue_id):
		_last_reject = "duplicate:" + cue_id
		return false
	if cue.loop and _voice_loops.has(persistent_key):
		if _voices[_voice_loops[persistent_key]].cue.id != cue_id:
			_last_reject = "loop-key-conflict:" + cue_id
			return false
		return renew_loop(persistent_key, lease_seconds)
	var now = _now()
	if cue_id == "sfx.lightning_chain" and (now < _next_crack_at or not _pending_cracks.is_empty()):
		_pending_cracks.append(cue)
		return true
	return _start_sound(cue, persistent_key, lease_seconds)

func _start_sound(cue: Dictionary, persistent_key: String, lease_seconds: float) -> bool:
	var cue_id: String = cue.id
	var now = _now()
	if now - float(_cooldowns.get(cue_id, -1000.0)) < cue.cooldown_ms / 1000.0:
		_last_reject = "cooldown:" + cue_id
		return false
	var same_cue: Array = []
	for token in _voices:
		if _voices[token].cue.id == cue_id or (cue.bus == "Voice" and _voices[token].cue.bus == "Voice"):
			same_cue.append(token)
	var limit = 1 if cue.bus == "Voice" else int(cue.max_voices)
	while same_cue.size() >= limit:
		_stop_voice(same_cue.pop_front())
	if _voices.size() >= MAX_VOICES:
		_last_reject = "voice-limit"
		return false
	var duration = minf(lease_seconds, MAX_LEASE) if cue.loop else minf(lease_seconds, float(cue.duration_seconds) + 0.2)
	var player = null
	var sound = null
	if _fmod != null and _fmod.available() and _bank_loaded:
		var event_path: String
		if str(cue.file).begins_with("profiles/riot_en/"):
			event_path = "event:/volibear/riot/" + str(cue.id)
		else:
			event_path = "event:/volibear/open/" + str(cue.asset_id)
		sound = _fmod.create(event_path)
	if sound != null:
		_next += 1
		_voices[_next] = {"sound": sound, "cue": cue, "expires": now + duration, "key": persistent_key if cue.loop else "", "fade_end": 0.0}
	else:
		if not _streams.has(cue.file):
			_streams[cue.file] = load("res://VolibearArt/audio/" + cue.file)
		var source_stream = _streams[cue.file] as AudioStreamOggVorbis
		if source_stream == null:
			_last_reject = "missing-stream:" + str(cue.file)
			return false
		var stream = source_stream.duplicate() as AudioStreamOggVorbis
		if stream == null:
			_last_reject = "duplicate-stream:" + str(cue.file)
			return false
		stream.loop = cue.loop
		player = AudioStreamPlayer.new()
		player.stream = stream
		player.bus = "Master"
		add_child(player)
		_next += 1
		_voices[_next] = {"node": player, "cue": cue, "expires": now + duration, "key": persistent_key if cue.loop else "", "fade_end": 0.0}
	if cue.loop:
		_voice_loops[persistent_key] = _next
	_cooldowns[cue_id] = now
	_refresh_volumes()
	if player != null:
		player.play()
	elif sound != null:
		_fmod.start(sound)
	if cue_id in ["sfx.lightning_strike", "sfx.lightning_chain"]:
		_next_crack_at = now + CRACK_INTERVAL
	return true

func _refresh_volumes() -> void:
	var gains = volume_provider.call() if volume_provider.is_valid() else {"Sfx": 1.0, "Voice": 1.0, "Ambience": 1.0}
	for record in _voices.values():
		var category = str(record.cue.bus)
		var db = float(record.cue.gain_db) + float(_mix.get(category.to_lower() + "_bus", 0.0))
		var gain = clampf(float(gains.get(category, 0.0)), 0.0, 1.0) * db_to_linear(db)
		if record.fade_end > 0:
			gain *= clampf((record.fade_end - _now()) / 0.14, 0.0, 1.0)
		if record.has("sound"):
			_fmod.set_volume(record.sound, gain)
		else:
			record.node.volume_linear = gain

func renew_loop(key: String, lease_seconds: float = 10.0) -> bool:
	if lease_seconds <= 0 or _closing:
		return false
	var found = false
	var expires = _now() + minf(lease_seconds, MAX_LEASE)
	if _loops.has(key):
		_visuals[_loops[key]].expires = expires
		found = true
	if _voice_loops.has(key):
		_voices[_voice_loops[key]].expires = expires
		found = true
	return found

func _stop_voice(token) -> void:
	if not _voices.has(token):
		return
	var record = _voices[token]
	_voices.erase(token)
	if not str(record.key).is_empty() and _voice_loops.get(record.key) == token:
		_voice_loops.erase(record.key)
	if record.has("sound"):
		_fmod.stop(record.sound)
	elif is_instance_valid(record.node):
		record.node.stop()
		record.node.stream = null
		record.node.queue_free()

func _stop_voice_key(key: String, fade: bool) -> void:
	if not _voice_loops.has(key):
		return
	var token = _voice_loops[key]
	_voice_loops.erase(key)
	if fade:
		_voices[token].fade_end = _now() + 0.14
		_voices[token].expires = _now() + 0.14
	else:
		_stop_voice(token)

func _stop_visual(token, fade_audio: bool = false) -> void:
	if not _visuals.has(token):
		return
	var record = _visuals[token]
	_visuals.erase(token)
	if not str(record.key).is_empty():
		_loops.erase(record.key)
		_stop_voice_key(record.key, fade_audio)
	if is_instance_valid(record.node):
		record.node.stop()
		record.node.queue_free()

func stop_loop(key: String, fade_audio: bool = true) -> void:
	if _loops.has(key):
		_stop_visual(_loops[key], fade_audio)
	else:
		_stop_voice_key(key, fade_audio)

## Combat can enter IsEnding immediately after its final damage receipt. Remove
## persistent fields at that boundary while allowing the confirmed strike and
## its already-started sound to finish their own bounded lifetime. Room teardown
## and owner death still call stop_all(), which clears every transient as well.
func stop_persistent() -> void:
	for key in _loops.keys():
		stop_loop(key, false)
	# A fading loop has already relinquished its lookup key. Stop by the actual
	# voice's authored loop flag as well, so no detached loop survives ending.
	for token in _voices.keys():
		if _voices[token].cue.loop:
			_stop_voice(token)

func stop_all() -> void:
	_pending_cracks.clear()
	_next_crack_at = 0.0
	for token in _visuals.keys():
		_stop_visual(token)
	for token in _combat_visuals.keys():
		_stop_combat(token)
	for token in _voices.keys():
		_stop_voice(token)
	_loops.clear()
	_voice_loops.clear()

func active_visuals() -> int:
	return _visuals.size() + _combat_visuals.size()

func active_voices() -> int:
	return _voices.size()

func _process(delta: float) -> void:
	var now = _now()
	if not _pending_cracks.is_empty() and now >= _next_crack_at:
		_start_sound(_pending_cracks.pop_front(), "", 10.0)
	for token in _visuals.keys():
		var record = _visuals[token]
		if now >= record.expires or not _position_visual(record) or (not record.effect.loop and not record.node.is_playing()):
			_stop_visual(token)
	for token in _combat_visuals.keys():
		var record = _combat_visuals[token]
		if not _position_combat(record) or not record.node.advance(delta):
			_stop_combat(token)
	for token in _voices.keys():
		var record = _voices[token]
		if now >= record.expires:
			_stop_voice(token)
		elif record.has("sound"):
			if not _fmod.playing(record.sound):
				if record.cue.loop:
					var loop_path := ("event:/volibear/riot/" + str(record.cue.id)) if str(record.cue.file).begins_with("profiles/riot_en/") else ("event:/volibear/open/" + str(record.cue.asset_id))
					var again = _fmod.create(loop_path)
					if again != null:
						record.sound = again
						_refresh_volumes()
						_fmod.start(again)
				else:
					_stop_voice(token)
		elif not is_instance_valid(record.node) or not record.node.playing:
			_stop_voice(token)
	_refresh_elapsed += delta
	if _refresh_elapsed >= 0.025:
		_refresh_elapsed = 0.0
		_refresh_volumes()

func _exit_tree() -> void:
	_closing = true
	stop_all()
	_seen.clear()
	_seen_order.clear()
	_streams.clear()
