extends Node2D
## Geometry for a confirmed hit or synergy, drawn in the owning effects layer.
## No scene-tree timers, random generator, game state, sound, or model callbacks.
## CenterPos/Bounds are supplied afresh by effects.gd, so contact follows the real
## visible target (including small, large, mirrored and airborne visuals).
const DURATIONS = {
	"claw": 0.30, "cross_claw": 0.38, "rake": 0.34, "sweep": 0.40,
	"uppercut": 0.38, "lunge": 0.32, "slam": 0.46, "stomp": 0.40,
	"bite": 0.36, "bite_tear": 0.43, "feral_claw": 0.38,
	"bolt": 0.34, "chain": 0.24, "spear": 0.36, "storm": 0.58,
	"ground_thunder": 0.48, "fork": 0.43, "eruption": 0.62,
	"guard": 0.34, "armor": 0.43, "retaliation": 0.40,
	"domain_echo": 0.40, "storm_charge": 0.43, "thunder_armor": 0.45,
	"replay_echo": 0.42, "lifesteal": 0.55, "beast": 0.50,
	"absorb": 0.42, "purify": 0.45,
}
const INK = Color(0.035, 0.12, 0.18)
const BLUE = Color(0.13, 0.55, 0.78)
const ICE = Color(0.46, 0.86, 0.94)
const WHITE = Color(0.90, 0.98, 0.96)
const STONE = Color(0.48, 0.65, 0.68)

var style := "claw"
var hit_index := 0
var blocked := false
var intensity := 1.0
var age := 0.0
var duration := 0.3
var source_point := Vector2.ZERO
var contact_point := Vector2.ZERO
var ground_point := Vector2.ZERO
var target_size := Vector2(120, 160)
var _seed := 0

static func supports(style_id: String) -> bool:
	return DURATIONS.has(style_id)

func configure(style_id: String, event_id: String, options: Dictionary) -> void:
	style = style_id
	hit_index = maxi(0, int(options.get("hit_index", 0)))
	blocked = bool(options.get("blocked", false))
	intensity = clampf(float(options.get("intensity", 1.0)), 0.45, 1.8)
	duration = float(DURATIONS[style])
	_seed = int(event_id.hash()) % 997
	z_index = 24

func set_endpoints(source: Vector2, contact: Vector2, ground: Vector2, bounds_size: Vector2) -> void:
	source_point = source
	contact_point = contact
	ground_point = ground
	target_size = bounds_size
	queue_redraw()

func advance(delta: float) -> bool:
	age += maxf(delta, 0.0)
	queue_redraw()
	return age < duration

## Resource previews seek the same renderer; this never advances combat.
func seek_fraction(fraction: float) -> void:
	age = clampf(fraction, 0.0, 1.0) * duration
	queue_redraw()

func _radius() -> float:
	return clampf((target_size.x * 0.32 + target_size.y * 0.10), 26.0, 100.0) * lerpf(0.9, 1.1, intensity / 1.8)

func _alpha(t: float) -> float:
	return minf(t * 12.0 + 0.20, 1.0) * pow(maxf(1.0 - t, 0.0), 0.65)

func _tint(color: Color, alpha: float) -> Color:
	return Color(color.r, color.g, color.b, clampf(alpha, 0.0, 1.0))

func _stroke(points: PackedVector2Array, width: float, alpha: float, core: Color = WHITE) -> void:
	if points.size() < 2 or alpha <= 0.001:
		return
	draw_polyline(points, _tint(INK, alpha * 0.82), width + 5.0, true)
	draw_polyline(points, _tint(BLUE, alpha), width + 2.0, true)
	draw_polyline(points, _tint(core, alpha), maxf(1.0, width), true)

func _arc(center: Vector2, radius: Vector2, start: float, finish: float, rotation_angle: float = 0.0) -> PackedVector2Array:
	var points := PackedVector2Array()
	for i in 25:
		var angle := lerpf(start, finish, i / 24.0)
		points.append(center + (Vector2(cos(angle), sin(angle)) * radius).rotated(rotation_angle))
	return points

