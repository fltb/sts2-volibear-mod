extends AnimatedSprite2D
## Only presentation lifetime: no combat timing, damage or gameplay callbacks.
@export var return_animation: StringName = &"idle_loop"
var _contact_frames: Dictionary = {}
var _sequence_hits: Dictionary = {}
var _sequence_order: Array[String] = []
var _local_sequence := 0
var _current_sequence := "local:0"

func _ready() -> void:
	animation_finished.connect(_on_animation_finished)
	var path := "res://VolibearArt/animations/combat/manifest.json"
	if FileAccess.file_exists(path):
		var manifest = JSON.parse_string(FileAccess.get_file_as_string(path))
		for clip in manifest.clips:
			_contact_frames[StringName(clip.name)] = clip.contact_frames

func _is_death() -> bool:
	return animation in [&"die", &"Die", &"dead", &"Dead", &"death", &"Death", &"domain_die"]

func _last_hit(sequence: String) -> int:
	return int(_sequence_hits.get(sequence, -1))

func _record_hit(sequence: String, hit_index: int) -> void:
	if not _sequence_hits.has(sequence):
		_sequence_order.append(sequence)
		if _sequence_order.size() > 64:
			_sequence_hits.erase(_sequence_order.pop_front())
	_sequence_hits[sequence] = maxi(_last_hit(sequence), hit_index)

## Native settlement remains authoritative. A confirmed hit can advance a slow
## cosmetic windup to its authored contact, but never rewind/restart the attack.
## A confirmed card batch can bind its sequence without a native Attack/Cast
## trigger. Physical segments and lightning batches use separate sequence keys.
func combat_impact(hit_index: int = 0, sequence: String = "") -> void:
	if _is_death() or not _contact_frames.has(animation) or not is_playing():
		return
	if not sequence.is_empty():
		_current_sequence = sequence
	if hit_index < _last_hit(_current_sequence):
		return
	_record_hit(_current_sequence, hit_index)
	var contacts: Array = _contact_frames[animation]
	var contact := int(contacts[clampi(hit_index, 0, contacts.size() - 1)])
	if frame < contact:
		set_frame_and_progress(contact, 0.0)

func play_action(clip: StringName) -> bool:
	if _is_death() or not sprite_frames.has_animation(clip):
		return false
	_local_sequence += 1
	_current_sequence = "local:%d" % _local_sequence
	stop()
	play(clip)
	return true

## Only a new native attack/cast trigger requests this. A late actual segment can
## recover from idle, an incoming reaction or a nested play without replaying the
## paid action's long windup. New segments beyond the authored contacts reuse a
## short contact cycle only when that segment's native trigger actually arrives.
## The optional sequence belongs to one native CardPlay, including its replay;
## retaining its last index lets a nested play restore the outer action safely.
func resume_action(clip: StringName, hit_index: int = 0, sequence: String = "") -> bool:
	if _is_death() or not sprite_frames.has_animation(clip):
		return false
	if not sequence.is_empty():
		_current_sequence = sequence
	if hit_index <= _last_hit(_current_sequence):
		return true
	_record_hit(_current_sequence, hit_index)
	var contact := 0
	var authored := _contact_frames.has(clip)
	if authored:
		var contacts: Array = _contact_frames[clip]
		contact = int(contacts[clampi(hit_index, 0, contacts.size() - 1)])
	if animation == clip and is_playing():
		if authored and frame > contact:
			set_frame_and_progress(maxi(0, contact - 4), 0.0)
		return true
	stop()
	play(clip)
	if authored:
		set_frame_and_progress(maxi(0, contact - 4), 0.0)
	return true

func cancel_action() -> void:
	if not _is_death() and sprite_frames.has_animation(return_animation):
		play(return_animation)

func _on_animation_finished() -> void:
	# Death holds the final authored frame; it must never return to a living pose.
	if _is_death():
		return
	if sprite_frames.has_animation(return_animation):
		play(return_animation)
