extends AnimatedSprite2D
## Only presentation lifetime: no combat timing, damage or gameplay callbacks.
@export var return_animation: StringName = &"idle_loop"

func _ready() -> void:
	animation_finished.connect(_on_animation_finished)

func _on_animation_finished() -> void:
	# Death holds the final authored frame; it must never return to a living pose.
	if animation in [&"die", &"Die", &"dead", &"Dead", &"death", &"Death", &"domain_die"]:
		return
	if sprite_frames.has_animation(return_animation):
		play(return_animation)