func _slash(center: Vector2, radius: float, rotation_angle: float, alpha: float, thickness: float = 5.0, spread: float = 1.0) -> void:
	# Tapered hooked polygons retain a solid readable silhouette on light scenes.
	for finger in 3:
		var offset := Vector2((finger - 1) * radius * 0.22 * spread, 0).rotated(rotation_angle)
		var spine := _arc(center + offset, Vector2(radius * 0.46, radius), -1.62, 1.22, rotation_angle)
		var polygon := PackedVector2Array()
		for i in spine.size():
			var tangent: Vector2 = spine[mini(i + 1, spine.size() - 1)] - spine[maxi(i - 1, 0)]
			var taper := sin(PI * i / (spine.size() - 1))
			polygon.append(spine[i] + tangent.orthogonal().normalized() * thickness * taper)
		for i in range(spine.size() - 1, -1, -1):
			var tangent: Vector2 = spine[mini(i + 1, spine.size() - 1)] - spine[maxi(i - 1, 0)]
			var taper := sin(PI * i / (spine.size() - 1))
			polygon.append(spine[i] - tangent.orthogonal().normalized() * thickness * 0.35 * taper)
		draw_polyline(spine, _tint(INK, alpha * 0.85), thickness * 2.6, true)
		draw_colored_polygon(polygon, _tint(ICE, alpha))
		draw_polyline(spine, _tint(WHITE, alpha), 1.7, true)

func _bolt(start: Vector2, finish: Vector2, width: float, alpha: float, branch: int = 0) -> void:
	var delta := finish - start
	if delta.length_squared() < 0.01:
		return
	var cross := delta.normalized().orthogonal()
	var points := PackedVector2Array([start])
	var bends := clampi(int(delta.length() / 28.0), 5, 16)
	for i in range(1, bends):
		var side := sin(float(i * 71 + _seed * 3 + branch * 29 + hit_index * 11))
		var envelope := sin(PI * i / bends)
		points.append(start + delta * (float(i) / bends) + cross * side * minf(24.0, delta.length() * 0.12) * envelope)
	points.append(finish)
	_stroke(points, width, alpha)
	if bends > 7:
		var root_point: Vector2 = points[int(bends * 0.55)]
		var twig := root_point + delta * 0.11 + cross * (24.0 if branch % 2 == 0 else -24.0)
		_stroke(PackedVector2Array([root_point, twig - delta * 0.03, twig]), maxf(1.0, width * 0.48), alpha * 0.65, ICE)

func _burst(center: Vector2, radius: float, t: float, alpha: float, count: int = 7) -> void:
	for i in count:
		var angle := TAU * i / count + _seed * 0.013
		var direction := Vector2.from_angle(angle)
		var inner := radius * (0.18 + t * 0.48)
		var outer := radius * (0.46 + t * 0.96) * (1.0 if i % 2 == 0 else 0.72)
		var points := PackedVector2Array([center + direction * inner, center + direction * outer])
		_stroke(points, 1.6 + (1.0 - t) * 1.4, alpha, ICE)

func _chips(center: Vector2, radius: float, t: float, alpha: float, count: int = 8) -> void:
	for i in count:
		var direction := Vector2.from_angle(TAU * i / count + _seed * 0.017)
		var p := center + direction * radius * (0.36 + t * 0.9)
		var side := direction.orthogonal()
		var length := lerpf(6.0, 2.0, t)
		var chip := PackedVector2Array([p - direction * length, p + side * 2.5, p + direction * length, p - side * 2.5])
		draw_colored_polygon(chip, _tint(WHITE if blocked else STONE, alpha))

func _ground_ring(center: Vector2, radius: float, t: float, alpha: float, spiked: bool = false) -> void:
	var growth := radius * (0.35 + t * 0.85)
	_stroke(_arc(center, Vector2(growth, growth * 0.29), 0.0, TAU), 2.3 * (1.0 - t) + 1.0, alpha, ICE)
	if spiked:
		for i in 7:
			var direction := Vector2.from_angle(PI * (0.12 + 0.76 * i / 6.0))
			var base := center + Vector2(direction.x * radius * 0.52, -direction.y * radius * 0.12)
			var tip := base + Vector2(direction.x, -direction.y * 1.8) * radius * (0.35 + 0.28 * sin(PI * t))
			var shard := PackedVector2Array([base - Vector2(4, 0), tip, base + Vector2(5, 0)])
			draw_colored_polygon(shard, _tint(BLUE, alpha * 0.5))
			_stroke(PackedVector2Array([base, tip]), 1.5, alpha * 0.8)

