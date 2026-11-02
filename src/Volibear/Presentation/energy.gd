extends Control
## Cosmetic child survives BaseLib's Control -> NEnergyCounter root conversion.
## The native Label is the only energy source: never write it or predict card payment.
const PULSE_SECONDS = 0.42
const CENTER = Vector2(64, 64)
const CHARGED_EMBLEM = preload("res://VolibearArt/ui/images/energy_master.png")
const EMPTY_EMBLEM = preload("res://VolibearArt/ui/images/big_energy_empty.png")
var _label: Label
var _core: Panel
var _emblem: TextureRect
var _charged_style: StyleBoxFlat
var _empty_style: StyleBoxFlat
var _tag_pattern = RegEx.new()
var _value_pattern = RegEx.new()
var _last_text = ""
var _has_value = false
var _energy_value = 0
var _phase = 0.0
var _pulse = 0.0
var _pulse_direction = 0

func _ready() -> void:
	_tag_pattern.compile("\\[[^\\]]*\\]")
	_value_pattern.compile("^\\s*(-?\\d+)\\s*(?:/\\s*\\d+)?\\s*$")
	_charged_style = _make_core_style(Color(0.035, 0.20, 0.34, 1.0), Color(0.32, 0.83, 1.0, 1.0), 3)
	_empty_style = _make_core_style(Color(0.035, 0.043, 0.055, 1.0), Color(0.17, 0.20, 0.23, 1.0), 2)
	_read_native_value()

func _make_core_style(fill: Color, edge: Color, width: int) -> StyleBoxFlat:
	var style = StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = edge
	style.set_border_width_all(width)
	style.set_corner_radius_all(42)
	style.anti_aliasing = true
	return style

func _bind_native_widgets() -> bool:
	# Find the counter after native node conversion, including any wrapper nodes.
	var ancestor = get_parent()
	while ancestor != null:
		var candidate = ancestor.get_node_or_null("Label") as Label
		if candidate != null:
			_label = candidate
			_core = ancestor.get_node_or_null("Layers/Core") as Panel
			_emblem = ancestor.get_node_or_null("Layers/Emblem") as TextureRect
			_last_text = ""
			return is_instance_valid(_core) and is_instance_valid(_emblem)
		ancestor = ancestor.get_parent()
	return false

func _read_native_value() -> void:
	if not is_instance_valid(_label) or not is_instance_valid(_core) or not is_instance_valid(_emblem):
		if not _bind_native_widgets():
			return
	if _label.text == _last_text:
		return
	_last_text = _label.text
	var match_value = _value_pattern.search(_tag_pattern.sub(_last_text, "", true))
	if match_value == null:
		return # Unknown/native placeholder text is not a zero-energy signal.
	var value = int(match_value.get_string(1))
	if _has_value and value != _energy_value:
		_pulse_direction = 1 if value > _energy_value else -1
		_pulse = PULSE_SECONDS if value > 0 else 0.0
	_energy_value = value
	_has_value = true
	var charged = _energy_value > 0
	_core.add_theme_stylebox_override("panel", _charged_style if charged else _empty_style)
	_emblem.texture = CHARGED_EMBLEM if charged else EMPTY_EMBLEM
	queue_redraw()

func _process(delta: float) -> void:
	_read_native_value()
	_pulse = maxf(0.0, _pulse - delta)
	if _has_value and _energy_value > 0:
		_phase = fmod(_phase + delta * 0.85, TAU)
	if is_visible_in_tree():
		queue_redraw()

func _draw() -> void:
	if not _has_value or _energy_value <= 0:
		# Empty: a cold metal rim, no charged arcs, halo, sparks or lingering pulse.
		draw_arc(CENTER, 52.0, 0.0, TAU, 64, Color(0.20, 0.23, 0.26, 1.0), 3.0, true)
		return
	var blue = Color(0.30, 0.77, 0.97, 0.95)
	var pale = Color(0.75, 0.94, 1.0, 1.0)
	draw_arc(CENTER, 53.0, 0.0, TAU, 64, Color(0.12, 0.55, 0.88, 0.22), 14.0, true)
	draw_arc(CENTER, 53.0, 0.0, TAU, 64, Color(0.22, 0.72, 1.0, 0.50), 7.0, true)
	draw_arc(CENTER, 51.0, 0.0, TAU, 64, blue, 3.0, true)
	for index in 3:
		var angle = _phase + index * TAU / 3.0
		draw_arc(CENTER, 52.0, angle, angle + 0.95, 18, pale, 3.2, true)
		# Electric branches stay on the rim, outside the numeric label.
		var points = PackedVector2Array()
		for step in 6:
			var radius = 50.0 + ([0.0, 3.0, -1.5, 3.5, -0.5, 0.0][step])
			points.append(CENTER + Vector2.from_angle(angle + step * 0.047) * radius)
		draw_polyline(points, pale, 2.0, true)
		draw_circle(CENTER + Vector2.from_angle(angle + 0.95) * 52.0, 2.0, pale, true, -1.0, true)
	if _pulse > 0.0:
		var strength = _pulse / PULSE_SECONDS
		var radius = 48.0 + (1.0 - strength) * 12.0 if _pulse_direction > 0 else 58.0 - (1.0 - strength) * 12.0
		draw_arc(CENTER, radius, 0.0, TAU, 64, Color(0.64, 0.94, 1.0, strength * 0.85), 2.0 + strength * 1.8, true)
