extends RefCounted
## Optional private sounds only replace validated, existing one-shot cue files.
## Missing config/files preserve the complete open manifest and its mixing rules.
const ROOT = "res://VolibearArt/audio/"
const CONFIG = ROOT + "profiles/runtime.json"
const PRIVATE_ROOT = "profiles/riot_en/"

static func resolve_manifest(base_manifest: Dictionary) -> Dictionary:
	var result = base_manifest.duplicate(true)
	result["active_profile"] = "open"
	if not FileAccess.file_exists(CONFIG):
		return result
	var parser = JSON.new()
	if parser.parse(FileAccess.get_file_as_string(CONFIG)) != OK:
		return result
	var config = parser.data
	if not config is Dictionary or config.get("schema_version") != 1 or config.get("profile") != "riot_en":
		return result
	if not config.get("overrides") is Array:
		return result
	var candidates: Dictionary = {}
	for row in config.overrides:
		if not row is Dictionary or not row.get("cue") is String:
			continue
		# Duplicate bindings are ambiguous: neither copy is selected.
		if candidates.has(row.cue):
			candidates[row.cue] = null
		else:
			candidates[row.cue] = row
	for cue in result.get("cues", []):
		var row = candidates.get(cue.id)
		if not row is Dictionary or cue.loop:
			continue
		var valid = true
		for key in row:
			if key not in ["cue", "file", "duration_seconds", "gain_db"]:
				valid = false
		var path = row.get("file", "")
		if not path is String or not path.begins_with(PRIVATE_ROOT) or not path.ends_with(".ogg"):
			continue
		var name = path.trim_prefix(PRIVATE_ROOT)
		if name.is_empty() or "/" in name or "\\" in name or ".." in name or ":" in name:
			continue
		var seconds = row.get("duration_seconds", 0)
		var gain = row.get("gain_db", 0)
		if not (seconds is float or seconds is int) or not (gain is float or gain is int):
			continue
		if not is_finite(float(seconds)) or not is_finite(float(gain)) or seconds <= 0 or seconds > 60 or gain < -40 or gain > 0:
			continue
		if not valid or not ResourceLoader.exists(ROOT + path, "AudioStreamOggVorbis"):
			continue
		# Existence alone is insufficient: a broken import or a mismatched clip
		# must keep this cue's complete open fallback instead of becoming silent.
		var stream = load(ROOT + path) as AudioStreamOggVorbis
		if stream == null or stream.get_length() <= 0 or absf(stream.get_length() - float(seconds)) > 0.02:
			continue
		if cue.id == "voice.death" and stream.get_length() > 3.0:
			continue
		cue["file"] = path
		cue["duration_seconds"] = seconds
		cue["gain_db"] = gain
		result["active_profile"] = "riot_en"
	return result
