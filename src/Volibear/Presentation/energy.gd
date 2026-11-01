extends Control
## Cosmetic child survives BaseLib's Control -> NEnergyCounter root conversion.
## The native Label is the only energy source: never write it or predict card payment.
const PULSE_SECONDS = 0.42
const CENTER = Vector2(64, 64)
var _label: Label
var _tag_pattern = RegEx.new()
var _value_pattern = RegEx.new()
var _last_text = ""
var _has_value = false
var _energy_value = 0
var _phase = 0.0
var _pulse = 0.0
var _pulse_direction = 0

func _ready() -> void:
	# Root and Label may have been replaced by native types before entering the tree.
	_label = get_node_or_null("../../../Label") as Label
	_tag_pattern.compile("\\[[^\\]]*\\]")
	_value_pattern.compile("^\\s*(-?\\d+)\\s*(?:/\\s*\\d+)?\\s*$")
	_read_native_value()

func _read_native_value() -> void:
	if not is_instance_valid(_label) or _label.text == _last_text:
		return
	_last_text = _label.text
	var match_value = _value_pattern.search(_tag_pattern.sub(_last_text, "", true))
	if match_value == null:
		return # Unknown/native placeholder text is not a zero-energy signal.
	var value = int(match_value.get_string(1))
	if _has_value and value != _energy_value:
		_pulse_direction = 1 if value > _energy_value else -1
		_pulse = PULSE_SECONDS
	_energy_value = value
	_has_value = true

func _process(delta: float) -> void:
	_read_native_value()
	_pulse = maxf(0.0, _pulse - delta)
	# No tween or repeating timer can survive removal or become stuck after depletion.
	_phase = fmod(_phase + delta * (0.18 if _has_value and _energy_value <= 0 else 0.85), TAU)
	if is_visible_in_tree():
		queue_redraw()

func _draw() -> void:
	var depleted = _has_value and _energy_value <= 0
	var brightness = 0.20 if depleted else 1.0
	var blue = Color(0.30, 0.77, 0.97, 0.72 * brightness)
	var pale = Color(0.75, 0.94, 1.0, 0.90 * brightness)
	draw_arc(CENTER, 51.0, 0.0, TAU, 64, Color(0.14, 0.32, 0.40, 0.8), 2.0, true)
	draw_arc(CENTER, 55.0, 0.0, TAU, 64, Color(0.22, 0.52, 0.65, 0.13 * brightness), 5.0, true)
	for index in 3:
		var angle = _phase + index * TAU / 3.0
		draw_arc(CENTER, 51.0, angle, angle + 0.85, 18, blue, 2.5, true)
		if not depleted:
			# Short moving electric branches stay on the rim, outside the numeric label.
			var points = PackedVector2Array()
			for step in 6:
				var radius = 50.0 + ([0.0, 3.0, -1.5, 3.5, -0.5, 0.0][step])
				points.append(CENTER + Vector2.from_angle(angle + step * 0.047) * radius)
			draw_polyline(points, pale, 1.4, true)
			draw_circle(CENTER + Vector2.from_angle(angle + 0.85) * 51.0, 1.8, pale, true, -1.0, true)
	if _pulse > 0.0:
		var strength = _pulse / PULSE_SECONDS
		var radius = 48.0 + (1.0 - strength) * 12.0 if _pulse_direction > 0 else 58.0 - (1.0 - strength) * 12.0
		var color = Color(0.64, 0.94, 1.0, strength * 0.85) if _pulse_direction > 0 else Color(0.46, 0.70, 0.85, strength * 0.75)
		draw_arc(CENTER, radius, 0.0, TAU, 64, color, 2.0 + strength * 1.8, true)