func _shield(center: Vector2, radius: float, t: float, alpha: float, plates: bool = false) -> void:
	var direction := -1.0 if source_point.x > contact_point.x else 1.0
	if plates:
		for i in 3:
			var point := center + Vector2(direction * radius * 0.16 * i, (i - 1) * radius * 0.50)
			var polygon := PackedVector2Array()
			for corner in 6:
				polygon.append(point + Vector2.from_angle(TAU * corner / 6.0 + PI / 6.0) * radius * 0.36)
			draw_colored_polygon(polygon, _tint(BLUE, alpha * 0.20))
			polygon.append(polygon[0])
			_stroke(polygon, 2.0, alpha)
	else:
		_stroke(_arc(center, Vector2(radius * (0.58 + t * 0.1), radius), -1.38, 1.38, PI if direction < 0 else 0.0), 4.2, alpha)
		_stroke(_arc(center, Vector2(radius * 0.72, radius * 1.13), -1.2, 1.2, PI if direction < 0 else 0.0), 1.2, alpha * 0.48, ICE)

func _fangs(center: Vector2, radius: float, t: float, alpha: float, tearing: bool) -> void:
	var closing := sin(minf(t / 0.36, 1.0) * PI * 0.5)
	var gap := radius * lerpf(0.9, 0.22, closing)
	var tear := maxf(0.0, (t - 0.30) / 0.70) * radius * 0.55 if tearing else 0.0
	for jaw in [-1, 1]:
		var c := center + Vector2(tear * jaw, gap * jaw)
		_stroke(_arc(c, Vector2(radius * 0.78, radius * 0.35), 0.05, PI - 0.05, 0 if jaw < 0 else PI), 2.0, alpha, ICE)
		for i in 3:
			var base := c + Vector2((i - 1) * radius * 0.48, 0)
			var length := radius * (0.47 if i != 1 else 0.27)
			var tooth := PackedVector2Array([base - Vector2(radius * 0.09, 0), base + Vector2(radius * 0.09, 0), base - Vector2(0, jaw * length)])
			draw_colored_polygon(tooth, _tint(INK, alpha))
			_stroke(PackedVector2Array([tooth[0], tooth[2], tooth[1]]), 1.6, alpha)
	if tearing:
		_slash(center + Vector2(tear, 0), radius * 0.75, -0.55, alpha * 0.8, 4.2)

func _spiral(center: Vector2, radius: float, t: float, alpha: float, arms: int = 3) -> void:
	for arm in arms:
		var points := PackedVector2Array()
		for i in 23:
			var f := i / 22.0
			var angle := TAU * arm / arms + t * TAU * 0.55 + f * PI * 1.15
			points.append(center + Vector2.from_angle(angle) * radius * lerpf(0.18, 1.0, f))
		_stroke(points, 2.1, alpha * (0.7 if arm % 2 else 1.0), ICE)

