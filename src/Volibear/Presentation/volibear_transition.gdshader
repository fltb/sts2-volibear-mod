shader_type canvas_item;
render_mode unshaded;

// NTransition owns this value: 0 is unobscured, 1 is fully covered black.
uniform float threshold : hint_range(0.0, 1.0) = 0.0;
uniform sampler2D portrait : source_color, filter_linear;

void fragment() {
    float progress = clamp(threshold, 0.0, 1.0);
    vec4 actor = texture(portrait, UV);
    float reveal = sin(progress * 3.14159265);
    float coverage = smoothstep(0.0, 1.0, progress);
    COLOR = vec4(actor.rgb * actor.a * reveal, coverage);
}
