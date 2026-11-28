extends RefCounted
## Bank-backed FMOD playback: the game's own mixer plays our events, so the
## volume sliders, buses and ducking apply natively. No second audio engine.

var _server = null
var _bank := false
var _guids: Dictionary = {}

func _init() -> void:
	if Engine.has_singleton("FmodServer"):
		_server = Engine.get_singleton("FmodServer")

func available() -> bool:
	return _server != null

func load_bank(path: String) -> bool:
	if _server == null:
		return false
	_server.call("load_bank", path, 0)
	_bank = true
	var text = FileAccess.get_file_as_string("res://VolibearArt/audio/fmod/GUIDs.txt")
	for line in text.split("\n"):
		var trimmed = line.strip_edges()
		var space = trimmed.find(" ")
		if space > 0:
			_guids[trimmed.substr(space + 1).strip_edges()] = trimmed.substr(0, space).strip_edges()
	return _bank

func create(event_path: String) -> Object:
	if _server == null or not _bank:
		return null
	var guid = _guids.get(event_path, "")
	var event = null
	if guid != "":
		event = _server.call("create_event_instance_with_guid", guid)
	if event == null:
		event = _server.call("create_event_instance", event_path)
	if event == null:
		push_warning("[Volibear] FMOD event missing: " + event_path)
	return event

func start(event: Object) -> void:
	if event != null:
		event.call("start")

func set_volume(event: Object, gain: float) -> void:
	if event != null:
		event.set("volume", gain)

func playing(event: Object) -> bool:
	if event == null:
		return false
	return bool(event.get("is_playing"))

func stop(event: Object) -> void:
	if event != null:
		event.call("stop")