func _draw() -> void:
	if not supports(style) or age >= duration:
		return
	var t := clampf(age / duration, 0.0, 1.0)
	var alpha := _alpha(t)
	var r := _radius()
	var alternate := -1.0 if hit_index % 2 else 1.0
	var offset := Vector2((hit_index % 3 - 1) * r * 0.11, (hit_index % 2 - 0.5) * r * 0.14)
	var c := contact_point + offset
	var travel := c - source_point
	var facing := travel.angle() if travel.length_squared() > 0.01 else 0.0
	match style:
		"claw":
			_slash(c, r * 1.1, -0.55 * alternate + (t - 0.2) * 0.2, alpha)
		"cross_claw":
			_slash(c - Vector2(r * 0.13, 0), r, -0.72, alpha)
			_slash(c + Vector2(r * 0.13, 0), r, 0.72, alpha * clampf(t * 7.0, 0, 1))
		"rake":
			_slash(c, r * 1.35, -0.32 * alternate, alpha, 7.0, 1.45)
			_burst(c, r * 0.65, t, alpha * 0.65, 5)
		"sweep":
			for trail in 3:
				_stroke(_arc(c, Vector2(r * 1.60, r * (0.40 + trail * 0.16)), -0.4 - t * 0.5, PI * 0.88, -0.13 * alternate), 5.3 - trail * 1.6, alpha * (1.0 - trail * 0.22))
		"uppercut":
			_slash(c + Vector2(0, (0.18 - t) * r * 0.5), r * 1.3, 0.08 * alternate, alpha, 6.5)
			_stroke(PackedVector2Array([c + Vector2(-r * 0.55, r * 1.1), c + Vector2(r * 0.10, -r * 0.35), c + Vector2(r * 0.48, -r * 1.45)]), 2.3, alpha * 0.55)
		"lunge":
			var start := c - Vector2.from_angle(facing) * minf(220.0, travel.length() * 0.60)
			for lane in [-1, 0, 1]:
				var shift: Vector2 = Vector2.from_angle(facing).orthogonal() * lane * r * 0.27
				_stroke(PackedVector2Array([start + shift * 1.7, c + shift]), 2.5 + (1 - absi(lane)) * 2.0, alpha)
			_slash(c, r * 0.70, facing - 0.8, alpha)
		"slam", "stomp":
			var ground := ground_point
			_ground_ring(ground, r * (1.55 if style == "slam" else 1.15), t, alpha, style == "slam")
			for crack in 5:
				var ray := Vector2.from_angle(PI * 2 * crack / 5.0 + 0.3)
				var middle := ground + ray * Vector2(r * 0.55, r * 0.20)
				var end := ground + ray * Vector2(r * (1.1 + t * 0.25), r * 0.40)
				_stroke(PackedVector2Array([ground, middle + Vector2(5, -4), end]), 2.1, alpha * 0.7, STONE)
			_chips(ground - Vector2(0, r * 0.12), r, t, alpha, 8)
			if style == "slam":
				_stroke(PackedVector2Array([c - Vector2(0, r * 1.35), ground]), 5.0 * (1.0 - t), alpha * 0.55)
		"bite", "bite_tear":
			_fangs(c, r, t, alpha, style == "bite_tear")
		"feral_claw":
			_slash(c, r * 1.32, -0.6 * alternate, alpha, 8.0, 1.4)
			_spiral(c, r * 1.18, t, alpha * 0.36, 2)
		"bolt":
			_bolt(c - Vector2(r * 0.25 * alternate, minf(235.0, r * 3.1)), c, 3.3, alpha)
			_burst(c, r * 0.9, t, alpha * 0.8)
		"chain":
			_bolt(source_point, c, 2.7, alpha)
			_stroke(_arc(c, Vector2.ONE * r * (0.35 + t * 0.7), 0.15, 5.6, t * 2), 1.8, alpha * 0.6)
		"spear":
			var direction := Vector2.from_angle(facing)
			var side := direction.orthogonal()
			var start := c - direction * minf(travel.length(), 290.0)
			var lance := PackedVector2Array([start, c - side * r * 0.2 - direction * r * 0.45, c + direction * r * 0.45, c + side * r * 0.2 - direction * r * 0.45])
			draw_colored_polygon(lance, _tint(ICE, alpha * 0.8))
			_stroke(PackedVector2Array([start, c + direction * r * 0.45]), 2.6, alpha)
			_bolt(start + side * r * 0.28, c, 1.2, alpha * 0.5)
		"storm":
			_spiral(c, r * 1.42, t, alpha * 0.7)
			for i in 3:
				var top := c + Vector2((i - 1) * r * 0.75, -r * 1.65)
				_bolt(top, c + Vector2((i - 1) * r * 0.22, r * 0.25), 2.0, alpha * (0.95 - i * 0.13), i)
		"ground_thunder":
			_ground_ring(ground_point, r * 1.35, t, alpha, true)
			_bolt(ground_point, c - Vector2(r * 0.1, r * 0.9), 3.1, alpha)
		"fork":
			var fork_point := c + Vector2(-r * 0.6, -r * 1.35)
			_bolt(source_point, fork_point, 2.8, alpha)
			for i in 3:
				_bolt(fork_point, c + Vector2((i - 1) * r * 0.65, absf(i - 1) * r * 0.25), 1.8, alpha * 0.85, i)
		"eruption":
			_ground_ring(ground_point, r * 1.6, t, alpha)
			for i in 3:
				var side := (i - 1) * r * 0.40
				_bolt(c + Vector2(side, -minf(320.0, r * 3.7)), ground_point + Vector2(side * 0.35, 0), 5.0 if i == 1 else 2.1, alpha * (1.0 if i == 1 else 0.65), i)
			_burst(c, r * 1.28, t, alpha * 0.65, 10)
		"guard", "armor":
			_shield(c, r * 1.05, t, alpha, style == "armor")
		"retaliation":
			_bolt(source_point, c, 3.0, alpha)
			var direction := Vector2.from_angle(facing)
			var side := direction.orthogonal()
			_stroke(PackedVector2Array([c - direction * r * 0.5 - side * r * 0.4, c, c - direction * r * 0.5 + side * r * 0.4]), 3.2, alpha)
			_burst(c, r * 0.85, t, alpha * 0.65, 5)
		"domain_echo":
			_ground_ring(ground_point, r * 1.15, t, alpha * 0.8)
			for i in 3:
				var ray := Vector2.from_angle(TAU * i / 3 + hit_index * 0.5)
				_bolt(c + ray * r * 0.85, c + ray * r * 0.2, 1.6, alpha * 0.75, i)
		"storm_charge":
			for i in 5:
				var direction := Vector2.from_angle(TAU * i / 5.0 + t * 0.8)
				_bolt(c + direction * r * (1.2 - t * 0.3), c + direction * r * 0.3, 1.7, alpha, i)
			_stroke(_arc(c, Vector2.ONE * r * 0.38, 0, TAU), 1.5, alpha * 0.8)
		"thunder_armor":
			_shield(c + Vector2(r * 0.28, r * 0.05), r * 0.72, t, alpha, true)
			_bolt(c + Vector2(-r * 0.15, -r * 0.65), c + Vector2(r * 0.4, r * 0.65), 1.4, alpha * 0.6)
		"replay_echo":
			for echo in 2:
				var radius := r * (0.65 + echo * 0.34 + t * 0.2)
				_stroke(_arc(c, Vector2.ONE * radius, 0.3, TAU - 0.55, t * PI + echo * PI), 2.4 - echo * 0.6, alpha * (1 - echo * 0.25))
				var tip := c + Vector2.from_angle(TAU - 0.55 + t * PI + echo * PI) * radius
				var direction := Vector2.from_angle(TAU - 0.55 + t * PI + echo * PI).orthogonal()
				_stroke(PackedVector2Array([tip - direction * 10 - direction.orthogonal() * 7, tip, tip - direction * 10 + direction.orthogonal() * 7]), 2.0, alpha)
		"lifesteal":
			for mote in 5:
				var progress := clampf(t * 1.28 - mote * 0.07, 0, 1)
				var p := c.lerp(source_point, progress) + Vector2(0, -sin(progress * PI) * (38 + mote * 5))
				draw_circle(p, 3.5 - mote * 0.3, _tint(WHITE, alpha), true, -1, true)
				var previous := c.lerp(source_point, maxf(0, progress - 0.09)) + Vector2(0, -sin(maxf(0, progress - 0.09) * PI) * (38 + mote * 5))
				_stroke(PackedVector2Array([previous, p]), 1.6, alpha * 0.6, ICE)
		"beast":
			_slash(c + Vector2(-r * 0.35, 0), r * 0.90, -0.85, alpha * 0.8, 4.0)
			_slash(c + Vector2(r * 0.35, 0), r * 0.90, 0.85, alpha * 0.8, 4.0)
			_spiral(c, r * (0.75 + t * 0.45), t, alpha * 0.5, 2)
		"absorb":
			_shield(c, r, t, alpha * 0.75)
			for i in 6:
				var direction := Vector2.from_angle(TAU * i / 6)
				var p := c + direction * r * (1.2 - t * 0.95)
				_stroke(PackedVector2Array([p + direction * 13, p]), 2.2, alpha, ICE)
		"purify":
			for i in 7:
				var p := c + Vector2((i - 3) * r * 0.24, r * 0.4 - t * r * (1.2 + (i % 3) * 0.25))
				_stroke(PackedVector2Array([p + Vector2(0, 10), p]), 1.5, alpha, ICE)
				if i % 2 == 0:
					_stroke(PackedVector2Array([p + Vector2(-4, 0), p + Vector2(4, 0)]), 1.1, alpha)
	if blocked and style not in ["guard", "armor", "thunder_armor", "absorb"]:
		_shield(c, r * 0.75, t, alpha * 0.58)
		_chips(c, r * 0.75, t, alpha * 0.8, 5)
